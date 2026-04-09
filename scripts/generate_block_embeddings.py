#!/usr/bin/env python3
"""为新导入的textbook_blocks_v2生成向量嵌入"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
import httpx

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb",
)
EMBED_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")
BATCH_SIZE = 20


async def main():
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)

    async with pool.acquire() as conn:
        unembedded = await conn.fetch(
            "SELECT id, content FROM textbook_blocks_v2 "
            "WHERE embedding IS NULL AND content IS NOT NULL "
            "AND LENGTH(content) > 10 ORDER BY id"
        )

    print(f"待生成嵌入的文本块: {len(unembedded)}")
    if not unembedded:
        await pool.close()
        return

    count = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(unembedded), BATCH_SIZE):
            batch = unembedded[i : i + BATCH_SIZE]
            texts = [r["content"][:512] for r in batch]

            try:
                resp = await client.post(f"{EMBED_URL}/embed_batch", json={"texts": texts})
                if resp.status_code != 200:
                    print(f"  嵌入服务返回 {resp.status_code}, 跳过批次")
                    continue

                embeddings = resp.json().get("embeddings", [])
            except Exception as e:
                print(f"  嵌入失败: {e}")
                continue

            async with pool.acquire() as conn:
                async with conn.transaction():
                    for j, row in enumerate(batch):
                        if j >= len(embeddings):
                            break
                        emb = embeddings[j]
                        await conn.execute(
                            "UPDATE textbook_blocks_v2 SET embedding = $1::vector WHERE id = $2",
                            str(emb),
                            row["id"],
                        )
                        count += 1

            print(f"  进度: {count}/{len(unembedded)} ({count*100//len(unembedded)}%)")

    print(f"\n完成! 共生成 {count} 个嵌入向量")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
