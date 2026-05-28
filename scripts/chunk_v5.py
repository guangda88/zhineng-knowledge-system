#!/usr/bin/env python3
"""Chunking with single-row inserts."""

import asyncio
import os
import re
import time
import logging

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", os.getenv("DATABASE_URL"))
CHUNK_SIZE = 300
OVERLAP = 50
MIN_DOC_CHARS = 400
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

    if cats:
        doc_ids = [r["id"] for r in await conn.fetch(
            """SELECT id FROM documents
            WHERE length(content) > $1 AND category = ANY($2)
              AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = documents.id)
            ORDER BY id""",
            MIN_DOC_CHARS, cats,
        )]
    else:
        doc_ids = [r["id"] for r in await conn.fetch(
            """SELECT id FROM documents
            WHERE length(content) > $1
              AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = documents.id)
            ORDER BY id""",
            MIN_DOC_CHARS,
        )]

    logger.info(f"Found {len(doc_ids)} docs to chunk")

    # Prepared statement for single row insert
    stmt = "INSERT INTO doc_chunks (doc_id, chunk_index, content) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING"

    total_chunks = 0
    t0 = time.time()

    for i, doc_id in enumerate(doc_ids):
        doc = await conn.fetchrow("SELECT content FROM documents WHERE id = $1", doc_id)
        if not doc:
            continue

        parts = chunk_text(doc["content"])

        async with conn.transaction():
            for idx, (text, s, e) in enumerate(parts):
                await conn.execute(stmt, doc_id, idx, text)
                total_chunks += 1

        if (i + 1) % 10 == 0 or i == len(doc_ids) - 1:
            elapsed = time.time() - t0
            logger.info(f"Progress: {i+1}/{len(doc_ids)} docs, {total_chunks} chunks, {elapsed:.1f}s, {total_chunks/max(elapsed,1):.0f} c/s")

    await conn.close()
    elapsed = time.time() - t0
    logger.info(f"Done: {len(doc_ids)} docs, {total_chunks} chunks in {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
