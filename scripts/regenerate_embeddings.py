"""Regenerate embeddings for documents/textbook_blocks via the local embedding service.

Usage:
    python scripts/regenerate_embeddings.py [--batch-size 32] [--limit 0]

The embedding service must be running at localhost:8001 (zhineng-embedding container).
"""

import argparse
import asyncio
import logging
import os
import sys
import time

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EMBEDDING_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")
MAX_TEXT_LENGTH = 8192

TABLES = [
    {"name": "documents", "text_columns": ["title", "content"], "label": "documents"},
    {"name": "textbook_blocks", "text_columns": ["content"], "label": "textbook_blocks"},
    {"name": "textbook_blocks_v2", "text_columns": ["content"], "label": "textbook_blocks_v2"},
]


async def fetch_embeddings(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    resp = await client.post(
        f"{EMBEDDING_URL}/embed_batch",
        json={"texts": texts},
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


async def regenerate_table(
    pool, client: httpx.AsyncClient, table: dict, batch_size: int, limit: int
):
    table_name = table["name"]
    text_cols = table["text_columns"]
    label = table["label"]
    col_expr = ", ".join(text_cols)

    total = await pool.fetchval(f"SELECT count(*) FROM {table_name} WHERE embedding IS NULL")
    if limit > 0:
        total = min(total, limit)

    if total == 0:
        logger.info(f"[{label}] No rows to update")
        return 0

    logger.info(f"[{label}] Processing {total} rows...")
    updated = 0
    failed = 0
    t0 = time.time()

    while True:
        rows = await pool.fetch(
            f"SELECT id, {col_expr} FROM {table_name} "
            f"WHERE embedding IS NULL ORDER BY id LIMIT {batch_size}"
        )
        if not rows:
            break

        texts = []
        for row in rows:
            parts = [str(row[c]) for c in text_cols if row[c]]
            texts.append("\n".join(parts)[:MAX_TEXT_LENGTH])

        try:
            embeddings = await fetch_embeddings(client, texts)

            async with pool.acquire() as conn:
                async with conn.transaction():
                    for row, emb in zip(rows, embeddings):
                        vector_str = "[" + ",".join(map(str, emb)) + "]"
                        await conn.execute(
                            f"UPDATE {table_name} SET embedding = $1::vector WHERE id = $2",
                            vector_str,
                            row["id"],
                        )
            updated += len(rows)

        except Exception as e:
            logger.error(f"[{label}] Batch failed: {e}")
            failed += len(rows)

        if updated % 500 < batch_size:
            elapsed = time.time() - t0
            rate = updated / elapsed if elapsed > 0 else 0
            eta = (total - updated) / rate if rate > 0 else 0
            logger.info(
                f"[{label}] Progress: {updated}/{total} "
                f"({updated * 100 // total}%) "
                f"rate={rate:.1f}/s ETA={eta / 60:.1f}min failed={failed}"
            )

        if limit > 0 and updated >= limit:
            break

    elapsed = time.time() - t0
    logger.info(f"[{label}] Done: {updated} updated, {failed} failed in {elapsed:.0f}s")
    return updated


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=0, help="Max rows per table (0=all)")
    parser.add_argument(
        "--tables", type=str, default="", help="Comma-separated table names to process"
    )
    args = parser.parse_args()

    target_tables = TABLES
    if args.tables:
        names = set(args.tables.split(","))
        target_tables = [t for t in TABLES if t["name"] in names]

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb",
    )
    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=4)

    try:
        t0 = time.time()
        async with httpx.AsyncClient(timeout=120.0) as client:
            for table in target_tables:
                await regenerate_table(pool, client, table, args.batch_size, args.limit)
        elapsed = time.time() - t0
        logger.info(f"All done in {elapsed:.0f}s")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
