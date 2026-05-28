#!/usr/bin/env python3
"""Backfill embeddings for doc_chunks using host GPU (CUDA).
Uses temp table + COPY + UPDATE JOIN for batch efficiency."""

import os
import asyncio
import time

import asyncpg
import numpy as np
from sentence_transformers import SentenceTransformer

DB_URL = os.getenv("DATABASE_URL")
MODEL_PATH = "/data/models/bge-small-zh"
BATCH_SIZE = 1024


async def main():
    print("Loading model on CUDA...")
    model = SentenceTransformer(MODEL_PATH).to("cuda")
    dim = model.get_sentence_embedding_dimension()
    print(f"Model loaded, dim={dim}")

    conn = await asyncpg.connect(DB_URL)

    null_count = await conn.fetchval(
        "SELECT COUNT(*) FROM doc_chunks WHERE embedding IS NULL"
    )
    print(f"Chunks without embedding: {null_count}")

    if null_count == 0:
        print("Nothing to do!")
        await conn.close()
        return

    processed = 0
    start_time = time.time()

    while True:
        rows = await conn.fetch(
            "SELECT id, content FROM doc_chunks WHERE embedding IS NULL ORDER BY id LIMIT $1",
            BATCH_SIZE,
        )
        if not rows:
            break

        ids = [r["id"] for r in rows]
        texts = [r["content"] for r in rows]

        embeddings = model.encode(texts, batch_size=128, show_progress_bar=False)
        embeddings = np.asarray(embeddings, dtype=np.float32)

        # Build binary vectors as bytes for pgvector
        rows_data = []
        for chunk_id, emb in zip(ids, embeddings):
            rows_data.append((chunk_id, emb.tobytes()))

        # Use batch upsert via temp table
        async with conn.transaction():
            await conn.execute(
                "CREATE TEMP TABLE IF NOT EXISTS _emb_tmp (id int PRIMARY KEY, emb bytea) ON COMMIT DELETE ROWS"
            )
            await conn.executemany(
                "INSERT INTO _emb_tmp (id, emb) VALUES ($1, $2)",
                rows_data,
            )
            result = await conn.execute(
                "UPDATE doc_chunks dc SET embedding = (_emb.emb)::vector "
                "FROM _emb_tmp _emb WHERE dc.id = _emb.id"
            )
            await conn.execute("TRUNCATE _emb_tmp")

        processed += len(ids)
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = (null_count - processed) / rate if rate > 0 else 0
        print(
            f"  {processed}/{null_count} ({processed/null_count*100:.1f}%) "
            f"| {rate:.0f}/s | ETA {remaining/60:.1f}min"
        )

    elapsed = time.time() - start_time
    print(f"\nDone! {processed} chunks in {elapsed:.1f}s ({processed/elapsed:.0f}/s)")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
