#!/usr/bin/env python3
"""古籍数据安全导入脚本 - 使用导入管理器防止并发问题"""

import asyncio
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from backend.services.import_manager import ImportManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# 数据源路径
SOURCE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"


async def import_table_batch(
    conn: asyncpg.Connection,
    source_db: str,
    table: str,
    batch_size: int = 2000
) -> int:
    """
    导入单个表的数据（使用小事务批量提交）

    关键改进:
    - 每批独立事务，避免长事务持有锁
    - 使用 ON CONFLICT DO NOTHING 避免锁冲突
    """
    sqlite_conn = sqlite3.connect(source_db)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    # 获取表结构和总数
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [col[1] for col in cursor.fetchall()]

    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    total = cursor.fetchone()[0]

    if total == 0:
        sqlite_conn.close()
        return 0

    logger.info(f"导入表 {table}: {total:,} 条记录")

    imported = 0
    offset = 0

    while offset < total:
        # 分批读取数据
        cursor.execute(f"SELECT * FROM {table} LIMIT {batch_size} OFFSET {offset}")
        rows = cursor.fetchall()

        if not rows:
            break

        # 准备数据
        batch_data = []
        for row in rows:
            row_id = row['id']
            content = None

            # 查找内容列
            for col in ('body', 'd', 'content'):
                if col in row.keys() and row[col]:
                    content = row[col]
                    break

            if not content or len(str(content)) < 10:
                continue

            batch_data.append((table, row_id, str(content), len(str(content))))

        # 使用独立小事务插入
        if batch_data:
            try:
                async with conn.transaction():
                    await conn.executemany(
                        """
                        INSERT INTO guji_documents (source_table, source_id, content, content_length)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (source_table, source_id) DO NOTHING
                        """,
                        batch_data
                    )
                imported += len(batch_data)

                # 每批输出进度
                if imported % 10000 == 0:
                    logger.info(f"  {table}: {imported:,}/{total:,}")

            except Exception as e:
                logger.error(f"  批量插入失败: {e}")
                # 继续下一批

        offset += batch_size

    sqlite_conn.close()
    return imported


async def main():
    """主函数 - 使用导入管理器"""

    # 使用导入管理器，自动处理锁和资源
    async with ImportManager("guji_import") as mgr:
        conn = mgr.conn

        # 1. 创建表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS guji_documents (
                id SERIAL PRIMARY KEY,
                source_table VARCHAR(50) NOT NULL,
                source_id INTEGER NOT NULL,
                content TEXT,
                content_length INTEGER,
                category VARCHAR(100) DEFAULT '古籍',
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(source_table, source_id)
            );
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_guji_source
            ON guji_documents(source_table, source_id);
        """)

        # 2. 获取源数据库表列表
        sqlite_conn = sqlite3.connect(str(SOURCE_DB))
        cursor = sqlite_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wx%';")
        tables = [row[0] for row in cursor.fetchall()]
        sqlite_conn.close()

        # 按记录数排序（大表优先）
        table_counts = []
        for table in tables:
            sqlite_conn = sqlite3.connect(str(SOURCE_DB))
            cursor = sqlite_conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            sqlite_conn.close()
            if count > 0:
                table_counts.append((table, count))

        table_counts.sort(key=lambda x: -x[1])

        logger.info(f"找到 {len(table_counts)} 个非空表，总计 {sum(c for _, c in table_counts):,} 条记录")

        # 3. 限制导入数量（避免过长时间）
        MAX_TABLES = 20  # 只导入前20个最大的表
        total_imported = 0

        for i, (table, count) in enumerate(table_counts[:MAX_TABLES], 1):
            logger.info(f"[{i}/{MAX_TABLES}] 开始处理 {table}")

            try:
                imported = await import_table_batch(
                    conn,
                    str(SOURCE_DB),
                    table,
                    batch_size=2000
                )
                total_imported += imported

                # 检查当前总数
                current_total = await conn.fetchval("SELECT COUNT(*) FROM guji_documents")
                logger.info(f"  数据库当前总计: {current_total:,}")

            except Exception as e:
                logger.error(f"导入表 {table} 失败: {e}")
                continue

        # 4. 输出最终统计
        final_stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total_documents,
                COUNT(DISTINCT source_table) as total_tables,
                SUM(content_length) as total_content
            FROM guji_documents
        """)

        logger.info("=" * 50)
        logger.info("古籍数据导入完成!")
        logger.info(f"本次导入: {total_imported:,} 条")
        logger.info(f"数据库总计: {final_stats['total_documents']:,} 条")
        logger.info(f"数据表数: {final_stats['total_tables']}")
        logger.info(f"总字符数: {final_stats['total_content']:,}")
        logger.info("=" * 50)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        if "已在运行" in str(e) or "锁" in str(e):
            logger.error(f"导入失败: {e}")
            logger.error("如需强制解锁，运行: python backend/services/import_manager.py guji_import --force-unlock")
        else:
            logger.error(f"导入失败: {e}")
        sys.exit(1)
