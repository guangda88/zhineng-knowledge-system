#!/usr/bin/env python3
"""古籍数据导入脚本

从 lingzhi_ubuntu/database/guoxue.db 导入约26万条古籍数据到主数据库。

数据来源:
- guoxue.db: 约26万条古籍文献数据

使用方法:
    python scripts/import_guji_data.py
"""

import asyncio
import logging
import sqlite3
import sys
from pathlib import Path
from typing import List, Tuple

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from tqdm import tqdm

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# 源数据库路径
SOURCE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"

# 批量处理大小
BATCH_SIZE = 1000


def get_source_tables(source_db: str) -> List[str]:
    """获取源数据库中所有以wx开头的表"""
    conn = sqlite3.connect(source_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wx%';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return sorted(tables)


def count_total_records(source_db: str, tables: List[str]) -> int:
    """统计总记录数"""
    conn = sqlite3.connect(source_db)
    cursor = conn.cursor()
    total = 0
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        total += count
    conn.close()
    return total


def get_table_data(source_db: str, table: str, offset: int = 0, limit: int = None) -> List[Tuple]:
    """获取表数据"""
    conn = sqlite3.connect(source_db)
    cursor = conn.cursor()
    query = f"SELECT * FROM {table}"
    if limit:
        query += f" LIMIT {limit} OFFSET {offset}"
    cursor.execute(query)
    data = cursor.fetchall()
    conn.close()
    return data


def get_table_structure(source_db: str, table: str) -> List[Tuple]:
    """获取表结构"""
    conn = sqlite3.connect(source_db)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table});")
    structure = cursor.fetchall()
    conn.close()
    return structure


async def create_guji_tables(conn: asyncpg.Connection) -> None:
    """创建古籍数据表"""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS guji_documents (
            id SERIAL PRIMARY KEY,
            source_table VARCHAR(50) NOT NULL,
            source_id INTEGER NOT NULL,
            title TEXT,
            author TEXT,
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
        CREATE INDEX IF NOT EXISTS idx_guji_tags ON guji_documents USING gin(tags);
    """
    )

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS guji_import_log (
            id SERIAL PRIMARY KEY,
            source_table VARCHAR(50) NOT NULL,
            records_imported INTEGER DEFAULT 0,
            import_time TIMESTAMP DEFAULT NOW(),
            status VARCHAR(20) DEFAULT 'pending'
        );
    """
    )

    logger.info("古籍数据表创建完成")


async def import_table_data(
    conn: asyncpg.Connection, source_db: str, table: str, batch_size: int = BATCH_SIZE
) -> int:
    """导入单个表的数据"""
    structure = get_table_structure(source_db, table)
    columns = [col[1] for col in structure]

    # 获取总记录数
    sqlite_conn = sqlite3.connect(source_db)
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    total = cursor.fetchone()[0]
    sqlite_conn.close()

    logger.info(f"开始导入表 {table}: {total} 条记录")

    imported = 0
    offset = 0

    with tqdm(total=total, desc=f"导入 {table}") as pbar:
        while offset < total:
            # 获取数据
            data = get_table_data(source_db, table, offset, batch_size)
            if not data:
                break

            # 准备插入数据
            insert_data = []
            for row in data:
                # 解析数据
                row_id = row[0] if len(row) > 0 else None
                title = None
                author = None
                content = None

                # 根据列结构解析
                if len(columns) >= 3:
                    if "body" in columns:
                        body_idx = columns.index("body")
                        content = row[body_idx] if body_idx < len(row) else None
                    elif "d" in columns:
                        body_idx = columns.index("d")
                        content = row[body_idx] if body_idx < len(row) else None

                    if "title" in columns or "a" in columns:
                        title_idx = columns.index("a") if "a" in columns else 0
                        title = row[title_idx] if title_idx < len(row) else None

                    if "author" in columns or "b" in columns:
                        author_idx = columns.index("b") if "b" in columns else 1
                        author = row[author_idx] if author_idx < len(row) else None

                # 计算内容长度
                content_length = len(content) if content else 0

                # 提取朝代（从标题或内容中）
                dynasty = None
                if title:
                    for d in ["唐", "宋", "元", "明", "清", "汉", "秦", "周", "商"]:
                        if d in title:
                            dynasty = d
                            break

                insert_data.append(
                    (
                        table,  # source_table
                        row_id,  # source_id
                        title,  # title
                        author,  # author
                        content,  # content
                        content_length,  # content_length
                        dynasty,  # dynasty
                        "古籍",  # category
                    )
                )

            # 批量插入
            if insert_data:
                await conn.executemany(
                    """
                    INSERT INTO guji_documents (source_table, source_id, title, author, content, content_length, dynasty, category)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (source_table, source_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        author = EXCLUDED.author,
                        content = EXCLUDED.content,
                        content_length = EXCLUDED.content_length,
                        dynasty = EXCLUDED.dynasty
                    """,
                    insert_data,
                )
                imported += len(insert_data)
                pbar.update(len(insert_data))

            offset += batch_size

    # 记录导入日志
    await conn.execute(
        """
        INSERT INTO guji_import_log (source_table, records_imported, status)
        VALUES ($1, $2, 'completed')
        """,
        (table, imported),
    )

    logger.info(f"表 {table} 导入完成: {imported} 条记录")
    return imported


async def import_all_guji_data(database_url: str) -> dict:
    """导入所有古籍数据"""
    # 检查源数据库
    if not SOURCE_DB.exists():
        logger.error(f"源数据库不存在: {SOURCE_DB}")
        return {"status": "error", "message": "源数据库不存在"}

    # 获取所有表
    tables = get_source_tables(str(SOURCE_DB))
    if not tables:
        logger.error("源数据库中没有找到wx开头的表")
        return {"status": "error", "message": "没有找到数据表"}

    total_records = count_total_records(str(SOURCE_DB), tables)
    logger.info(f"找到 {len(tables)} 个表，总计 {total_records} 条记录")

    # 连接数据库
    conn = await asyncpg.connect(database_url)

    try:
        # 创建表
        await create_guji_tables(conn)

        # 导入数据
        total_imported = 0
        results = {}

        for table in tables:
            try:
                count = await import_table_data(conn, str(SOURCE_DB), table)
                results[table] = count
                total_imported += count
            except Exception as e:
                logger.error(f"导入表 {table} 失败: {e}")
                results[table] = 0

        # 获取导入后的统计
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total_documents,
                COUNT(DISTINCT source_table) as total_tables,
                SUM(content_length) as total_content,
                COUNT(DISTINCT dynasty) as distinct_dynasties
            FROM guji_documents
        """
        )

        await conn.close()

        return {
            "status": "success",
            "tables": results,
            "total_imported": total_imported,
            "stats": {
                "total_documents": stats["total_documents"],
                "total_tables": stats["total_tables"],
                "total_content_chars": stats["total_content"],
                "dynasties": stats["distinct_dynasties"],
            },
        }

    except Exception as e:
        logger.error(f"导入失败: {e}")
        await conn.close()
        return {"status": "error", "message": str(e)}


async def main():
    """主函数"""
    import os

    # 获取数据库URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        database_url = "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"

    logger.info("开始导入古籍数据...")
    logger.info(f"源数据库: {SOURCE_DB}")

    result = await import_all_guji_data(database_url)

    if result["status"] == "success":
        logger.info("=" * 50)
        logger.info("古籍数据导入完成!")
        logger.info(f"总计导入: {result['total_imported']:,} 条记录")
        if "stats" in result:
            logger.info(f"文档总数: {result['stats']['total_documents']:,}")
            logger.info(f"数据表数: {result['stats']['total_tables']}")
            logger.info(f"总字符数: {result['stats']['total_content_chars']:,}")
            logger.info(f"朝代数: {result['stats']['dynasties']}")
        logger.info("=" * 50)
    else:
        logger.error(f"导入失败: {result.get('message')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
