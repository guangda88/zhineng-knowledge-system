"""Generate embeddings for guji_documents via the local embedding service.

Usage:
    python scripts/generate_guji_embeddings.py [--batch-size 32] [--limit 0]

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
BATCH_SIZE = 32
MAX_TEXT_LENGTH = 8192


async def fetch_embedding(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    resp = await client.post(
        f"{EMBEDDING_URL}/embed_batch",
        json={"texts": texts, "normalize": True},
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=0, help="Max rows to process (0=all)")
    args = parser.parse_args()

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb",
    )

    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=4)

    try:
        total = await pool.fetchval(
            "SELECT count(*) FROM guji_documents WHERE embedding IS NULL"
        )
        if args.limit > 0:
            total = min(total, args.limit)

        logger.info(f"guji_documents: {total} rows to embed (batch_size={args.batch_size})")

        if total == 0:
            logger.info("Nothing to do")
            return

        updated = 0
        failed = 0
        t0 = time.time()

        async with httpx.AsyncClient(timeout=120.0) as client:
            while True:
                limit_clause = f"LIMIT {args.batch_size}"
                rows = await pool.fetch(
                    f"SELECT id, title, content FROM guji_documents "
                    f"WHERE embedding IS NULL ORDER BY id {limit_clause}"
                )
                if not rows:
                    break

                texts = []
                for row in rows:
                    text = (row["title"] or "") + "\n" + (row["content"] or "")
                    texts.append(text[:MAX_TEXT_LENGTH])

                try:
                    embeddings = await fetch_embedding(client, texts)

                    async with pool.acquire() as conn:
                        async with conn.transaction():
                            for row, emb in zip(rows, embeddings):
                                vector_str = "[" + ",".join(map(str, emb)) + "]"
                                await conn.execute(
                                    "UPDATE guji_documents SET embedding = $1::vector WHERE id = $2",
                                    vector_str,
                                    row["id"],
                                )
                    updated += len(rows)

                except Exception as e:
                    logger.error(f"Batch failed: {e}")
                    failed += len(rows)

                if updated % 1000 < args.batch_size:
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

                if args.limit > 0 and updated >= args.limit:
                    break

        elapsed = time.time() - t0
        logger.info(f"Done: {updated} updated, {failed} failed in {elapsed:.0f}s")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
