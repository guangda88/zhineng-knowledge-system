#!/usr/bin/env python3
"""
从 SQLite textbooks.db 批量导入教材数据到 PostgreSQL

数据源: data/textbooks.db
目标表: textbook_toc, textbook_blocks_v2, textbook_metadata
"""

import asyncio
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_URL = os.getenv(
    "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
)
SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "textbooks.db",
)

import asyncpg


async def import_chapters_to_toc(pool: asyncpg.Pool) -> dict:
    """从SQLite chapters表导入到PostgreSQL textbook_toc"""
    conn_sqlite = sqlite3.connect(SQLITE_PATH)
    cur = conn_sqlite.cursor()

    chapters = cur.execute(
        "SELECT id, textbook_id, chapter_number, level, parent_id, title, "
        "char_count, order_index FROM chapters ORDER BY textbook_id, order_index"
    ).fetchall()

    stats = {"total": len(chapters), "inserted": 0, "skipped": 0}

    async with pool.acquire() as conn:
        existing = await conn.fetch("SELECT id FROM textbook_toc")
        existing_ids = {r["id"] for r in existing}

        async with conn.transaction():
            for ch in chapters:
                ch_id, tb_id, ch_num, level, parent_id, title, char_count, order_idx = ch

                if ch_id in existing_ids:
                    stats["skipped"] += 1
                    continue

                await conn.execute(
                    """
                    INSERT INTO textbook_toc
                        (id, textbook_id, level, title, parent_id, generated)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    ch_id,
                    tb_id,
                    level or 1,
                    (title or "")[:500],
                    parent_id,
                    False,
                )
                stats["inserted"] += 1

    conn_sqlite.close()
    return stats


async def import_nodes(pool: asyncpg.Pool) -> dict:
    """从SQLite chapters创建textbook_nodes记录"""
    conn_sqlite = sqlite3.connect(SQLITE_PATH)
    cur = conn_sqlite.cursor()

    chapters = cur.execute(
        "SELECT id, textbook_id, level, parent_id, title, char_count, order_index "
        "FROM chapters ORDER BY textbook_id, order_index"
    ).fetchall()

    stats = {"total": len(chapters), "inserted": 0, "skipped": 0}

    async with pool.acquire() as conn:
        existing = await conn.fetch("SELECT id FROM textbook_nodes")
        existing_ids = {r["id"] for r in existing}

        async with conn.transaction():
            for ch in chapters:
                ch_id, tb_id, level, parent_id, title, char_count, order_idx = ch

                node_id = f"{tb_id}_{ch_id}"
                if node_id in existing_ids:
                    stats["skipped"] += 1
                    continue

                parent_node_id = f"{tb_id}_{parent_id}" if parent_id else None

                await conn.execute(
                    """
                    INSERT INTO textbook_nodes
                        (id, name, path, level, parent_id, textbook_id, content, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    node_id,
                    (title or "")[:200],
                    f"教材{tb_id}",
                    min(max(level or 1, 1), 5),
                    parent_node_id,
                    str(tb_id),
                    title if char_count and char_count > 20 else None,
                    json.dumps(
                        {
                            "source": "sqlite_import",
                            "char_count": char_count,
                            "order_index": order_idx,
                        }
                    ),
                )
                stats["inserted"] += 1

    conn_sqlite.close()
    return stats


async def import_blocks_v2(pool: asyncpg.Pool) -> dict:
    """从SQLite chapters表导入内容文本到PostgreSQL textbook_blocks_v2

    SQLite chapters表中title字段实际存储的是段落文本内容。
    """
    conn_sqlite = sqlite3.connect(SQLITE_PATH)
    cur = conn_sqlite.cursor()

    chapters = cur.execute(
        "SELECT id, textbook_id, level, parent_id, title, char_count, order_index "
        "FROM chapters WHERE char_count > 20 ORDER BY textbook_id, order_index"
    ).fetchall()

    stats = {"total": len(chapters), "inserted": 0, "skipped": 0}

    async with pool.acquire() as conn:
        existing = set()
        rows = await conn.fetch(
            "SELECT node_id, content FROM textbook_blocks_v2"
        )
        for r in rows:
            existing.add((r["node_id"], r["content"][:100] if r["content"] else ""))

        max_id = await conn.fetchval(
            "SELECT COALESCE(MAX(id), 0) FROM textbook_blocks_v2"
        )

        batch_size = 100
        batch = []

        async with conn.transaction():
            for ch in chapters:
                ch_id, tb_id, level, parent_id, content, char_count, order_idx = ch

                if not content or len(content) < 20:
                    continue

                node_id = f"{tb_id}_{ch_id}"

                key = (node_id, content[:100])
                if key in existing:
                    stats["skipped"] += 1
                    continue

                max_id += 1
                batch.append(
                    (
                        max_id,
                        node_id,
                        content,
                        order_idx or 0,
                        json.dumps(
                            {
                                "textbook_id": tb_id,
                                "chapter_id": ch_id,
                                "level": level,
                                "parent_id": parent_id,
                                "source": "sqlite_chapters_import",
                                "char_count": char_count,
                            }
                        ),
                    )
                )

                if len(batch) >= batch_size:
                    await conn.executemany(
                        """
                        INSERT INTO textbook_blocks_v2
                            (id, node_id, content, block_order, metadata)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT DO NOTHING
                        """,
                        batch,
                    )
                    stats["inserted"] += len(batch)
                    print(f"  已导入 {stats['inserted']} 块...")
                    batch = []

            if batch:
                await conn.executemany(
                    """
                    INSERT INTO textbook_blocks_v2
                        (id, node_id, content, block_order, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT DO NOTHING
                    """,
                    batch,
                )
                stats["inserted"] += len(batch)

    conn_sqlite.close()
    return stats


async def sync_metadata(pool: asyncpg.Pool) -> dict:
    """从SQLite textbooks表同步元数据到PostgreSQL textbook_metadata"""
    conn_sqlite = sqlite3.connect(SQLITE_PATH)
    cur = conn_sqlite.cursor()

    textbooks = cur.execute(
        "SELECT id, number, title, total_chars, chinese_chars, quality_score, "
        "quality_grade, version FROM textbooks ORDER BY number"
    ).fetchall()

    stats = {"total": len(textbooks), "updated": 0}

    async with pool.acquire() as conn:
        async with conn.transaction():
            for tb in textbooks:
                tb_id, number, title, total_chars, chinese_chars, quality, grade, version = tb

                await conn.execute(
                    """
                    INSERT INTO textbook_metadata
                        (id, title, category, version, description)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        updated_at = NOW()
                    """,
                    str(tb_id),
                    title,
                    "智能气功科学",
                    version or "2010版",
                    f"总字数{total_chars:,}，中文字符{chinese_chars:,}，质量评分{quality}",
                )
                stats["updated"] += 1

    conn_sqlite.close()
    return stats


async def main():
    print("=" * 60)
    print("教材数据批量导入: SQLite → PostgreSQL")
    print("=" * 60)

    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)

    try:
        print("\n[1/3] 同步元数据...")
        meta_stats = await sync_metadata(pool)
        print(f"  元数据: {meta_stats}")

        print("\n[2/3] 导入章节目录...")
        toc_stats = await import_chapters_to_toc(pool)
        print(f"  章节: {toc_stats}")

        print("\n[2.5/3] 创建教材节点...")
        node_stats = await import_nodes(pool)
        print(f"  节点: {node_stats}")

        print("\n[3/3] 导入文本块...")
        block_stats = await import_blocks_v2(pool)
        print(f"  文本块: {block_stats}")

        print("\n" + "=" * 60)
        print("导入完成!")
        print(f"  元数据: {meta_stats['updated']} 本")
        print(f"  章节: {toc_stats['inserted']} 新增, {toc_stats['skipped']} 已存在")
        print(f"  文本块: {block_stats['inserted']} 新增")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
