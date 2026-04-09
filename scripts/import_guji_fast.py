#!/usr/bin/env python3
"""古籍数据快速导入脚本 - 使用COPY命令批量导入"""

import asyncio
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


SOURCE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"


async def create_guji_tables(conn: asyncpg.Connection) -> None:
    """创建古籍数据表"""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS guji_documents (
            id SERIAL PRIMARY KEY,
            source_table VARCHAR(50) NOT NULL,
            source_id INTEGER NOT NULL,
            title TEXT,
            content TEXT,
            content_length INTEGER,
            dynasty VARCHAR(50),
            category VARCHAR(100),
            tags JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(source_table, source_id)
        );
    """
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_guji_source ON guji_documents(source_table, source_id);
    """
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_guji_title ON guji_documents USING gin(to_tsvector('simple', title));
    """
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_guji_content ON guji_documents USING gin(to_tsvector('simple', content));
    """
    )

    await conn.execute(
        """
        TRUNCATE guji_documents;
    """
    )

    logger.info("古籍数据表创建完成")


async def import_table_data(
    conn: asyncpg.Connection, source_db: str, table: str, batch_size: int = 50000
) -> int:
    """导入单个表的数据"""
    sqlite_conn = sqlite3.connect(source_db)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    total = cursor.fetchone()[0]
    logger.info(f"开始导入表 {table}: {total:,} 条记录")

    imported = 0
    offset = 0

    while offset < total:
        cursor.execute(f"SELECT * FROM {table} LIMIT {batch_size} OFFSET {offset}")
        rows = cursor.fetchall()

        if not rows:
            break

        # 准备数据
        data = []
        for row in rows:
            # wx表结构: id, body, bid (或其他)
            row_id = row["id"] if "id" in row.keys() else row[0]
            title = None
            content = None

            if "body" in row.keys() and row["body"]:
                content = row["body"]
                # 从内容开头提取标题（前20字）
                if content and len(content) > 20:
                    title = content[:30].split("\n")[0][:50]
            elif "d" in row.keys() and row["d"]:
                content = row["d"]

            content_length = len(content) if content else 0

            # 跳过过短的内容
            if content_length < 10:
                continue

            data.append(
                [
                    table,
                    row_id,
                    title,
                    content,
                    content_length,
                    None,  # dynasty
                    "古籍",
                    "{}",  # tags
                ]
            )

        if data:
            async with conn.transaction():
                await conn.executemany(
                    """
                    INSERT INTO guji_documents (source_table, source_id, title, content, content_length, dynasty, category, tags)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                    ON CONFLICT (source_table, source_id) DO NOTHING
                    """,
                    data,
                )
            imported += len(data)
            logger.info(f"  {table}: {imported:,}/{total:,}")

        offset += batch_size

    sqlite_conn.close()
    logger.info(f"表 {table} 导入完成: {imported:,} 条")
    return imported


async def main():
    import os

    database_url = os.getenv(
        "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
    )

    if not SOURCE_DB.exists():
        logger.error(f"源数据库不存在: {SOURCE_DB}")
        return

    # 获取所有表
    conn = sqlite3.connect(str(SOURCE_DB))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wx%';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not tables:
        logger.error("没有找到wx开头的表")
        return

    # 统计总数
    conn = sqlite3.connect(str(SOURCE_DB))
    cursor = conn.cursor()
    total = 0
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total += cursor.fetchone()[0]
    conn.close()

    logger.info(f"找到 {len(tables)} 个表，总计 {total:,} 条记录")

    # 连接数据库
    pg_conn = await asyncpg.connect(database_url)

    try:
        await create_guji_tables(pg_conn)

        total_imported = 0
        for i, table in enumerate(tables, 1):
            logger.info(f"[{i}/{len(tables)}] 处理表: {table}")
            try:
                count = await import_table_data(pg_conn, str(SOURCE_DB), table)
                total_imported += count
            except Exception as e:
                logger.error(f"导入表 {table} 失败: {e}")

        # 获取统计
        stats = await pg_conn.fetchrow(
            """
            SELECT
                COUNT(*) as total_documents,
                COUNT(DISTINCT source_table) as total_tables,
                SUM(content_length) as total_content
            FROM guji_documents
        """
        )

        await pg_conn.close()

        logger.info("=" * 50)
        logger.info("古籍数据导入完成!")
        logger.info(f"总计导入: {total_imported:,} 条记录")
        logger.info(f"文档总数: {stats['total_documents']:,}")
        logger.info(f"数据表数: {stats['total_tables']}")
        logger.info(f"总字符数: {stats['total_content']:,}")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"导入失败: {e}")
        await pg_conn.close()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
