"""Batch backfill source_file - small committed batches for HDD."""
import os
import asyncio
import asyncpg
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger()

DB_URL = os.getenv("DATABASE_URL")
BATCH = 1000


async def backfill_qigong(conn):
    total = await conn.fetchval("""
        SELECT count(*) FROM documents
        WHERE category = '气功' AND (source_file IS NULL OR source_file = '')
    """)
    log.info(f"气功待补: {total}")
    if total == 0:
        return 0

    updated = 0
    t0 = time.time()
    while True:
        n = await conn.execute("""
            UPDATE documents SET source_file = 'qigong:' || COALESCE(metadata->>'source', 'unknown')
            WHERE id IN (
                SELECT id FROM documents
                WHERE category = '气功' AND (source_file IS NULL OR source_file = '')
                LIMIT $1
            )
        """, BATCH)
        count = int(n.split()[-1])
        if count == 0:
            break
        updated += count
        if updated % 5000 < BATCH:
            elapsed = time.time() - t0
            rate = updated / elapsed if elapsed > 0 else 0
            eta = (total - updated) / rate if rate > 0 else 0
            log.info(f"气功: {updated}/{total} ({rate:.0f}/s, ETA {eta:.0f}s)")

    elapsed = time.time() - t0
    log.info(f"气功完成: {updated} in {elapsed:.0f}s ({updated/elapsed:.0f}/s)")
    return updated


async def backfill_buddhist(conn):
    total = await conn.fetchval("""
        SELECT count(*) FROM documents
        WHERE category = '佛家' AND (source_file IS NULL OR source_file = '')
    """)
    log.info(f"佛家待补: {total}")
    if total == 0:
        return 0

    # 有metadata source的
    r1 = await conn.execute("""
        UPDATE documents SET source_file = 'CBETA:' || metadata->>'source'
        WHERE id IN (
            SELECT id FROM documents
            WHERE category = '佛家' AND (source_file IS NULL OR source_file = '')
              AND metadata->>'source' IS NOT NULL
            LIMIT $1
        )
    """, BATCH)
    log.info(f"佛家(metadata): {r1}")

    # 标题含CBETA编码的
    r2 = await conn.execute("""
        UPDATE documents SET source_file = 'CBETA:' || substring(title from '\[[^\]]+\]')
        WHERE id IN (
            SELECT id FROM documents
            WHERE category = '佛家' AND (source_file IS NULL OR source_file = '')
              AND title ~ '\[[^\]]+\]'
            LIMIT $1
        )
    """, BATCH)
    log.info(f"佛家(title): {r2}")

    # 剩余标记unknown
    r3 = await conn.execute("""
        UPDATE documents SET source_file = 'CBETA:unknown'
        WHERE category = '佛家' AND (source_file IS NULL OR source_file = '')
    """)
    log.info(f"佛家(unknown): {r3}")
    return total


async def main():
    conn = await asyncpg.connect(DB_URL)
    t0 = time.time()

    await backfill_qigong(conn)
    await backfill_buddhist(conn)

    remaining = await conn.fetchval("""
        SELECT count(*) FROM documents WHERE source_file IS NULL OR source_file = ''
    """)
    log.info(f"=== 总耗时 {time.time()-t0:.0f}s, 剩余无source_file: {remaining} ===")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())