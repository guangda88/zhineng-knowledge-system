#!/usr/bin/env python3
"""
将 guoxue_content 中佛家/道家相关章节导入 documents 表

策略:
1. 从 guoxue_books 按关键词匹配佛家/道家书籍
2. 提取对应的 guoxue_content 章节
3. 按 content_count 阈值分割超长文本（每块 ≤ 50000 字）
4. 插入 documents 表，category='佛家' 或 '道家'

用法:
    python scripts/import_fodao_from_guoxue.py --dry-run    # 仅预览
    python scripts/import_fodao_from_guoxue.py              # 执行导入
    python scripts/import_fodao_from_guoxue.py --chunk-size 30000  # 自定义分块大小
"""

import argparse
import asyncio
import logging
import re
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = os.getenv("DATABASE_URL")
MAX_CHUNK_SIZE = 30000

BUDDHIST_KEYWORDS = [
    "佛", "禅", "般若", "阿含", "法华", "华严", "涅槃", "净土", "维摩",
    "楞严", "金刚经", "心经", "地藏", "弘明", "僧", "比丘", "菩萨",
    "三藏", "大藏", "经律", "法苑", "高僧", "传灯", "五灯", "公案",
    "坛经", "百丈", "沩山", "临济", "曹洞", "云门", "法眼", "律藏",
    "论藏", "经藏", "佛国", "禅师语录", "赞佛",
]

DAOIST_KEYWORDS = [
    "老子", "庄子", "道德经", "列子", "文子", "抱朴", "道藏", "真经",
    "太上", "黄庭", "周易参同", "悟真", "内丹", "神仙", "灵宝",
    "太平经", "道枢", "云笈", "阴符", "淮南", "关尹", "老君",
]


def classify_title(title: str | None) -> str | None:
    """Classify a book title as 佛家/道家 or None."""
    if not title:
        return None
    for kw in BUDDHIST_KEYWORDS:
        if kw in title:
            return "佛家"
    for kw in DAOIST_KEYWORDS:
        if kw in title:
            return "道家"
    return None


async def find_fodao_books(conn) -> list[dict]:
    """Find Buddhist/Daoist books from guoxue_books."""
    rows = await conn.fetch("SELECT book_id, title, content_count, total_chars FROM guoxue_books")
    books = []
    for r in rows:
        category = classify_title(r["title"])
        if category:
            books.append({
                "book_id": r["book_id"],
                "title": r["title"],
                "content_count": r["content_count"],
                "total_chars": r["total_chars"],
                "category": category,
            })
    return books


async def import_from_guoxue(db_url: str, chunk_size: int, dry_run: bool):
    """Main import logic."""
    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=4)
    async with pool.acquire() as conn:
        books = await find_fodao_books(conn)

        if not books:
            logger.error("No 佛家/道家 books found in guoxue_books")
            await pool.close()
            return

        buddhist_books = [b for b in books if b["category"] == "佛家"]
        daoist_books = [b for b in books if b["category"] == "道家"]

        logger.info(f"Found {len(buddhist_books)} 佛家 books, {len(daoist_books)} 道家 books")

        total_chapters = 0
        total_docs = 0
        total_chars = 0

        for book in books:
            chapters = await conn.fetch(
                "SELECT id, book_id, chapter_id, body, body_length FROM guoxue_content WHERE book_id = $1 ORDER BY chapter_id",
                book["book_id"],
            )

            book_chars = sum(c["body_length"] for c in chapters if c["body"])
            total_chapters += len(chapters)

            if dry_run:
                logger.info(
                    f"  [{book['category']}] {book['title']}: {len(chapters)} chapters, "
                    f"{book_chars:,} chars"
                )
                total_chars += book_chars
                continue

            # Merge and chunk chapters into documents
            chunks = chunk_chapters(book, chapters, chunk_size)
            total_docs += len(chunks)
            total_chars += sum(len(c["content"]) for c in chunks)

            # Insert chunks
            for i in range(0, len(chunks), 50):
                batch = chunks[i : i + 50]
                await _insert_batch(conn, batch)

            logger.info(
                f"  [{book['category']}] {book['title']}: {len(chapters)} chapters → {len(chunks)} docs"
            )

    await pool.close()

    print(f"\n{'=== Dry Run Summary ===' if dry_run else '=== Import Summary ==='}")
    print(f"Books: {len(books)} ({len(buddhist_books)} 佛家, {len(daoist_books)} 道家)")
    print(f"Chapters: {total_chapters}")
    if dry_run:
        print(f"Estimated docs: ~{total_chapters} (depends on chunking)")
    else:
        print(f"Docs imported: {total_docs}")
    print(f"Total chars: {total_chars:,}")


def chunk_chapters(book: dict, chapters: list, max_size: int) -> list[dict]:
    """Split chapters into chunks respecting max_size."""
    docs = []
    current_parts = []
    current_len = 0

    for ch in chapters:
        body = ch["body"] or ""
        if not body.strip():
            continue

        if current_len + len(body) > max_size and current_parts:
            # Flush current chunk
            content = "\n\n".join(current_parts)
            docs.append({
                "title": f"{book['title']} (卷{len(docs) + 1})",
                "content": content,
                "category": book["category"],
                "tags": ["guoxue_content", f"book_{book['book_id']}"],
            })
            current_parts = []
            current_len = 0

        current_parts.append(body)
        current_len += len(body)

    if current_parts:
        content = "\n\n".join(current_parts)
        docs.append({
            "title": f"{book['title']} (卷{len(docs) + 1})",
            "content": content,
            "category": book["category"],
            "tags": ["guoxue_content", f"book_{book['book_id']}"],
        })

    return docs


async def _insert_batch(conn, batch: list[dict]):
    """Insert batch of documents."""
    for d in batch:
        try:
            await conn.execute(
                "INSERT INTO documents (title, content, category, tags) VALUES ($1,$2,$3,$4) ON CONFLICT (title) DO NOTHING",
                d["title"],
                d["content"],
                d["category"],
                d["tags"],
            )
        except Exception as e:
            logger.error(f"  Row error: {d['title'][:60]}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Import 佛家/道家 from guoxue_content to documents")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    parser.add_argument("--chunk-size", type=int, default=MAX_CHUNK_SIZE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(import_from_guoxue(args.db_url, args.chunk_size, args.dry_run))


if __name__ == "__main__":
    main()
