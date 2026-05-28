#!/usr/bin/env python3
"""Fast backfill embeddings via Docker embedding service API - batch UPDATE version."""

import asyncio
import os
import time

import asyncpg
import httpx

DB_URL = os.getenv("DATABASE_URL")
EMBED_URL = "http://localhost:8001/embed_batch"
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "256"))
CONCURRENT = int(os.environ.get("CONCURRENT", "4"))
FETCH_SIZE = BATCH_SIZE * CONCURRENT


async def embed_texts(client, texts):
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
        t0 = time.time()
        rows = await conn.fetch(
            "SELECT id, content FROM doc_chunks WHERE embedding IS NULL ORDER BY id LIMIT $1",
            FETCH_SIZE,
        )
        if not rows:
            break
        print(f"  Fetched {len(rows)} rows in {time.time()-t0:.1f}s", flush=True)

        batches = [rows[i : i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
        t1 = time.time()
        results = await asyncio.gather(
            *[embed_texts(client, [r["content"] for r in b]) for b in batches]
        )
        print(f"  Embedded {len(rows)} texts in {time.time()-t1:.1f}s", flush=True)

        t2 = time.time()
        async with conn.transaction():
            for batch, embeddings in zip(batches, results):
                ids = []
                vecs = []
                for row, emb in zip(batch, embeddings):
                    ids.append(row["id"])
                    vecs.append("[" + ",".join(f"{v:.6f}" for v in emb) + "]")

                await conn.execute(
                    """
                    UPDATE doc_chunks d SET embedding = v.vec::vector
                    FROM (SELECT unnest($1::bigint[]) as id, unnest($2::text[]) as vec) v
                    WHERE d.id = v.id
                    """,
                    ids,
                    vecs,
                )
        print(f"  Updated DB in {time.time()-t2:.1f}s", flush=True)

        processed += len(rows)
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = (null_count - processed) / rate if rate > 0 else 0
        print(
            f"  {processed}/{null_count} ({processed/null_count*100:.1f}%) "
            f"| {rate:.0f}/s | ETA {remaining/60:.0f}min",
            flush=True,
        )

    elapsed = time.time() - start_time
    print(f"\nDone! {processed} chunks in {elapsed:.1f}s ({processed/elapsed:.0f}/s)")
    await client.aclose()
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
