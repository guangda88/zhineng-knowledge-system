#!/usr/bin/env python3
"""
Sys_books.db → PostgreSQL sys_books 表导入脚本
从 SQLite 数据库导入 302 万条书目记录到 PostgreSQL
"""

import asyncio
import logging
import os
import sqlite3
import time
from datetime import datetime
from typing import List, Optional, Tuple

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

SQLITE_PATH = "data/external/Sys_books.db"
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb",
)
BATCH_SIZE = 5000


async def create_table(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sys_books (
            id SERIAL PRIMARY KEY,
            source TEXT NOT NULL,
            path TEXT NOT NULL,
            filename TEXT NOT NULL,
            category TEXT,
            author TEXT,
            year TEXT,
            book_number TEXT,
            file_type TEXT,
            size BIGINT DEFAULT 0,
            extension TEXT,
            created_date TIMESTAMPTZ,
            publisher TEXT,
            domain TEXT,
            subcategory TEXT
        )
    """
    )

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_sys_books_domain ON sys_books(domain)",
        "CREATE INDEX IF NOT EXISTS idx_sys_books_category ON sys_books(category)",
        "CREATE INDEX IF NOT EXISTS idx_sys_books_extension ON sys_books(extension)",
        "CREATE INDEX IF NOT EXISTS idx_sys_books_source ON sys_books(source)",
        "CREATE INDEX IF NOT EXISTS idx_sys_books_file_type ON sys_books(file_type)",
    ]
    for idx_sql in indexes:
        try:
            await conn.execute(idx_sql)
        except Exception as e:
            logger.warning(f"Index creation skipped: {e}")

    logger.info("Table sys_books and basic indexes ready")


def iter_sqlite_batches(batch_size: int):
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT source, path, filename, category, author, year, "
        "book_number, file_type, size, extension, created_date, publisher "
        "FROM books"
    )

    batch: List[Tuple] = []
    total = 0
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break

        for row in rows:
            source = row[0] or ""
            path = row[1] or ""
            filename = row[2] or ""
            category = row[3] or None
            author = row[4] or None
            year_val = row[5] or None
            book_number = row[6] or None
            file_type = row[7] or "file"
            size = row[8] or 0
            extension = row[9] or None
            created_date = row[10] or None
            if isinstance(created_date, str):
                try:
                    created_date = datetime.strptime(created_date, "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    created_date = None
            publisher = row[11] or None

            domain, subcategory = extract_domain(path, category, filename)

            batch.append(
                (
                    source,
                    path,
                    filename,
                    category,
                    author,
                    year_val,
                    book_number,
                    file_type,
                    size,
                    extension,
                    created_date,
                    publisher,
                    domain,
                    subcategory,
                )
            )
            total += 1

        yield batch
        batch = []

    conn.close()
    logger.info(f"SQLite iteration complete: {total:,} rows read")


def extract_domain(path: str, category: str, filename: str) -> Tuple[Optional[str], Optional[str]]:
    p = (path or "").lower()
    c = (category or "").lower()

    if any(k in p or k in c for k in ["znqg", "智能气功", "智能功"]):
        return "智能气功", _qigong_sub(p, c)
    if any(
        k in p or k in c for k in ["气功", "八段锦", "五禽戏", "六字诀", "易筋经", "太极拳", "太极"]
    ):
        if "智能" in c or "znqg" in p:
            return "智能气功", _qigong_sub(p, c)
        return "气功", "其他气功"
    if any(k in p or k in c for k in ["中医", "中药", "针灸", "经络", "伤寒", "本草", "黄帝内经"]):
        return "中医", _tcm_sub(p, c)
    if any(k in p or k in c for k in ["儒家", "论语", "孟子", "大学", "中庸", "四书", "十三经"]):
        return "儒家", None
    if any(k in p or k in c for k in ["道家", "老子", "庄子", "道德经", "道藏"]):
        return "道家", None
    if any(k in p or k in c for k in ["佛家", "佛经", "大藏经", "禅"]):
        return "佛家", None
    if any(k in c for k in ["古籍"]):
        return "古籍", _guji_sub(p, c)
    if any(k in c for k in ["国学大师"]):
        return "国学大师", None
    if any(k in c for k in ["四库全书"]):
        return "四库全书", _siku_sub(p, c)
    if any(k in c for k in ["哲学"]):
        return "哲学", None
    if any(k in c for k in ["文学"]):
        return "文学", None
    if any(k in c for k in ["历史", "历史学"]):
        return "历史", None
    if any(k in p or k in c for k in ["传统文化"]):
        return "传统文化", None

    return "其他", None


def _qigong_sub(p: str, c: str) -> Optional[str]:
    if any(k in c for k in ["音频", "mp3", "录音", "讲课"]):
        return "音频"
    if any(k in c for k in ["视频", "mp4", "讲座"]):
        return "视频"
    if any(k in c for k in ["文字", "图文", "pdf", "txt"]):
        return "文字"
    if any(k in c for k in ["教材", "大专", "精义", "概论"]):
        return "教材"
    if any(k in c for k in ["科研", "实验"]):
        return "科研"
    return "综合"


def _tcm_sub(p: str, c: str) -> Optional[str]:
    if "黄帝内经" in p or "黄帝内经" in c:
        return "黄帝内经"
    if "伤寒" in p or "伤寒" in c:
        return "伤寒论"
    if "本草" in p or "本草" in c:
        return "本草"
    if "针灸" in p or "针灸" in c:
        return "针灸"
    if "经络" in p or "经络" in c:
        return "经络"
    return None


def _guji_sub(p: str, c: str) -> Optional[str]:
    if "经部" in p:
        return "经部"
    if "史部" in p:
        return "史部"
    if "子部" in p:
        return "子部"
    if "集部" in p:
        return "集部"
    return None


def _siku_sub(p: str, c: str) -> Optional[str]:
    if "经部" in p:
        return "经部"
    if "史部" in p:
        return "史部"
    if "子部" in p:
        return "子部"
    if "集部" in p:
        return "集部"
    return None


async def import_batch(conn: asyncpg.Connection, batch: List[Tuple]) -> int:
    result = await conn.executemany(
        """
        INSERT INTO sys_books (
            source, path, filename, category, author, year,
            book_number, file_type, size, extension, created_date,
            publisher, domain, subcategory
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::timestamptz, $12, $13, $14)
        """,
        batch,
    )
    return len(batch)


async def main():
    start = time.time()
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=4, command_timeout=3600)

    async with pool.acquire() as conn:
        await create_table(conn)

        # Drop ALL non-primary indexes for faster import
        indexes = await conn.fetch(
            "SELECT indexname FROM pg_indexes WHERE tablename='sys_books' "
            "AND indexname != 'sys_books_pkey'"
        )
        for idx_row in indexes:
            idx_name = idx_row["indexname"]
            logger.info(f"Dropping index {idx_name} for faster import...")
            await conn.execute(f"DROP INDEX IF EXISTS {idx_name}")

        # Truncate if re-running
        existing = await conn.fetchval("SELECT COUNT(*) FROM sys_books")
        if existing > 0:
            logger.info(f"Table has {existing:,} existing rows, truncating...")
            await conn.execute("TRUNCATE sys_books RESTART IDENTITY")

    total_imported = 0
    batch_num = 0

    for batch in iter_sqlite_batches(BATCH_SIZE):
        async with pool.acquire() as conn:
            count = await import_batch(conn, batch)
            total_imported += count
            batch_num += 1

            if batch_num % 20 == 0:
                elapsed = time.time() - start
                rate = total_imported / elapsed
                logger.info(
                    f"  Progress: {total_imported:>10,} rows | "
                    f"{rate:>8,.0f} rows/s | "
                    f"{elapsed:.1f}s elapsed"
                )

    elapsed = time.time() - start
    logger.info(
        f"\nImport complete: {total_imported:,} rows in {elapsed:.1f}s ({total_imported/elapsed:,.0f} rows/s)"
    )

    # Create ALL indexes after all data is loaded (much faster)
    logger.info("Creating indexes on sys_books...")
    async with pool.acquire() as conn:
        all_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_sys_books_domain ON sys_books(domain)",
            "CREATE INDEX IF NOT EXISTS idx_sys_books_category ON sys_books(category)",
            "CREATE INDEX IF NOT EXISTS idx_sys_books_extension ON sys_books(extension)",
            "CREATE INDEX IF NOT EXISTS idx_sys_books_source ON sys_books(source)",
            "CREATE INDEX IF NOT EXISTS idx_sys_books_file_type ON sys_books(file_type)",
            "CREATE INDEX IF NOT EXISTS idx_sys_books_filename_trgm ON sys_books USING gin (filename gin_trgm_ops)",
            "CREATE INDEX IF NOT EXISTS idx_sys_books_path_trgm ON sys_books USING gin (path gin_trgm_ops)",
        ]
        for idx_sql in all_indexes:
            try:
                t0 = time.time()
                await conn.execute(idx_sql)
                dt = time.time() - t0
                idx_name = idx_sql.split("ON sys_books")[0].strip().split()[-1]
                logger.info(f"  Created {idx_name} in {dt:.1f}s")
            except Exception as e:
                logger.warning(f"Index creation failed: {e}")

    # Verify
    async with pool.acquire() as conn:
        pg_count = await conn.fetchval("SELECT COUNT(*) FROM sys_books")
        logger.info(f"PostgreSQL count: {pg_count:,}")

        # Domain distribution
        rows = await conn.fetch(
            "SELECT domain, COUNT(*) as cnt FROM sys_books GROUP BY domain ORDER BY cnt DESC"
        )
        logger.info("\n=== Domain distribution ===")
        for r in rows:
            logger.info(f"  {r['domain'] or '(null)'}: {r['cnt']:>10,}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
