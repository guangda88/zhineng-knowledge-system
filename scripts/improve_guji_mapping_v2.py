#!/usr/bin/env python3
"""
古籍数据关联改进脚本 v2

功能:
1. 从wx200/wx201导入有意义的书籍内容到guji_documents
2. 建立bid与书名的映射
3. 更新guji_documents的title等元数据
4. 建立索引
"""

import asyncio
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

import asyncpg

# 配置
SQLITE_DB = Path("/home/ai/zhineng-knowledge-system/lingzhi_ubuntu/database/guoxue.db")
POSTGRES_CONTAINER = "dfdd3b278296_zhineng-postgres"
BID_BOOK_MAPPING = Path("/home/ai/zhineng-knowledge-system/data/bid_book_mapping.json")


def load_bid_mapping() -> Dict[str, str]:
    """加载bid到书名的映射"""
    import json

    with open(BID_BOOK_MAPPING, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {str(k): v.get("book_name", "") for k, v in data.items()}


def get_wx200_books(limit: int = 500) -> List[Tuple]:
    """从wx200获取有bid的记录"""
    conn = sqlite3.connect(str(SQLITE_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, bid, substr(body, 1, 500) as preview
        FROM wx200
        WHERE bid > 0
        ORDER BY bid, id
        LIMIT ?
    """,
        (limit,),
    )

    results = [(row["id"], row["bid"], row["preview"]) for row in cursor.fetchall()]
    conn.close()
    return results


def get_wx201_books(limit: int = 500) -> List[Tuple]:
    """从wx201获取记录"""
    conn = sqlite3.connect(str(SQLITE_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, bid, substr(body, 1, 500) as preview
        FROM wx201
        WHERE bid IS NOT NULL
        ORDER BY bid, id
        LIMIT ?
    """,
        (limit,),
    )

    results = [(row["id"], row["bid"], row["preview"]) for row in cursor.fetchall()]
    conn.close()
    return results


async def update_guji_documents():
    """更新guji_documents表"""
    db_url = "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"

    conn = await asyncpg.connect(db_url)

    try:
        # 1. 检查当前状态
        print("=" * 70)
        print("📊 当前guji_documents状态")
        print("=" * 70)

        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as has_title,
                MIN(source_id) as min_id,
                MAX(source_id) as max_id
            FROM guji_documents
        """
        )
        print(f"总记录: {stats['total']}")
        print(f"有标题: {stats['has_title']}")
        print(f"ID范围: {stats['min_id']} - {stats['max_id']}")

        # 2. 导入bid映射
        print("\n" + "=" * 70)
        print("📚 加载bid书名映射")
        print("=" * 70)

        bid_mapping = load_bid_mapping()
        print(f"加载了 {len(bid_mapping)} 个bid映射")

        # 3. 从SQLite获取书籍记录
        print("\n" + "=" * 70)
        print("📖 从wx200获取书籍记录")
        print("=" * 70)

        wx200_books = get_wx200_books(1000)
        print(f"获取了 {len(wx200_books)} 条wx200记录")

        # 4. 插入新的书籍记录到guji_documents
        print("\n" + "=" * 70)
        print("💾 插入新记录到guji_documents")
        print("=" * 70)

        inserted = 0
        for source_id, bid, preview in wx200_books:
            # 检查是否已存在
            exists = await conn.fetchval(
                "SELECT 1 FROM guji_documents WHERE source_table = 'wx200' AND source_id = $1",
                source_id,
            )

            if not exists:
                book_name = bid_mapping.get(str(bid), "")
                # 提取第一行作为标题
                first_line = preview.split("\n")[0][:100] if preview else ""

                await conn.execute(
                    """
                    INSERT INTO guji_documents (source_table, source_id, title, content, content_length)
                    VALUES ($1, $2, $3, $4, $5)
                """,
                    "wx200",
                    source_id,
                    book_name or first_line,
                    preview,
                    len(preview),
                )

                inserted += 1
                if inserted % 100 == 0:
                    print(f"  已插入 {inserted} 条...")

        print(f"✅ 共插入 {inserted} 条新记录")

        # 5. 更新现有记录的title
        print("\n" + "=" * 70)
        print("🔄 更新现有记录的标题")
        print("=" * 70)

        # 首先通过bid_source_id关联更新
        updated = await conn.execute(
            """
            UPDATE guji_documents g
            SET title = bm.book_name
            FROM (
                SELECT unnest($1::text[]) as bid, unnest($2::text[]) as book_name
            ) bm
            WHERE g.source_id::text = bm.bid
            AND g.title IS NULL OR g.title = ''
        """,
            list(bid_mapping.keys()),
            list(bid_mapping.values()),
        )

        print(f"✅ 更新了 {updated} 条记录的标题")

        # 6. 建立索引
        print("\n" + "=" * 70)
        print("🔍 建立索引")
        print("=" * 70)

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_guji_source_bid ON guji_documents(source_table, source_id)",
            "CREATE INDEX IF NOT EXISTS idx_guji_title ON guji_documents USING gin(to_tsvector('simple', title))",
        ]

        for idx_sql in indexes:
            await conn.execute(idx_sql)
            print(f"  ✅ {idx_sql.split()[2]}")

        # 7. 最终统计
        print("\n" + "=" * 70)
        print("📊 最终统计")
        print("=" * 70)

        final_stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as has_title,
                COUNT(DISTINCT source_table) as sources
            FROM guji_documents
        """
        )

        print(f"总记录: {final_stats['total']}")
        print(f"有标题: {final_stats['has_title']}")
        print(f"来源表数: {final_stats['sources']}")

        # 显示书名样本
        print("\n" + "=" * 70)
        print("📖 书名样本 (前20条)")
        print("=" * 70)

        samples = await conn.fetch(
            """
            SELECT source_id, LEFT(title, 40) as title, LEFT(content, 50) as preview
            FROM guji_documents
            WHERE title IS NOT NULL AND title != ''
            ORDER BY source_id
            LIMIT 20
        """
        )

        for row in samples:
            print(f"  [{row['source_id']:6d}] {row['title']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(update_guji_documents())
