#!/usr/bin/env python3
"""
从 zh.wikisource.org 导入武术典籍到 documents 表

覆盖传统武术经典著作

用法:
    python scripts/import_martial_arts_wikisource.py --dry-run
    python scripts/import_martial_arts_wikisource.py

数据来源: zh.wikisource.org
License: 维基文库内容为公共领域
"""

import argparse
import os
import asyncio
import logging
import re

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = os.getenv("DATABASE_URL")
CATEGORY = "武术"
API_BASE = "https://zh.wikisource.org/w/api.php"
UA = "ZhiNengKnowledgeSystem/1.0 (educational use)"

TEXTS = [
    {
        "wiki_title": "太极拳论",
        "display_title": "太極拳論",
        "tags": ["太極拳", "武禹襄", "清代"],
        "subpages": False,
    },
    {
        "wiki_title": "紀效新書",
        "display_title": "紀效新書",
        "tags": ["戚繼光", "明代", "兵器"],
        "subpages": True,
        "subpage_list": [
            "卷首", "卷一", "卷二", "卷三", "卷四", "卷五",
            "卷六", "卷七", "卷八", "卷九", "卷十", "卷十一",
            "卷十二", "卷十三", "卷十四", "卷十五", "卷十六",
            "卷十七", "卷十八",
        ],
    },
    {
        "wiki_title": "劍經",
        "display_title": "劍經",
        "tags": ["俞大猷", "明代", "劍法"],
        "subpages": False,
    },
    {
        "wiki_title": "少林拳術秘訣",
        "display_title": "少林拳術秘訣",
        "tags": ["少林", "民國", "拳法"],
        "subpages": False,
    },
    {
        "wiki_title": "手臂錄",
        "display_title": "手臂錄",
        "tags": ["吳殳", "明代", "槍法"],
        "subpages": False,
    },
    {
        "wiki_title": "練兵實紀",
        "display_title": "練兵實紀",
        "tags": ["戚繼光", "明代", "軍事"],
        "subpages": True,
        "subpage_list": [
            "卷一", "卷二", "卷三", "卷四", "卷五", "卷六",
        ],
    },
]


def clean_wikitext(wikitext: str) -> str:
    text = wikitext
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    text = re.sub(r"\[\[Category:[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[[^|\]]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"__[A-Z]+__", "", text)
    text = re.sub(r"^=+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*=+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"'''", "", text)
    text = re.sub(r"''", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def fetch_wikitext(client: httpx.AsyncClient, title: str, max_retries: int = 3) -> str | None:
    for attempt in range(max_retries):
        try:
            await asyncio.sleep(2.5)
            r = await client.get(
                API_BASE,
                params={
                    "action": "query",
                    "titles": title,
                    "prop": "revisions",
                    "rvprop": "content",
                    "format": "json",
                },
            )
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", "10"))
                logger.warning(f"Rate limited on '{title}', waiting {wait}s")
                await asyncio.sleep(wait)
                continue
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            for pid, page in pages.items():
                if "missing" in page:
                    return None
                revs = page.get("revisions", [])
                if revs:
                    return revs[0]["*"]
        except Exception as e:
            logger.error(f"Failed to fetch '{title}': {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)
    return None


async def import_martial(db_url: str, dry_run: bool):
    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)
    imported = 0

    async with httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers={"User-Agent": UA}
    ) as client:
        for text_info in TEXTS:
            main_title = text_info["display_title"]

            if text_info["subpages"]:
                for subpage in text_info["subpage_list"]:
                    full_title = f"{text_info['wiki_title']}/{subpage}"
                    doc_title = f"{main_title}·{subpage}"

                    async with pool.acquire() as conn:
                        existing = await conn.fetchval(
                            "SELECT 1 FROM documents WHERE title = $1", doc_title
                        )
                    if existing:
                        logger.info(f"  Skip (exists): {doc_title}")
                        imported += 1
                        continue

                    logger.info(f"Fetching {full_title}")
                    wikitext = await fetch_wikitext(client, full_title)
                    if not wikitext:
                        logger.warning(f"  Not found: {full_title}")
                        continue

                    content = clean_wikitext(wikitext)
                    ch_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
                    if ch_chars < 20:
                        logger.warning(f"  Too short ({ch_chars} chars): {subpage}")
                        continue

                    doc_title = f"{main_title}·{subpage}"
                    tags = text_info["tags"] + [subpage]

                    if dry_run:
                        logger.info(f"  {doc_title}: {ch_chars} Chinese chars")
                        imported += 1
                        continue

                    async with pool.acquire() as conn:
                        try:
                            await conn.execute(
                                """
                                INSERT INTO documents (title, content, category, tags)
                                VALUES ($1, $2, $3, $4)
                                ON CONFLICT (title) DO NOTHING
                                """,
                                doc_title, content, CATEGORY, tags,
                            )
                            imported += 1
                            logger.info(f"  Imported: {doc_title} ({ch_chars} chars)")
                        except Exception as e:
                            logger.error(f"  Insert error: {e}")
            else:
                async with pool.acquire() as conn:
                    existing = await conn.fetchval(
                        "SELECT 1 FROM documents WHERE title = $1", main_title
                    )
                if existing:
                    logger.info(f"  Skip (exists): {main_title}")
                    imported += 1
                    continue

                logger.info(f"Fetching {text_info['wiki_title']}")
                wikitext = await fetch_wikitext(client, text_info["wiki_title"])
                if not wikitext:
                    logger.warning(f"  Not found: {text_info['wiki_title']}")
                    continue

                content = clean_wikitext(wikitext)
                ch_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
                if ch_chars < 20:
                    logger.warning(f"  Too short ({ch_chars} chars)")
                    continue

                if dry_run:
                    logger.info(f"  {main_title}: {ch_chars} Chinese chars")
                    imported += 1
                    continue

                async with pool.acquire() as conn:
                    try:
                        await conn.execute(
                            """
                            INSERT INTO documents (title, content, category, tags)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (title) DO NOTHING
                            """,
                            main_title, content, CATEGORY, text_info["tags"],
                        )
                        imported += 1
                        logger.info(f"  Imported: {main_title} ({ch_chars} chars)")
                    except Exception as e:
                        logger.error(f"  Insert error: {e}")

    await pool.close()
    print(f"\n{'Dry run' if dry_run else 'Import'} summary: {imported} documents")


def main():
    parser = argparse.ArgumentParser(description="Import Martial Arts texts from zh.wikisource.org")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(import_martial(args.db_url, args.dry_run))


if __name__ == "__main__":
    main()
