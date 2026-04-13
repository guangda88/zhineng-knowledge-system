"""Rebuild search_vector column with jieba Chinese word segmentation.

PostgreSQL's built-in 'chinese' and 'simple' text search configs do NOT
perform Chinese word segmentation - they only split on whitespace/punctuation.
This script uses jieba to properly segment Chinese text, then stores the
result as a tsvector using PostgreSQL's 'simple' config (which preserves
the word boundaries we created).

Usage:
    python scripts/rebuild_search_vector.py --table documents
    python scripts/rebuild_search_vector.py --table guoxue_content --batch-size 500
"""

import argparse
import asyncio
import logging
import os
import time

import asyncpg
import jieba

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
)

CONTENT_COL = {
    "documents": "content",
    "guoxue_content": "body",
}
TITLE_COL = {
    "documents": "title",
    "guoxue_content": None,
}
STAGING_TABLES = {
    "documents": "doc_search_staging",
    "guoxue_content": "search_vector_staging",
}

jieba.setLogLevel(logging.WARNING)
_jieba_initialized = False


def init_jieba():
    global _jieba_initialized
    if _jieba_initialized:
        return
    custom_dict = os.path.join(
        os.path.dirname(__file__), "..", "backend", "services", "retrieval", "custom_dict.txt"
    )
    if os.path.exists(custom_dict):
        jieba.load_userdict(custom_dict)
        logger.info(f"Loaded custom dict: {custom_dict}")
    _jieba_initialized = True


_SINGLE_CHAR_DOMAIN_WORDS = frozenset("仁义礼智信道德气心神精")


def segment_text(text: str, max_len: int = 5000) -> str:
    if not text or not text.strip():
        return ""
    if len(text) > max_len:
        text = text[:max_len]
    words = jieba.lcut(text)
    filtered = [
        w.strip() for w in words if len(w.strip()) > 1 or w.strip() in _SINGLE_CHAR_DOMAIN_WORDS
    ]
    return " ".join(filtered)


async def ensure_staging_table(pool, table: str):
    staging = STAGING_TABLES[table]
    async with pool.acquire() as conn:
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {staging} (
                id INTEGER PRIMARY KEY,
                search_vector TSVECTOR
            ) TABLESPACE nvme
        """)
        logger.info(f"Staging table {staging} ready on NVMe")


async def batch_segment(pool, table: str, batch_size: int):
    init_jieba()
    staging = STAGING_TABLES[table]
    content_col = CONTENT_COL[table]
    title_col = TITLE_COL.get(table)

    async with pool.acquire() as conn:
        total = await conn.fetchval(f"""
            SELECT count(*) FROM {table} t
            WHERE NOT EXISTS (SELECT 1 FROM {staging} s WHERE s.id = t.id)
        """)

    logger.info(f"Table {table}: {total} rows to segment")

    processed = 0
    t0 = time.time()

    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, {title_col + ' AS title,' if title_col else ''} {content_col} AS content
                FROM {table} t
                WHERE NOT EXISTS (SELECT 1 FROM {staging} s WHERE s.id = t.id)
                ORDER BY t.id
                LIMIT $1
            """,
                batch_size,
            )

        if not rows:
            break

        segmented = []
        for row in rows:
            parts = []
            if title_col and row["title"]:
                parts.append(segment_text(str(row["title"])))
            if row["content"]:
                text = str(row["content"])
                parts.append(segment_text(text))

            seg_text = " ".join(p for p in parts if p)
            segmented.append((row["id"], seg_text))

        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(
                    f"""
                    INSERT INTO {staging} (id, search_vector)
                    VALUES ($1, to_tsvector('simple', $2))
                    ON CONFLICT (id) DO UPDATE SET search_vector = EXCLUDED.search_vector
                    """,
                    segmented,
                )

        processed += len(rows)
        elapsed = time.time() - t0
        rate = processed / elapsed if elapsed > 0 else 0
        logger.info(
            f"  batch: {processed}/{total} ({processed * 100 // max(total, 1)}%) rate={rate:.0f}/s"
        )

    elapsed = time.time() - t0
    logger.info(
        f"Segmentation done: {processed} rows in {elapsed:.0f}s ({processed / max(elapsed, 1):.0f}/s)"
    )


async def bulk_update(pool, table: str):
    staging = STAGING_TABLES[table]
    logger.info(f"Bulk updating {table}.search_vector from {staging}...")
    t0 = time.time()

    async with pool.acquire() as conn:
        result = await conn.fetchval(f"""
            WITH updated AS (
                UPDATE {table} t SET search_vector = s.search_vector
                FROM {staging} s
                WHERE t.id = s.id AND (
                    t.search_vector IS DISTINCT FROM s.search_vector
                    OR t.search_vector IS NULL
                )
                RETURNING 1
            )
            SELECT count(*) FROM updated
        """)

    elapsed = time.time() - t0
    rate = result / elapsed if elapsed > 0 else 0
    logger.info(f"Bulk update: {result} rows in {elapsed:.1f}s ({rate:.0f}/s)")
    return result


async def rebuild_index(pool, table: str):
    index_name = f"idx_{table}_search_vector"

    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT count(*) FROM pg_indexes WHERE indexname = $1", index_name
        )
        if existing:
            logger.info(f"Dropping old index {index_name}...")
            await conn.execute(f"DROP INDEX IF EXISTS {index_name}")

    logger.info(f"Creating GIN index {index_name} on {table}(search_vector)...")

    async with pool.acquire() as conn:
        await conn.execute("SET statement_timeout = '30min'")
        await conn.execute(f"""
            CREATE INDEX CONCURRENTLY {index_name}
            ON {table} USING gin (search_vector)
        """)
        await conn.execute("SET statement_timeout = DEFAULT")

    logger.info(f"Index {index_name} created")


async def main():
    parser = argparse.ArgumentParser(description="Rebuild search_vector with jieba segmentation")
    parser.add_argument("--table", required=True, choices=["documents", "guoxue_content"])
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--skip-segment", action="store_true", help="Skip segmentation, only bulk update + index"
    )
    parser.add_argument("--skip-index", action="store_true", help="Skip index rebuild")
    args = parser.parse_args()

    logger.info("Connecting to database...")
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=4)

    try:
        await ensure_staging_table(pool, args.table)

        if not args.skip_segment:
            await conn_execute(pool, "TRUNCATE " + STAGING_TABLES[args.table])
            await batch_segment(pool, args.table, args.batch_size)

        await bulk_update(pool, args.table)

        if not args.skip_index:
            await rebuild_index(pool, args.table)

        async with pool.acquire() as conn:
            count = await conn.fetchval(
                f"SELECT count(*) FROM {args.table} WHERE search_vector IS NOT NULL"
            )
            total = await conn.fetchval(f"SELECT count(*) FROM {args.table}")
        logger.info(f"Final: {count}/{total} rows have search_vector")

    finally:
        await pool.close()


async def conn_execute(pool, sql):
    async with pool.acquire() as conn:
        await conn.execute(sql)


if __name__ == "__main__":
    asyncio.run(main())
