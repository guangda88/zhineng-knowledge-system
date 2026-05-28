"""Fast FTS backfill using batch UPDATE with CTE."""
import os
import asyncio
import asyncpg
import re
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL")

_WORD_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}")

def segment(text: str) -> str:
    return " ".join(_WORD_RE.findall(text[:2000]))


async def backfill_docs(conn, batch_size=500):
    total = 0
    while True:
        rows = await conn.fetch("""
            SELECT id, content FROM documents
            WHERE search_vector IS NULL
            LIMIT $1
        """, batch_size)
        if not rows:
            break
        # Build batch update values
        pairs = [(r["id"], segment(r["content"])) for r in rows]
        # Use executemany with prepared statement
        await conn.executemany(
            "UPDATE documents SET search_vector = to_tsvector('simple', $2) WHERE id = $1",
            pairs,
        )
        total += len(rows)
        log.info(f"doc FTS: {total}")
    print(f"Done doc FTS: {total}")
    return total


async def backfill_chunks(conn, batch_size=2000):
    total = 0
    t0 = time.time()
    while True:
        rows = await conn.fetch("""
            SELECT id, content FROM doc_chunks
            WHERE search_vector IS NULL
            LIMIT $1
        """, batch_size)
        if not rows:
            break
        pairs = [(r["id"], segment(r["content"])) for r in rows]
        await conn.executemany(
            "UPDATE doc_chunks SET search_vector = to_tsvector('simple', $2) WHERE id = $1",
            pairs,
        )
        total += len(rows)
        elapsed = time.time() - t0
        rate = total / elapsed if elapsed > 0 else 0
        if total % 10000 == 0 or total < 10000:
            log.info(f"chunk FTS: {total} ({rate:.0f}/s)")
    elapsed = time.time() - t0
    print(f"Done chunk FTS: {total} in {elapsed:.0f}s ({total/elapsed:.0f}/s)")
    return total


async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    conn = await asyncpg.connect(DB_URL)
    log.info("DB connected")

    if target in ("docs", "both"):
        await backfill_docs(conn)
    if target in ("chunks", "both"):
        await backfill_chunks(conn)

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
