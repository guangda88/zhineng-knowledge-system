#!/usr/bin/env python3
"""Backfill embeddings via Docker embedding service API."""

import os
import asyncio
import time

import asyncpg
import httpx

DB_URL = os.getenv("DATABASE_URL")
EMBED_URL = "http://localhost:8001/embed_batch"
BATCH_SIZE = 64
CONCURRENT_REQUESTS = 4


async def embed_batch(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    resp = await client.post(EMBED_URL, json={"texts": texts}, timeout=120)
    resp.raise_for_status()
    return resp.json()["embeddings"]


async def main():
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
    client = httpx.AsyncClient()

    while True:
        rows = await conn.fetch(
            "SELECT id, content FROM doc_chunks WHERE embedding IS NULL ORDER BY id LIMIT $1",
            BATCH_SIZE * CONCURRENT_REQUESTS,
        )
        if not rows:
            break

        # Split into sub-batches for concurrent embedding
        sub_batches = [rows[i : i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]

        # Embed all sub-batches concurrently
        embed_tasks = [
            embed_batch(client, [r["content"] for r in batch]) for batch in sub_batches
        ]
        embed_results = await asyncio.gather(*embed_tasks)

        # Write to DB
        async with conn.transaction():
            for batch, embeddings in zip(sub_batches, embed_results):
                for row, emb in zip(batch, embeddings):
                    vec_str = "[" + ",".join(f"{v:.8f}" for v in emb) + "]"
                    await conn.execute(
                        "UPDATE doc_chunks SET embedding = $1::vector WHERE id = $2",
                        vec_str,
                        row["id"],
                    )

        processed += len(rows)
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = (null_count - processed) / rate if rate > 0 else 0
        print(
            f"  {processed}/{null_count} ({processed/null_count*100:.1f}%) "
            f"| {rate:.0f}/s | ETA {remaining/60:.1f}min"
        )

    elapsed = time.time() - start_time
    print(f"\nDone! {processed} chunks in {elapsed:.1f}s ({processed/elapsed:.0f}/s)")
    await client.aclose()
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
