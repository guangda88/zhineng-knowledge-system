#!/usr/bin/env python3
"""
从 CText.org 导入道家核心典籍到 documents 表

获取道家核心文本：道德经、庄子、列子、文子、淮南子等
CText 的文本可以通过公开页面获取，无需 API key

用法:
    python scripts/import_daoist_ctext.py --dry-run    # 预览
    python scripts/import_daoist_ctext.py              # 执行导入

数据来源: https://ctext.org/daoism
License: CText 内容为公开领域古籍文本
"""

import argparse
import asyncio
import logging
import re
import sys
import os
import time

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = os.getenv("DATABASE_URL", os.getenv("DATABASE_URL"))
CATEGORY = "道家"

# Core Daoist texts available on CText
DAOIST_TEXTS = [
    {
        "url": "https://ctext.org/dao-de-jing",
        "title": "道德经",
        "tags": ["道德经", "老子", "先秦"],
    },
    {
        "url": "https://ctext.org/zhuangzi",
        "title": "庄子",
        "tags": ["庄子", "先秦"],
    },
    {
        "url": "https://ctext.org/liezi",
        "title": "列子",
        "tags": ["列子", "先秦"],
    },
    {
        "url": "https://ctext.org/wenzi",
        "title": "文子",
        "tags": ["文子", "先秦"],
    },
    {
        "url": "https://ctext.org/huainanzi",
        "title": "淮南子",
        "tags": ["淮南子", "西汉"],
    },
    {
        "url": "https://ctext.org/guanzi",
        "title": "管子",
        "tags": ["管子", "先秦"],
    },
]


def extract_text_from_html(html: str) -> str:
    """Extract Chinese text from CText HTML page."""
    # CText uses <td class="ctext"> for main text
    # Also look for content in specific div patterns
    texts = []

    # Pattern 1: ctext table cells
    pattern = r'<td[^>]*class="ctext"[^>]*>(.*?)</td>'
    matches = re.findall(pattern, html, re.DOTALL)
    for m in matches:
        clean = re.sub(r"<[^>]+>", "", m).strip()
        if clean and len(clean) > 5:
            texts.append(clean)

    if not texts:
        # Pattern 2: Any Chinese text content in paragraphs
        pattern = r"<p[^>]*>(.*?)</p>"
        matches = re.findall(pattern, html, re.DOTALL)
        for m in matches:
            clean = re.sub(r"<[^>]+>", "", m).strip()
            # Filter for substantial Chinese text
            chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", clean))
            if chinese_chars > 10:
                texts.append(clean)

    return "\n\n".join(texts)


async def fetch_ctext_page(client: httpx.AsyncClient, url: str) -> str:
    """Fetch a CText page and extract text."""
    try:
        r = await client.get(url, follow_redirects=True, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return ""


async def import_daoist_texts(db_url: str, dry_run: bool):
    """Main import logic."""
    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)
    imported = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; ZhiNengBot/1.0)"}
    ) as client:
        for text_info in DAOIST_TEXTS:
            logger.info(f"Fetching {text_info['title']} from {text_info['url']}")

            html = await fetch_ctext_page(client, text_info["url"])
            if not html:
                continue

            content = extract_text_from_html(html)
            if not content or len(content) < 100:
                logger.warning(f"  No substantial text extracted for {text_info['title']}")
                continue

            title = text_info["title"]
            tags = text_info.get("tags", [])

            if dry_run:
                chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
                logger.info(f"  {title}: {len(content)} chars ({chinese_chars} Chinese)")
                continue

            # Insert into documents
            async with pool.acquire() as conn:
                try:
                    await conn.execute(
                        """
                        INSERT INTO documents (title, content, category, tags)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (title) DO NOTHING
                        """,
                        title,
                        content,
                        CATEGORY,
                        tags,
                    )
                    imported += 1
                    logger.info(f"  Imported: {title} ({len(content)} chars)")
                except Exception as e:
                    logger.error(f"  Insert error for {title}: {e}")

    await pool.close()

    if dry_run:
        print("\n=== Dry Run Summary ===")
        print(f"Texts attempted: {len(DAOIST_TEXTS)}")
    else:
        print(f"\n=== Import Summary ===")
        print(f"Texts imported: {imported}/{len(DAOIST_TEXTS)}")


def main():
    parser = argparse.ArgumentParser(description="Import Daoist texts from CText.org")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(import_daoist_texts(args.db_url, args.dry_run))


if __name__ == "__main__":
    main()
