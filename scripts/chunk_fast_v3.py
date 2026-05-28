#!/usr/bin/env python3
"""Ultra-fast chunking using COPY to temp table then INSERT SELECT."""

import asyncio
import io
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
BATCH_SIZE = 50
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

    # Create temp table for bulk insert
    await conn.execute("""
        CREATE TEMP TABLE IF NOT EXISTS tmp_chunks (
            doc_id int, chunk_index int, content text
        ) ON COMMIT DELETE ROWS
    """)
    await conn.execute("TRUNCATE tmp_chunks")

    # Get doc IDs
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

    total_chunks = 0
    total_docs = 0
    t0 = time.time()

    for batch_start in range(0, len(doc_ids), BATCH_SIZE):
        batch_ids = doc_ids[batch_start:batch_start + BATCH_SIZE]
        docs = await conn.fetch(
            "SELECT id, content FROM documents WHERE id = ANY($1)",
            batch_ids,
        )

        # Build TSV data for COPY
        buf = io.StringIO()
        batch_count = 0
        for doc in docs:
            parts = chunk_text(doc["content"])
            for idx, (text, s, e) in enumerate(parts):
                # Escape tab/newline in content
                safe_text = text.replace("\t", " ").replace("\n", "\\n")
                buf.write(f"{doc['id']}\t{idx}\t{safe_text}\n")
                batch_count += 1

        buf.seek(0)
        await conn.execute("TRUNCATE tmp_chunks")
        await conn.copy_into_table("tmp_chunks", source=buf)
        await conn.execute("""
            INSERT INTO doc_chunks (doc_id, chunk_index, content)
            SELECT doc_id, chunk_index, content FROM tmp_chunks
            ON CONFLICT (doc_id, chunk_index) DO NOTHING
        """)

        total_chunks += batch_count
        total_docs += len(docs)
        elapsed = time.time() - t0
        logger.info(f"Progress: {total_docs}/{len(doc_ids)} docs, {total_chunks} chunks, {elapsed:.1f}s")

    await conn.execute("DROP TABLE IF EXISTS tmp_chunks")
    await conn.close()
    elapsed = time.time() - t0
    logger.info(f"Done: {total_docs} docs, {total_chunks} chunks in {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
