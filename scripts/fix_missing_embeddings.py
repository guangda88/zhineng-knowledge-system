"""补齐70个缺失embedding的文档
使用 embedding 服务 (localhost:8001) 生成向量并更新DB
"""
import asyncio
import asyncpg
import httpx
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_URL = os.getenv("DATABASE_URL")
EMBED_HOST = os.getenv("EMBED_HOST", "localhost")
EMBED_PORT = os.getenv("EMBED_PORT", "8001")
BATCH_SIZE = 16


async def main():
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch(
        "SELECT id, title, content FROM documents WHERE embedding IS NULL ORDER BY id"
    )
    print(f"Found {len(rows)} documents without embedding")

    if not rows:
        await conn.close()
        return

    async with httpx.AsyncClient(timeout=30) as client:
        updated = 0
        failed = 0
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            texts = [f"{r['title']}\n{r['content'][:2000]}" for r in batch]
            try:
                resp = await client.post(
                    f"http://{EMBED_HOST}:{EMBED_PORT}/embed_batch",
                    json={"texts": texts},
                    timeout=60,
                )
                if resp.status_code != 200:
                    print(f"Batch {i}: embed failed {resp.status_code}: {resp.text[:200]}")
                    failed += len(batch)
                    continue
                embeddings = resp.json()["embeddings"]
            except Exception as e:
                print(f"Batch {i}: embed error: {e}")
                failed += len(batch)
                continue

            for row, emb in zip(batch, embeddings):
                try:
                    await conn.execute(
                        "UPDATE documents SET embedding = $1::vector WHERE id = $2",
                        "[" + ",".join(map(str, emb)) + "]",
                        int(row["id"]),
                    )
                    updated += 1
                except Exception as e:
                    print(f"  Doc {row['id']} update failed: {e}")
                    failed += 1

            print(f"  Progress: {updated}/{len(rows)} (failed={failed})")

    await conn.close()
    print(f"Done: updated={updated}, failed={failed}")


if __name__ == "__main__":
    asyncio.run(main())
