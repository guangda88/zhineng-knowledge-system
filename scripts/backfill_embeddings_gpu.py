#!/usr/bin/env python3
"""Backfill embeddings using host GPU (CUDA) + sentence_transformers.

Usage:
    python3 scripts/backfill_embeddings_gpu.py              # all chunks
    BATCH_SIZE=128 python3 scripts/backfill_embeddings_gpu.py  # custom batch

~40x faster than Docker API. GTX 1660 Ti: ~500 embeddings/sec with batch_size=64.
"""

import asyncio
import os
import sys
import time

import asyncpg
import numpy as np
from sentence_transformers import SentenceTransformer

DB_URL = os.getenv("DATABASE_URL")
MODEL_PATH = "/data/models/bge-small-zh"
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "64"))
FETCH_SIZE = BATCH_SIZE * 4  # fetch more rows, embed in sub-batches

print(f"Loading model from {MODEL_PATH} ...", flush=True)
model = SentenceTransformer(MODEL_PATH)
model = model.to("cuda")
print(f"Model loaded. CUDA device: {model.device}", flush=True)


async def main():
    conn = await asyncpg.connect(DB_URL)

    null_count = await conn.fetchval(
        "SELECT COUNT(*) FROM doc_chunks WHERE embedding IS NULL"
    )
    print(f"Chunks without embedding: {null_count}", flush=True)

    if null_count == 0:
        print("Nothing to do!")
        await conn.close()
        return

    processed = 0
    start_time = time.time()

    while True:
        rows = await conn.fetch(
            "SELECT id, content FROM doc_chunks WHERE embedding IS NULL ORDER BY id LIMIT $1",
            FETCH_SIZE,
        )
        if not rows:
            break

        ids = [r["id"] for r in rows]
        texts = [r["content"] for r in rows]

        # Encode all texts in one batch on GPU
        embeddings = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False)
        embeddings = np.asarray(embeddings)

        # Write to DB
        async with conn.transaction():
            for i, (chunk_id, emb) in enumerate(zip(ids, embeddings)):
                vec_str = "[" + ",".join(f"{v:.6f}" for v in emb) + "]"
                await conn.execute(
                    "UPDATE doc_chunks SET embedding = $1::vector WHERE id = $2",
                    vec_str,
                    chunk_id,
                )

        processed += len(rows)
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = (null_count - processed) / rate if rate > 0 else 0
        print(
            f"  {processed}/{null_count} ({processed/null_count*100:.1f}%) "
            f"| {rate:.0f}/s | ETA {remaining/60:.1f}min",
            flush=True,
        )

    elapsed = time.time() - start_time
    print(f"\nDone! {processed} chunks in {elapsed:.1f}s ({processed/elapsed:.0f}/s)")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
