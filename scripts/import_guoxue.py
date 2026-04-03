#!/usr/bin/env python3
"""Import guoxue.db (SQLite) -> guoxue_content (PostgreSQL) - streaming version."""

import asyncio
import os
import sqlite3
import time

import asyncpg

SQLITE_PATH = "/home/ai/zhineng-knowledge-system/lingzhi_ubuntu/database/guoxue.db"
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://zhineng:zhineng123@localhost:5436/zhineng_kb"
)
BATCH_SIZE = 100


async def get_imported_tables(pool: asyncpg.Pool) -> set:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT source_table FROM guoxue_content")
        return {r["source_table"] for r in rows}


async def import_table(pool: asyncpg.Pool, table_name: str, book_id: int) -> int:
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    cur = sqlite_conn.cursor()
    cur.execute(f"SELECT body, bid FROM [{table_name}]")

    total = 0
    batch = []
    async with pool.acquire() as pg_conn:
        async with pg_conn.transaction():
            for row in cur:
                body = row[0]
                bid = row[1] if row[1] else 0
                batch.append((book_id, body, bid, table_name))
                if len(batch) >= BATCH_SIZE:
                    await pg_conn.executemany(
                        "INSERT INTO guoxue_content (book_id, body, chapter_id, source_table) "
                        "VALUES ($1, $2, $3, $4)",
                        batch,
                    )
                    total += len(batch)
                    batch.clear()
            if batch:
                await pg_conn.executemany(
                    "INSERT INTO guoxue_content (book_id, body, chapter_id, source_table) "
                    "VALUES ($1, $2, $3, $4)",
                    batch,
                )
                total += len(batch)
                batch.clear()

    sqlite_conn.close()
    return total


async def main():
    print(f"[{time.strftime('%H:%M:%S')}] Connecting...", flush=True)
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=2)

    already = await get_imported_tables(pool)
    print(f"[{time.strftime('%H:%M:%S')}] Already imported: {len(already)} tables", flush=True)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    cur = sqlite_conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wx%' ORDER BY name"
    )
    all_tables = [row[0] for row in cur.fetchall()]
    sqlite_conn.close()

    # Build active table list, skip already imported
    active = []
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    cur = sqlite_conn.cursor()
    for t in all_tables:
        if t in already:
            continue
        cur.execute(f"SELECT count(*) FROM [{t}]")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            active.append((t, int(t[2:]), cnt))
    sqlite_conn.close()

    total_expected = sum(c for _, _, c in active)
    print(
        f"[{time.strftime('%H:%M:%S')}] {len(active)} tables remaining, {total_expected:,} rows",
        flush=True,
    )

    imported = 0
    t0 = time.time()
    for i, (table_name, book_id, expected) in enumerate(active):
        cnt = await import_table(pool, table_name, book_id)
        imported += cnt
        elapsed = time.time() - t0
        rate = imported / elapsed if elapsed > 0 else 0
        print(
            f"[{time.strftime('%H:%M:%S')}] {i+1}/{len(active)} {table_name}: "
            f"{cnt:,} | total: {imported:,} | {rate:.0f} r/s",
            flush=True,
        )

    elapsed = time.time() - t0
    print(
        f"\n[{time.strftime('%H:%M:%S')}] Done! {imported:,} rows in {elapsed:.1f}s",
        flush=True,
    )
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
