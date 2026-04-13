"""Generate embeddings for documents table (categories 佛家/道家/武术/哲学/科学/心理学).

Usage:
    python scripts/generate_document_embeddings.py [--categories 佛家,道家] [--batch-size 32]

The embedding service must be running at localhost:8001 (zhineng-embedding container).
"""

import argparse
import asyncio
import logging
import os
import time

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EMBEDDING_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")
BATCH_SIZE = 32
MAX_TEXT_LENGTH = 8192
PROGRESS_INTERVAL = 500


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
    parser.add_argument(
        "--categories",
        default="佛家,道家,武术,哲学,科学,心理学",
        help="Comma-separated categories to embed (default: all new domains)",
    )
    args = parser.parse_args()

    cats = [c.strip() for c in args.categories.split(",")]
    logger.info(f"Categories to embed: {cats}")

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb",
    )

    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=4)

    try:
        cat_placeholders = ", ".join(f"${i+1}" for i in range(len(cats)))
        total = await pool.fetchval(
            f"SELECT count(*) FROM documents "
            f"WHERE embedding IS NULL AND category IN ({cat_placeholders})",
            *cats,
        )

        logger.info(f"documents: {total} rows to embed (batch_size={args.batch_size})")

        if total == 0:
            logger.info("Nothing to do")
            return

        updated = 0
        failed = 0
        t0 = time.time()

        async with httpx.AsyncClient(timeout=120.0) as client:
            while True:
                rows = await pool.fetch(
                    f"SELECT id, content FROM documents "
                    f"WHERE embedding IS NULL AND category IN ({cat_placeholders}) "
                    f"ORDER BY id LIMIT {args.batch_size}",
                    *cats,
                )
                if not rows:
                    break

                texts = []
                for row in rows:
                    text = row["content"] or ""
                    texts.append(text[:MAX_TEXT_LENGTH])

                try:
                    embeddings = await fetch_embedding(client, texts)

                    ids = [row["id"] for row in rows]
                    vectors = [
                        "[" + ",".join(map(str, emb)) + "]"
                        for emb in embeddings
                    ]
                    async with pool.acquire() as conn:
                        async with conn.transaction():
                            await conn.execute(
                                "UPDATE documents SET embedding = data.vec::vector "
                                "FROM (SELECT unnest($1::int[]) as id, unnest($2::text[]) as vec) data "
                                "WHERE documents.id = data.id",
                                ids,
                                vectors,
                            )
                    updated += len(rows)

                except Exception as e:
                    logger.error(f"Batch failed: {e}")
                    failed += len(rows)

                if updated % PROGRESS_INTERVAL < args.batch_size:
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


if __name__ == "__main__":
    asyncio.run(main())
