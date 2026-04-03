#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
教材数据导入服务

功能：
1. 导入TOC到数据库
2. 提取文本块
3. 生成向量嵌入
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List

import asyncpg


class TextbookImporter:
    """教材导入服务"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool = None

    async def connect(self):
        """连接数据库"""
        self.pool = await asyncpg.create_pool(
            self.db_url, min_size=2, max_size=10, command_timeout=60, timeout=10
        )
        print("✅ 数据库连接成功")

    async def close(self):
        """关闭连接"""
        if self.pool:
            await self.pool.close()
            print("✅ 数据库连接已关闭")

    async def import_toc(self, textbook_id: str, toc_path: str, text_path: str) -> Dict[str, int]:
        """
        导入TOC到数据库

        Args:
            textbook_id: 教材ID
            toc_path: TOC JSON文件路径
            text_path: 教材文本文件路径

        Returns:
            统计信息
        """
        # 读取TOC
        with open(toc_path, "r", encoding="utf-8") as f:
            toc_data = json.load(f)

        # 读取文本
        with open(text_path, "r", encoding="utf-8") as f:
            text_lines = f.readlines()

        stats = {"nodes_created": 0, "blocks_created": 0, "embeddings_generated": 0}

        print(f"\n📚 开始导入教材 {textbook_id}...")

        # 递归导入节点
        async with self.pool.acquire() as conn:
            for item in toc_data.get("items", []):
                await self._import_node_recursive(
                    conn, textbook_id, item, None, 0, text_lines, stats
                )

        print("\n✅ 导入完成！")
        print(f"   节点数: {stats['nodes_created']}")
        print(f"   文本块数: {stats['blocks_created']}")

        return stats

    async def _import_node_recursive(
        self,
        conn,
        textbook_id: str,
        item: Dict[str, Any],
        parent_id: str,
        depth: int,
        text_lines: List[str],
        stats: Dict[str, int],
    ):
        """
        递归导入节点

        Args:
            conn: 数据库连接
            textbook_id: 教材ID
            item: 节点数据
            parent_id: 父节点ID
            depth: 深度
            text_lines: 文本行列表
            stats: 统计信息
        """
        # 生成节点ID
        node_id = f"{textbook_id}_{item.get('level', 1)}_{hash(item.get('title', '')) % 1000000}"

        # 构建路径
        if parent_id:

            async def get_parent_path():
                row = await conn.fetchrow(
                    "SELECT path FROM textbook_nodes WHERE id = $1", parent_id
                )
                return row["path"] if row else ""

            parent_path = await get_parent_path()
        else:
            parent_path = ""

        path = f"{parent_path} > {item.get('title', '')}"

        # 提取内容
        line_range = item.get("line_range")
        content = None
        _range_value = None  # noqa: F841
        if line_range and len(line_range) == 2:
            start, end = line_range
            if end > start:
                content_lines = text_lines[start:end]
                content = "".join(content_lines).strip()
                # 暂时不存储line_range，因为需要range类型
                # 可以后续通过metadata存储

        # 插入节点
        metadata = {"source": "toc_ai_generated", "line_range": line_range}  # 存储在metadata中

        await conn.execute(
            """
            INSERT INTO textbook_nodes (
                id, name, path, level, parent_id, textbook_id,
                content, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                path = EXCLUDED.path,
                content = EXCLUDED.content,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            """,
            node_id,
            item.get("title", ""),
            path,
            item.get("level", 1),
            parent_id,
            textbook_id,
            content,
            json.dumps(metadata),
        )

        stats["nodes_created"] += 1
        print(f"  [{'▓' * ((depth % 10) + 1)}] {item.get('title', '')[:50]}")

        # 提取文本块（仅对叶子节点）
        children = item.get("children", [])
        if content and not children:
            await self._extract_and_insert_blocks(
                conn, node_id, content, line_range, text_lines, stats
            )

        # 递归处理子节点
        for child in item.get("children", []):
            await self._import_node_recursive(
                conn, textbook_id, child, node_id, depth + 1, text_lines, stats
            )

    async def _extract_and_insert_blocks(
        self,
        conn,
        node_id: str,
        content: str,
        line_range: tuple,
        text_lines: List[str],
        stats: Dict[str, int],
    ):
        """
        提取并插入文本块

        Args:
            conn: 数据库连接
            node_id: 节点ID
            content: 节点内容
            line_range: 行范围
            text_lines: 文本行列表
            stats: 统计信息
        """
        # 简单分块：按段落
        paragraphs = content.split("\n\n")
        paragraphs = [p.strip() for p in paragraphs if p.strip() and len(p) > 20]

        for idx, paragraph in enumerate(paragraphs):
            await conn.execute(
                """
                INSERT INTO textbook_blocks (node_id, content, block_order)
                VALUES ($1, $2, $3)
                """,
                node_id,
                paragraph,
                idx,
            )
            stats["blocks_created"] += 1

    async def generate_embeddings(self, textbook_id: str, limit: int = 100) -> int:
        """
        生成向量嵌入

        Args:
            textbook_id: 教材ID
            limit: 生成数量限制

        Returns:
            生成的嵌入数量
        """
        from backend.services.retrieval.vector import VectorRetriever

        print(f"\n🤖 开始生成向量嵌入（限制: {limit}）...")

        count = 0
        async with self.pool.acquire() as conn:
            # 获取未生成嵌入的文本块
            rows = await conn.fetch(
                """
                SELECT id, content
                FROM textbook_blocks tb
                JOIN textbook_nodes tn ON tb.node_id = tn.id
                WHERE tn.textbook_id = $1
                AND tb.embedding IS NULL
                LIMIT $2
                """,
                textbook_id,
                limit,
            )

            if not rows:
                print("没有需要生成嵌入的文本块")
                return 0

            retriever = VectorRetriever(self.pool)
            contents = [row["content"] for row in rows if row["content"] and row["content"].strip()]

            if not contents:
                return 0

            try:
                embeddings = await retriever.embed_batch(contents)
            except Exception as e:
                print(f"⚠️  BGE模型不可用，尝试通过嵌入服务生成: {e}")
                embeddings = await self._embed_via_service(contents)

            if not embeddings:
                print("⚠️  无法生成嵌入向量")
                return 0

            content_idx = 0
            for row in rows:
                if not row["content"] or not row["content"].strip():
                    continue
                if content_idx >= len(embeddings):
                    break
                embedding = embeddings[content_idx]
                content_idx += 1

                await conn.execute(
                    "UPDATE textbook_blocks SET embedding = $1 WHERE id = $2",
                    str(embedding),
                    row["id"],
                )
                count += 1

        print(f"✅ 生成完成！总数: {count}")
        return count

    async def _embed_via_service(self, texts: List[str]) -> List[List[float]]:
        """通过嵌入服务生成嵌入向量（备用方案）"""
        import httpx

        embeddings = []
        embed_url = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")
        async with httpx.AsyncClient(timeout=30.0) as client:
            for text in texts:
                try:
                    resp = await client.post(f"{embed_url}/embed", json={"text": text})
                    if resp.status_code == 200:
                        embeddings.append(resp.json()["embedding"])
                    else:
                        print(f"⚠️  嵌入服务返回 {resp.status_code}")
                        return []
                except Exception as e:
                    print(f"⚠️  嵌入服务连接失败: {e}")
                    return []
        return embeddings


async def main():
    """主函数"""
    # 配置
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("错误: 请设置 DATABASE_URL 环境变量")
        sys.exit(1)
    textbook_id = "7"
    toc_path = "data/processed/textbooks_v2/07-气功与人类文化/toc_ai_generated.json"
    text_path = "data/textbooks/txt格式/7智能气功科学气功与人类文化2010版.txt"

    # 创建导入器
    importer = TextbookImporter(db_url)

    try:
        # 连接数据库
        await importer.connect()

        # 导入TOC
        _stats = await importer.import_toc(textbook_id, toc_path, text_path)  # noqa: F841

        # 生成嵌入（示例：前100个）
        await importer.generate_embeddings(textbook_id, limit=100)

    finally:
        # 关闭连接
        await importer.close()


if __name__ == "__main__":
    asyncio.run(main())
