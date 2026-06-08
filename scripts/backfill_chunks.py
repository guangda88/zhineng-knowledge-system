#!/usr/bin/env python3
"""补全无chunk文档 — 批量创建chunk+embedding+FTS
用法: ZHINENG_DB_PASS=xxx python3 scripts/backfill_chunks.py --category 气功 --batch-size 500
"""
import os
import sys
import time
import asyncio
import argparse

import requests
import asyncpg

EMBED_URL = os.environ.get("EMBED_URL", "http://localhost:8001/embed")
CHUNK_SIZE = 400
MIN_CHUNK = 50


async def backfill(conn, category, batch_size, dry_run):
    rows = await conn.fetch(
        """SELECT d.id, d.content FROM documents d
        WHERE d.category = $1
        AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = d.id)
        AND char_length(d.content) >= $2
        ORDER BY d.id
        LIMIT $3""",
        category, MIN_CHUNK, batch_size,
    )
    if not rows:
        print(f"No unchunked docs found for '{category}'")
        return 0, 0

    print(f"Processing {len(rows)} docs for '{category}'")

    done = 0
    chunks_created = 0
    for doc in rows:
        doc_id = doc["id"]
        content = doc["content"]
        text = content.strip()
        if len(text) < MIN_CHUNK:
            continue

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        cur = ""
        for p in paragraphs:
            while len(p) > CHUNK_SIZE:
                if cur:
                    chunks.append(cur)
                chunks.append(p[:CHUNK_SIZE])
                p = p[CHUNK_SIZE:]
            if len(cur) + len(p) + 2 > CHUNK_SIZE and cur:
                chunks.append(cur)
                cur = p
            else:
                cur = f"{cur}\n\n{p}" if cur else p
        if cur:
            chunks.append(cur)
        chunks = [c for c in chunks if len(c.strip()) > 20]

        if not chunks:
            continue

        if dry_run:
            chunks_created += len(chunks)
            done += 1
            continue

        embs = []
        ok = True
        for c in chunks:
            try:
                r = requests.post(EMBED_URL, json={"text": c}, timeout=30)
                if r.status_code != 200:
                    ok = False
                    break
                embs.append(r.json()["embedding"])
            except Exception:
                ok = False
                break
            time.sleep(0.03)

        if not ok or len(embs) != len(chunks):
            print(f"  doc {doc_id}: embed partial, skip")
            continue

        async with conn.transaction():
            off = 0
            for i, (c, e) in enumerate(zip(chunks, embs)):
                es = "[" + ",".join(f"{x:.8f}" for x in e) + "]"
                await conn.execute(
                    "INSERT INTO doc_chunks(doc_id,chunk_index,content,start_offset,end_offset,embedding) VALUES($1,$2,$3,$4,$5,$6::vector)",
                    doc_id, i, c, off, off + len(c), es,
                )
                await conn.execute(
                    "UPDATE doc_chunks SET search_vector=to_tsvector('simple',content) WHERE doc_id=$1 AND chunk_index=$2",
                    doc_id, i,
                )
                off += len(c)

        chunks_created += len(chunks)
        done += 1
        if done % 100 == 0:
            print(f"  {done}/{len(rows)} docs, {chunks_created} chunks")

    return done, chunks_created


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--loop", action="store_true", help="keep running until no more docs")
    args = parser.parse_args()

    if not os.environ.get("ZHINENG_DB_PASS"):
        print("ERROR: ZHINENG_DB_PASS required")
        sys.exit(1)

    conn = await asyncpg.connect(
        host=os.environ.get("ZHINENG_DB_HOST", "localhost"),
        port=int(os.environ.get("ZHINENG_DB_PORT", "5436")),
        user=os.environ.get("ZHINENG_DB_USER", "zhineng"),
        password=os.environ.get("ZHINENG_DB_PASS", ""),
        database=os.environ.get("ZHINENG_DB_NAME", "zhineng_kb"),
    )

    total_done = 0
    total_chunks = 0
    round_num = 0
    while True:
        round_num += 1
        remaining = await conn.fetchval(
            """SELECT count(*) FROM documents d
            WHERE d.category = $1
            AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = d.id)
            AND char_length(d.content) >= $2""",
            args.category, MIN_CHUNK,
        )
        if remaining == 0:
            print(f"No more unchunked docs for '{args.category}'")
            break
        print(f"\n=== Round {round_num}: {remaining} remaining ===")
        done, chunks = await backfill(conn, args.category, args.batch_size, args.dry_run)
        total_done += done
        total_chunks += chunks
        print(f"Round {round_num}: {done} docs, {chunks} chunks")
        if not args.loop or done == 0:
            break

    await conn.close()
    print(f"\nTotal: {total_done} docs, {total_chunks} chunks")


if __name__ == "__main__":
    asyncio.run(main())
