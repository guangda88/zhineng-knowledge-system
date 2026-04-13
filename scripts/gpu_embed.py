"""GPU-accelerated embedding generation for documents and guoxue_content.

Uses CUDA GPU (GTX 1660 Ti) for fast embeddings.
Writes to a staging table on NVMe SSD tablespace for fast I/O,
then bulk-updates the target table.

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
STAGING_TABLE = "doc_embeddings_staging"
GUOXUE_STAGING = "guoxue_embeddings_staging"
CONTENT_COL = {"documents": "content", "guoxue_content": "body"}


def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Loading {MODEL_NAME} on {device}...")
    model = SentenceTransformer(MODEL_NAME, device=device)
    logger.info(f"Model loaded on {device}: {next(model.parameters()).device}")
    return model


async def ensure_staging_table(pool, table):
    staging = GUOXUE_STAGING if table == "guoxue_content" else STAGING_TABLE
    async with pool.acquire() as conn:
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {staging} (
                id INT PRIMARY KEY,
                embedding vector(512)
            ) TABLESPACE nvme
        """)
        await conn.execute(f"TRUNCATE {staging}")
    logger.info(f"Staging table {staging} ready on NVMe tablespace")
    return staging


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

        content_col = CONTENT_COL.get(table, "content")

        total = await pool.fetchval(f"SELECT count(*) FROM {table} WHERE {where}", *args)
        logger.info(f"{table}: {total} rows to embed (batch_size={batch_size})")

        if total == 0:
            logger.info("Nothing to do")
            return

        staging = await ensure_staging_table(pool, table)

        updated = 0
        failed = 0
        t0 = time.time()
        batch_num = 0

        while True:
            rows = await pool.fetch(
                f"SELECT id, {content_col} FROM {table} WHERE {where} "
                f"AND id NOT IN (SELECT id FROM {staging}) "
                f"ORDER BY id LIMIT {batch_size}",
                *args,
            )
            if not rows:
                break

            texts = [(row[content_col] or "")[:MAX_TEXT_LENGTH] for row in rows]

            try:
                embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        for row, emb in zip(rows, embeddings):
                            vec_str = "[" + ",".join(map(str, emb.tolist())) + "]"
                            try:
                                await conn.execute(
                                    f"INSERT INTO {staging} (id, embedding) VALUES ($1, $2::vector) "
                                    f"ON CONFLICT (id) DO UPDATE SET embedding = $2::vector",
                                    row["id"],
                                    vec_str,
                                )
                                updated += 1
                            except Exception as e3:
                                logger.error(f"Insert failed id={row['id']}: {e3}")
                                failed += 1

                batch_num += 1
                elapsed = time.time() - t0
                rate = updated / elapsed if elapsed > 0 else 0
                logger.info(
                    f"  batch {batch_num}: {updated}/{total} ({updated*100//total}%) "
                    f"rate={rate:.1f}/s"
                )
            except Exception as e:
                logger.error(f"Batch failed: {e}")
                failed += len(rows)

        # Bulk update from staging
        logger.info(f"Bulk updating {table} from staging table...")
        bulk_t0 = time.time()
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"UPDATE {table} t SET embedding = s.embedding "
                f"FROM {staging} s WHERE t.id = s.id"
            )
            bulk_count = int(result.split()[-1])
        bulk_time = time.time() - bulk_t0
        logger.info(f"Bulk update: {bulk_count} rows in {bulk_time:.1f}s ({bulk_count/bulk_time:.1f}/s)")

        # Clean up staging
        async with pool.acquire() as conn:
            await conn.execute(f"TRUNCATE {staging}")

        elapsed = time.time() - t0
        logger.info(f"Done: {bulk_count} updated, {failed} failed in {elapsed:.0f}s")
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
