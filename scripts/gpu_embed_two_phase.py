"""Two-phase GPU embedding: encode to file, then bulk import.

Phase 1: Read rows from DB, encode on GPU, write embeddings to a binary file on NVMe.
Phase 2: Read binary file, bulk UPDATE embeddings to DB in batches.

This separates GPU encoding (fast) from HDD I/O (slow), allowing us to
encode all rows first and then do the slow writes separately.

Usage:
    # Phase 1 only (encode to file)
    python scripts/gpu_embed_two_phase.py --table guoxue_content --phase encode --output /tmp/guoxue_embs.bin

    # Phase 2 only (import from file)
    python scripts/gpu_embed_two_phase.py --table guoxue_content --phase import --input /tmp/guoxue_embs.bin --flush-size 100

    # Both phases
    python scripts/gpu_embed_two_phase.py --table guoxue_content --phase both --output /tmp/guoxue_embs.bin

Binary format (per row):
    [4 bytes: id (int32)] [2048 bytes: embedding (512 x float32)]
"""

import argparse
import asyncio
import logging
import os
import struct
import time

import asyncpg
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", os.getenv("DATABASE_URL"))
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
MAX_TEXT_LENGTH = 512
EMB_DIM = 512
ROW_BYTES = 4 + EMB_DIM * 4  # id (int32) + embedding (512 * float32)


def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Loading {MODEL_NAME} on {device}...")
    model = SentenceTransformer(MODEL_NAME, device=device)
    logger.info(f"Model loaded on {device}: {next(model.parameters()).device}")
    return model


async def encode_phase(model, table, categories, output_path, batch_size):
    """Phase 1: Read rows, encode on GPU, write to binary file."""
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2)

    try:
        if table == "documents" and categories:
            cat_ph = ", ".join(f"${i+1}" for i in range(len(categories)))
            where = f"embedding IS NULL AND category IN ({cat_ph})"
            args = categories
        else:
            where = "embedding IS NULL"
            args = []

        total = await pool.fetchval(f"SELECT count(*) FROM {table} WHERE {where}", *args)
        logger.info(f"Phase 1: {table} has {total} rows to encode")

        if total == 0:
            logger.info("Nothing to encode")
            return

        encoded = 0
        t0 = time.time()

        with open(output_path, "wb") as f:
            offset = 0
            while True:
                rows = await pool.fetch(
                    f"SELECT id, content FROM {table} WHERE {where} ORDER BY id LIMIT {batch_size} OFFSET {offset}",
                    *args,
                )
                if not rows:
                    break

                texts = [(row["content"] or "")[:MAX_TEXT_LENGTH] for row in rows]
                ids = [row["id"] for row in rows]

                embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

                for row_id, emb in zip(ids, embeddings):
                    f.write(struct.pack("<i", row_id))
                    f.write(emb.astype(np.float32).tobytes())

                encoded += len(rows)
                offset += len(rows)

                elapsed = time.time() - t0
                rate = encoded / elapsed if elapsed > 0 else 0
                logger.info(f"  encoded {encoded}/{total} ({encoded*100//total}%) rate={rate:.1f}/s")

        elapsed = time.time() - t0
        file_size = os.path.getsize(output_path)
        logger.info(
            f"Phase 1 done: {encoded} rows encoded in {elapsed:.0f}s ({encoded/elapsed:.1f}/s), "
            f"file={file_size/1024/1024:.1f}MB"
        )
    finally:
        await pool.close()


async def import_phase(table, input_path, flush_size):
    """Phase 2: Read binary file, bulk UPDATE to DB."""
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2)

    try:
        file_size = os.path.getsize(input_path)
        total_rows = file_size // ROW_BYTES
        logger.info(f"Phase 2: importing {total_rows} embeddings from {file_size/1024/1024:.1f}MB")

        updated = 0
        t0 = time.time()
        pending = []

        with open(input_path, "rb") as f:
            row_idx = 0
            while True:
                data = f.read(ROW_BYTES)
                if len(data) < ROW_BYTES:
                    break

                row_id = struct.unpack("<i", data[:4])[0]
                emb_bytes = data[4:]
                vec_str = "[" + ",".join(f"{v:.6f}" for v in np.frombuffer(emb_bytes, dtype=np.float32)) + "]"
                pending.append((row_id, vec_str))
                row_idx += 1

                if len(pending) >= flush_size:
                    count = await _flush_batch(pool, table, pending)
                    updated += count
                    elapsed = time.time() - t0
                    rate = updated / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"  imported {updated}/{total_rows} ({updated*100//total_rows}%) "
                        f"rate={rate:.1f}/s ETA={((total_rows-updated)/rate)/60:.1f}min"
                    )
                    pending = []

        if pending:
            count = await _flush_batch(pool, table, pending)
            updated += count

        elapsed = time.time() - t0
        logger.info(f"Phase 2 done: {updated} updated in {elapsed:.0f}s ({updated/elapsed:.1f}/s)")
    finally:
        await pool.close()


async def _flush_batch(pool, table, pending):
    """Flush pending embeddings via temp table + UPDATE FROM."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "CREATE TEMP TABLE IF NOT EXISTS _emb_buf (id INT, emb vector(512)) ON COMMIT DELETE ROWS"
            )
            await conn.execute("TRUNCATE _emb_buf")
            for row_id, vec_str in pending:
                await conn.execute(
                    "INSERT INTO _emb_buf (id, emb) VALUES ($1, $2::vector)",
                    row_id,
                    vec_str,
                )
            result = await conn.execute(
                f"UPDATE {table} d SET embedding = b.emb FROM _emb_buf b WHERE d.id = b.id"
            )
            return int(result.split()[-1])


def main():
    parser = argparse.ArgumentParser(description="Two-phase GPU embedding")
    parser.add_argument("--table", choices=["documents", "guoxue_content"], required=True)
    parser.add_argument(
        "--phase",
        choices=["encode", "import", "both"],
        required=True,
        help="encode=GPU→file, import=file→DB, both=encode then import",
    )
    parser.add_argument("--categories", default=None, help="Comma-separated categories (documents only)")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--flush-size", type=int, default=100, help="Rows per DB write batch (import phase)")
    parser.add_argument("--output", default="/tmp/embeddings.bin", help="Binary file path for encode phase")
    parser.add_argument("--input", default=None, help="Binary file path for import phase (default: --output)")
    args = parser.parse_args()

    cats = [c.strip() for c in args.categories.split(",")] if args.categories else None
    input_path = args.input or args.output

    if args.phase in ("encode", "both"):
        model = load_model()
        asyncio.run(encode_phase(model, args.table, cats, args.output, args.batch_size))

    if args.phase in ("import", "both"):
        asyncio.run(import_phase(args.table, input_path, args.flush_size))


if __name__ == "__main__":
    main()
