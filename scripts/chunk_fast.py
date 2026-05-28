#!/usr/bin/env python3
"""Fast batch chunking - inserts chunks in bulk without embedding or jieba."""

import asyncio
import os
import re
import sys
import time
import logging

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", os.getenv("DATABASE_URL"))

CHUNK_SIZE = 300
OVERLAP = 50
MIN_DOC_CHARS = 400
BATCH_SIZE = 500
CATEGORIES = os.getenv("CHUNK_CATEGORIES", "")

_SENTENCE_ENDS = re.compile(r"[。！？；\n]")


def chunk_text(text: str):
    if len(text) <= CHUNK_SIZE:
        return [(text, 0, len(text))]
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            m = _SENTENCE_ENDS.search(text[end:min(end + 50, len(text))])
            if m:
                end += m.end()
        else:
            end = len(text)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append((chunk, start, end))
        start = end - OVERLAP
        if chunks and start <= chunks[-1][1]:
            start = end
    return chunks


async def main():
    conn = await asyncpg.connect(DB_URL)
    logger.info("DB connected")

    cats = [c.strip() for c in CATEGORIES.split(",") if c.strip()] if CATEGORIES else []

    total_chunks = 0
    total_docs = 0
    t0 = time.time()

    while True:
        if cats:
            docs = await conn.fetch(
                """
                SELECT id, content FROM documents d
                WHERE length(d.content) > $1
                  AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = d.id)
                  AND d.category = ANY($2)
                ORDER BY id LIMIT $3
                """,
                MIN_DOC_CHARS, cats, BATCH_SIZE,
            )
        else:
            docs = await conn.fetch(
                """
                SELECT id, content FROM documents d
                WHERE length(d.content) > $1
                  AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = d.id)
                ORDER BY id LIMIT $2
                """,
                MIN_DOC_CHARS, BATCH_SIZE,
            )

        if not docs:
            break

        rows = []
        for doc in docs:
            parts = chunk_text(doc["content"])
            for idx, (text, s, e) in enumerate(parts):
                rows.append((doc["id"], idx, text))

        if rows:
            async with conn.transaction():
                await conn.executemany(
                    """INSERT INTO doc_chunks (doc_id, chunk_index, content)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (doc_id, chunk_index) DO NOTHING""",
                    rows,
                )
            total_chunks += len(rows)

        total_docs += len(docs)
        elapsed = time.time() - t0
        rate = total_chunks / elapsed if elapsed > 0 else 0
        logger.info(f"Progress: {total_docs} docs, {total_chunks} chunks, {rate:.0f} chunks/s")

    await conn.close()
    elapsed = time.time() - t0
    logger.info(f"Done: {total_docs} docs, {total_chunks} chunks in {elapsed:.1f}s ({total_chunks/elapsed:.0f} chunks/s)")


if __name__ == "__main__":
    asyncio.run(main())
