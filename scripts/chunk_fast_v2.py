#!/usr/bin/env python3
"""Fast batch chunking using pre-fetched doc IDs to avoid NOT EXISTS."""

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
BATCH_SIZE = 100
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

    # Fetch all doc IDs that need chunking (one-time query)
    if cats:
        doc_ids = await conn.fetch(
            """SELECT id FROM documents d
            WHERE length(d.content) > $1 AND d.category = ANY($2)
              AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = d.id)
            ORDER BY id""",
            MIN_DOC_CHARS, cats,
        )
    else:
        doc_ids = await conn.fetch(
            """SELECT id FROM documents d
            WHERE length(d.content) > $1
              AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = d.id)
            ORDER BY id""",
            MIN_DOC_CHARS,
        )

    ids = [r["id"] for r in doc_ids]
    logger.info(f"Found {len(ids)} docs to chunk")

    total_chunks = 0
    total_docs = 0
    t0 = time.time()

    # Process in batches by fetching content
    for batch_start in range(0, len(ids), BATCH_SIZE):
        batch_ids = ids[batch_start:batch_start + BATCH_SIZE]
        docs = await conn.fetch(
            "SELECT id, content FROM documents WHERE id = ANY($1)",
            batch_ids,
        )

        rows = []
        for doc in docs:
            parts = chunk_text(doc["content"])
            for idx, (text, s, e) in enumerate(parts):
                rows.append((doc["id"], idx, text))

        if rows:
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
        logger.info(f"Progress: {total_docs}/{len(ids)} docs, {total_chunks} chunks, {rate:.0f} chunks/s")

    await conn.close()
    elapsed = time.time() - t0
    logger.info(f"Done: {total_docs} docs, {total_chunks} chunks in {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
