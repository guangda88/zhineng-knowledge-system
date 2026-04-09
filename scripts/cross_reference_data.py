#!/usr/bin/env python3
"""
data.db ↔ Sys_books.db 对账脚本

功能：
1. 从 data.db (x_search_nodes, 907K 云端文件索引) 读取文件信息
2. 与 PostgreSQL sys_books (3M 本地磁盘索引) 进行文件名匹配
3. 填充 cloud_path 字段
4. 标记匹配状态 (matched / deduplicated / unmatched)
5. 输出对账报告
"""

import asyncio
import logging
import os
import sqlite3
import time
from collections import defaultdict
from typing import Dict, List, Tuple

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DB_PATH = "data/data.db"
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb",
)
BATCH_SIZE = 5000


def load_cloud_files(db_path: str) -> Dict[str, Dict]:
    """从 data.db 加载云端文件索引

    Returns:
        {normalized_filename: {path, name, size}} 字典
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT parent, name, is_dir, size
        FROM x_search_nodes
        WHERE is_dir = 0
    """
    )

    file_index: Dict[str, List[Dict]] = defaultdict(list)
    total = 0

    for parent, name, is_dir, size in cursor:
        full_path = f"{parent}/{name}"
        normalized = normalize_filename(name)
        if normalized and len(normalized) >= 2:
            file_index[normalized].append(
                {
                    "cloud_path": full_path,
                    "name": name,
                    "size": size or 0,
                }
            )
            total += 1

    conn.close()
    logger.info(f"Loaded {total:,} cloud files, {len(file_index):,} unique normalized names")
    return file_index


def normalize_filename(filename: str) -> str:
    """标准化文件名用于匹配

    - 移除扩展名
    - 小写化
    - 移除多余空格和标点
    - 移除方括号内容
    """
    import re

    name = filename.lower().strip()

    # Remove extension
    for ext in [
        ".pdf",
        ".txt",
        ".doc",
        ".docx",
        ".djvu",
        ".mobi",
        ".epub",
        ".mp3",
        ".wav",
        ".mp4",
        ".avi",
        ".rmvb",
        ".rm",
        ".mkv",
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".tiff",
        ".pdg",
    ]:
        if name.endswith(ext):
            name = name[: -len(ext)]
            break

    # Remove bracketed content like [作者], (年份)
    name = re.sub(r"[\[【\[〈《].*?[\]】\]〉》]", "", name)
    name = re.sub(r"[（(][^）)]*[）)]", "", name)

    # Remove extra whitespace and punctuation
    name = re.sub(r"[\s\-_\.]+", "", name)
    name = name.strip()

    return name


async def cross_reference(file_index: Dict[str, List[Dict]]):
    """执行对账

    策略：
    1. 精确匹配：标准化文件名完全一致
    2. 大小验证：如果两边都有 size，检查是否相近
    3. 模糊匹配：对未匹配的记录使用 LIKE 查询
    """
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=6, command_timeout=600)

    try:
        # Get total unmatched count (use pg_class for fast estimate)
        total_unmatched = (
            await pool.fetchval(
                "SELECT reltuples::bigint FROM pg_class WHERE relname = 'sys_books'"
            )
            or 3024428
        )
        logger.info(f"Total sys_books records (estimate): {total_unmatched:,}")

        # Phase 1: Batch match by normalized filename
        await phase1_exact_match(pool, file_index)

        # Phase 2: Size-based dedup within matched
        await phase2_size_dedup(pool)

        # Phase 3: Path substring match for high-value domains
        await phase3_path_match(pool, file_index)

        # Report
        await generate_report(pool)

    finally:
        await pool.close()


async def phase1_exact_match(pool: asyncpg.Pool, file_index: Dict[str, List[Dict]]):
    """Phase 1: 精确文件名匹配（游标分页，边扫边更新）"""
    logger.info("Phase 1: Exact filename matching...")

    matched = 0
    last_id = 0
    UPDATE_EVERY = 5000

    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, filename, size, path
                FROM sys_books
                WHERE cross_ref_status = 'unmatched' AND id > $1
                ORDER BY id
                LIMIT $2
                """,
                last_id,
                BATCH_SIZE,
            )

        if not rows:
            break

        last_id = rows[-1]["id"]

        batch_updates: List[Tuple] = []
        for row in rows:
            normalized = normalize_filename(row["filename"])
            if normalized in file_index:
                candidates = file_index[normalized]
                best = candidates[0]

                if len(candidates) > 1 and row["size"] > 0:
                    for c in candidates:
                        if c["size"] > 0 and abs(c["size"] - row["size"]) < 1024:
                            best = c
                            break

                batch_updates.append(
                    (
                        best["cloud_path"],
                        row["id"],
                    )
                )

        if batch_updates:
            async with pool.acquire() as conn:
                await conn.executemany(
                    "UPDATE sys_books SET cloud_path = $1, cross_ref_status = 'matched' WHERE id = $2",
                    batch_updates,
                )
            matched += len(batch_updates)

        if matched > 0 and matched % UPDATE_EVERY < BATCH_SIZE:
            logger.info(f"  Scanned to id={last_id:,}, matched so far: {matched:,}")

    logger.info(f"Phase 1 complete: {matched:,} matched")


async def phase2_size_dedup(pool: asyncpg.Pool):
    """Phase 2: 标记同一文件被多源索引的去重"""
    logger.info("Phase 2: Size-based deduplication...")

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE sys_books
            SET cross_ref_status = 'deduplicated'
            WHERE cross_ref_status = 'matched'
              AND id NOT IN (
                SELECT DISTINCT ON (filename, size)
                    id
                FROM sys_books
                WHERE cross_ref_status = 'matched'
                  AND filename IS NOT NULL AND size > 0
                ORDER BY filename, size, id
              )
              AND filename IS NOT NULL AND size > 0
        """
        )
        count = int(result.split()[-1]) if result else 0
        logger.info(f"Phase 2 complete: {count:,} deduplicated")


async def phase3_path_match(pool: asyncpg.Pool, file_index: Dict[str, List[Dict]]):
    """Phase 3: 高价值领域的路径子串匹配"""
    logger.info("Phase 3: Path substring matching for key domains...")

    key_terms = [
        "智能气功",
        "八段锦",
        "五禽戏",
        "六字诀",
        "易筋经",
        "形神庄",
        "捧气贯顶",
        "黄帝内经",
        "伤寒论",
        "论语",
        "道德经",
    ]

    async with pool.acquire() as conn:
        total_matched = 0

        for term in key_terms:
            # Find sys_books with this term in filename but still unmatched
            rows = await conn.fetch(
                """
                SELECT id, filename
                FROM sys_books
                WHERE cross_ref_status = 'unmatched'
                  AND (filename LIKE $1 OR path LIKE $1)
                LIMIT 1000
            """,
                f"%{term}%",
            )

            if not rows:
                continue

            # Find matching cloud files
            term_matches = []
            for norm_name, entries in file_index.items():
                if term.lower() in norm_name:
                    for entry in entries:
                        term_matches.append(entry)

            if not term_matches:
                continue

            # Match by finding best cloud_path for each book
            for row in rows:
                best_path = None
                best_score = 0

                for cloud_entry in term_matches:
                    score = compute_name_similarity(
                        row["filename"].lower(),
                        cloud_entry["name"].lower(),
                    )
                    if score > best_score:
                        best_score = score
                        best_path = cloud_entry["cloud_path"]

                if best_path and best_score > 0.5:
                    await conn.execute(
                        """
                        UPDATE sys_books
                        SET cloud_path = $1, cross_ref_status = 'matched'
                        WHERE id = $2
                        """,
                        best_path,
                        row["id"],
                    )
                    total_matched += 1

        logger.info(f"Phase 3 complete: {total_matched:,} additional matched")


def compute_name_similarity(name1: str, name2: str) -> float:
    """计算两个文件名的相似度 (0-1)"""
    if not name1 or not name2:
        return 0.0

    # Remove common suffixes and extensions
    for s in [".", "_", "-", " "]:
        name1 = name1.replace(s, "")
        name2 = name2.replace(s, "")

    if name1 == name2:
        return 1.0

    # Simple: check if one contains the other
    if name1 in name2 or name2 in name1:
        shorter = min(len(name1), len(name2))
        longer = max(len(name1), len(name2))
        return shorter / longer

    # Character overlap
    set1 = set(name1)
    set2 = set(name2)
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / max(len(set1 | set2), 1)


async def generate_report(pool: asyncpg.Pool):
    """生成对账报告"""
    logger.info("Generating cross-reference report...")

    async with pool.acquire() as conn:
        status_counts = await conn.fetch(
            """
            SELECT cross_ref_status, COUNT(*) as cnt
            FROM sys_books
            GROUP BY cross_ref_status
            ORDER BY cnt DESC
        """
        )

        logger.info("\n=== Cross-Reference Report ===")
        total = 0
        for r in status_counts:
            logger.info(f"  {r['cross_ref_status']}: {r['cnt']:>10,}")
            total += r["cnt"]
        logger.info(f"  {'TOTAL':>14}: {total:>10,}")

        matched_with_cloud = await conn.fetchval(
            "SELECT COUNT(*) FROM sys_books WHERE cloud_path IS NOT NULL"
        )
        logger.info(f"\n  Matched with cloud_path: {matched_with_cloud:,}")

        by_domain = await conn.fetch(
            """
            SELECT domain, cross_ref_status, COUNT(*) as cnt
            FROM sys_books
            WHERE cross_ref_status = 'matched'
            GROUP BY domain, cross_ref_status
            ORDER BY cnt DESC
            LIMIT 10
        """
        )

        if by_domain:
            logger.info("\n  Top matched domains:")
            for r in by_domain:
                logger.info(f"    {r['domain']}: {r['cnt']:>8,}")


async def main():
    start = time.time()
    logger.info("Starting data.db ↔ sys_books cross-reference...")

    file_index = load_cloud_files(DATA_DB_PATH)
    await cross_reference(file_index)

    elapsed = time.time() - start
    logger.info(f"\nCross-reference complete in {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
