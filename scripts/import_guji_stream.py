#!/usr/bin/env python3
"""Optimized guji import using rowid pagination instead of OFFSET."""

import asyncio
import logging
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SOURCE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"
DATABASE_URL = "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
BATCH_SIZE = 5000


def get_wx_tables(db_path: str) -> list[tuple[str, int]]:
    """Get wx tables with row counts."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA cache_size = -256000")  # 256MB cache
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wx%' ORDER BY name"
    )
    tables = []
    for (name,) in cursor.fetchall():
        cursor.execute(f"SELECT COUNT(*) FROM [{name}]")
        cnt = cursor.fetchone()[0]
        if cnt > 0:
            tables.append((name, cnt))
    conn.close()
    return tables


async def import_table(pg: asyncpg.Connection, db_path: str, table: str) -> int:
    """Import one table using rowid-based pagination."""
    sqlite_conn = sqlite3.connect(db_path)
    sqlite_conn.execute("PRAGMA cache_size = -256000")
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    imported = 0
    last_id = 0
    t0 = time.time()

    while True:
        cursor.execute(
            f"SELECT * FROM [{table}] WHERE rowid > ? ORDER BY rowid LIMIT {BATCH_SIZE}", (last_id,)
        )
        rows = cursor.fetchall()

        if not rows:
            break

        data = []
        for row in rows:
            row_id = row["id"] if "id" in row.keys() else row[0]
            content = None
            if "body" in row.keys() and row["body"]:
                content = row["body"]
            elif "d" in row.keys() and row["d"]:
                content = row["d"]

            if not content or len(content) < 10:
                continue

            title = content[:50].split("\n")[0][:50]
            data.append((table, row_id, title, content, len(content), None, "古籍", "{}"))

        if data:
            async with pg.transaction():
                await pg.executemany(
                    """INSERT INTO guji_documents (source_table, source_id, title, content, content_length, dynasty, category, tags)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                       ON CONFLICT (source_table, source_id) DO NOTHING""",
                    data,
                )
            imported += len(data)

        last_id = rows[-1]["id"] if "id" in rows[-1].keys() else rows[-1][0]
        elapsed = time.time() - t0
        rate = imported / elapsed if elapsed > 0 else 0
        logger.info(f"  {table}: {imported:,} rows ({rate:.0f}/s, last_id={last_id})")

    sqlite_conn.close()
    return imported


async def main():
    if not SOURCE_DB.exists():
        logger.error(f"Source DB not found: {SOURCE_DB}")
        return

    tables = get_wx_tables(str(SOURCE_DB))
    total_source = sum(c for _, c in tables)
    logger.info(f"Found {len(tables)} non-empty wx tables, {total_source:,} total rows")

    pg = await asyncpg.connect(DATABASE_URL)
    try:
        # Already truncated above

        total = 0
        t_start = time.time()
        for i, (table, expected) in enumerate(tables, 1):
            logger.info(f"[{i}/{len(tables)}] {table} (~{expected:,} rows)")
            count = await import_table(pg, str(SOURCE_DB), table)
            total += count

        row = await pg.fetchrow("SELECT COUNT(*) as c FROM guji_documents")
        elapsed = time.time() - t_start
        logger.info(f"DONE in {elapsed:.0f}s. Imported: {total:,}, PG count: {row['c']:,}")
    finally:
        await pg.close()


if __name__ == "__main__":
    asyncio.run(main())
