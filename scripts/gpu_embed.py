"""GPU-accelerated embedding generation for documents and guoxue_content.

Uses CUDA GPU (GTX 1660 Ti) for 10-100x faster embeddings vs CPU service.

Usage:
    python scripts/gpu_embed.py --table documents --categories 佛家,道家,武术,哲学,科学,心理学
    python scripts/gpu_embed.py --table guoxue_content --batch-size 64
"""

import argparse
import asyncio
import logging
import os
import time

import asyncpg
import torch
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb")
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
MAX_TEXT_LENGTH = 512
PROGRESS_INTERVAL = 1000


def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Loading {MODEL_NAME} on {device}...")
    model = SentenceTransformer(MODEL_NAME, device=device)
    logger.info(f"Model loaded on {device}: {next(model.parameters()).device}")
    return model


async def embed_table(model, table: str, categories: list[str] | None, batch_size: int):
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=4)

    try:
        if table == "documents":
            if categories:
                cat_ph = ", ".join(f"${i+1}" for i in range(len(categories)))
                where = f"embedding IS NULL AND category IN ({cat_ph})"
                args = categories
            else:
                where = "embedding IS NULL"
                args = []
        else:
            where = "embedding IS NULL"
            args = []

        total = await pool.fetchval(f"SELECT count(*) FROM {table} WHERE {where}", *args)
        logger.info(f"{table}: {total} rows to embed (batch_size={batch_size})")

        if total == 0:
            logger.info("Nothing to do")
            return

        updated = 0
        failed = 0
        t0 = time.time()

        while True:
            rows = await pool.fetch(
                f"SELECT id, content FROM {table} WHERE {where} ORDER BY id LIMIT {batch_size}",
                *args,
            )
            if not rows:
                break

            texts = []
            for row in rows:
                text = row["content"] or ""
                texts.append(text[:MAX_TEXT_LENGTH])

            try:
                embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
                async with pool.acquire() as conn:
                    for i, (row, emb) in enumerate(zip(rows, embeddings)):
                        vec_str = "[" + ",".join(map(str, emb.tolist())) + "]"
                        try:
                            await conn.execute(
                                f"UPDATE {table} SET embedding = $1::vector WHERE id = $2",
                                vec_str,
                                row["id"],
                            )
                        except Exception as e3:
                            logger.error(f"Single update failed id={row['id']}: {e3}")
                            failed += 1
                            continue
                        updated += 1
                        if updated % 500 == 0:
                            logger.info(f"  ... {updated}/{total} embedded so far")
            except Exception as e:
                logger.error(f"Batch failed: {e}")
                failed += len(rows)

            if updated % PROGRESS_INTERVAL < batch_size:
                elapsed = time.time() - t0
                rate = updated / elapsed if elapsed > 0 else 0
                eta = (total - updated) / rate if rate > 0 else 0
                logger.info(
                    f"Progress: {updated}/{total} "
                    f"({updated * 100 // total}%) "
                    f"rate={rate:.1f}/s "
                    f"ETA={eta / 60:.1f}min "
                    f"failed={failed}"
                )

        elapsed = time.time() - t0
        logger.info(f"Done: {updated} updated, {failed} failed in {elapsed:.0f}s")
    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser(description="GPU-accelerated embedding generation")
    parser.add_argument("--table", choices=["documents", "guoxue_content"], required=True)
    parser.add_argument("--categories", default=None, help="Comma-separated categories (documents only)")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    model = load_model()
    cats = [c.strip() for c in args.categories.split(",")] if args.categories else None
    asyncio.run(embed_table(model, args.table, cats, args.batch_size))


if __name__ == "__main__":
    main()
