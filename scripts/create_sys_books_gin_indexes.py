"""Create GIN trigram indexes on sys_books table with long timeout.

These indexes are slow to build on 3M+ rows and need a longer timeout
than the default asyncpg command_timeout.
"""
import asyncio
import time
import asyncpg

DB_URL = "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sys_books_filename_trgm ON sys_books USING gin (filename gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS idx_sys_books_path_trgm ON sys_books USING gin (path gin_trgm_ops)",
]


async def main():
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2, command_timeout=7200)

    for idx_sql in INDEXES:
        idx_name = idx_sql.split("ON sys_books")[0].strip().split()[-1]

        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_indexes WHERE tablename='sys_books' AND indexname=$1",
                idx_name,
            )
            if exists:
                print(f"  {idx_name} already exists, skipping")
                continue

            print(f"Creating {idx_name}...", flush=True)
            t0 = time.time()
            try:
                await conn.execute(idx_sql)
                dt = time.time() - t0
                print(f"  Created {idx_name} in {dt:.1f}s")
            except Exception as e:
                dt = time.time() - t0
                print(f"  FAILED {idx_name} after {dt:.1f}s: {e}")

    async with pool.acquire() as conn:
        indexes = await conn.fetch(
            "SELECT indexname FROM pg_indexes WHERE tablename='sys_books' ORDER BY indexname"
        )
        print(f"\nAll sys_books indexes ({len(indexes)}):")
        for r in indexes:
            print(f"  {r['indexname']}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
