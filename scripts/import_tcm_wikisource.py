#!/usr/bin/env python3
"""
从 zh.wikisource.org 导入中医典籍到 documents 表

覆盖中医核心经典：黄帝内经、伤寒论、金匮要略、难经、千金方、温病条辨

子页面格式经过验证：
- 黃帝內經：按卷分页，如 黃帝內經/素問第一卷
- 傷寒論：整本在一页
- 金匱要略：整本在一页
- 難經：整本在一页
- 備急千金要方：按卷分页，如 備急千金要方/序
- 溫病條辨：按卷分页，如 溫病條辨/卷一

用法:
    python scripts/import_tcm_wikisource.py --dry-run
    python scripts/import_tcm_wikisource.py

数据来源: zh.wikisource.org
License: 维基文库内容为公共领域
"""

import argparse
import asyncio
import logging
import re

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = os.getenv("DATABASE_URL")
CATEGORY = "中医"
API_BASE = "https://zh.wikisource.org/w/api.php"
UA = "ZhiNengKnowledgeSystem/1.0 (educational use)"

TEXTS = [
    {
        "wiki_title": "黃帝內經",
        "display_title": "黃帝內經",
        "tags": ["黃帝內經", "中醫經典", "先秦"],
        "subpages": True,
        "subpage_list": [
            "素問第一卷", "素問第二卷", "素問第三卷",
            "素問第四卷", "素問第五卷", "素問第六卷",
            "素問第七卷", "素問第八卷", "素問第九卷",
            "素問第十卷", "素問第十一卷", "素問第十二卷",
            "素問第十三卷", "素問第十四卷", "素問第十五卷",
            "素問第十六卷", "素問第十七卷", "素問第十八卷",
            "素問第十九卷", "素問第二十卷", "素問第二十一卷",
            "素問第二十二卷", "素問第二十三卷", "素問第二十四卷",
            "靈樞第一卷", "靈樞第二卷", "靈樞第三卷",
            "靈樞第四卷", "靈樞第五卷", "靈樞第六卷",
            "靈樞第七卷", "靈樞第八卷", "靈樞第九卷",
            "靈樞第十卷", "靈樞第十一卷", "靈樞第十二卷",
        ],
    },
    {
        "wiki_title": "傷寒論",
        "display_title": "傷寒論",
        "tags": ["傷寒論", "張仲景", "東漢"],
        "subpages": False,
    },
    {
        "wiki_title": "金匱要略",
        "display_title": "金匱要略",
        "tags": ["金匱要略", "張仲景", "東漢"],
        "subpages": False,
    },
    {
        "wiki_title": "難經",
        "display_title": "難經",
        "tags": ["難經", "秦越人", "中醫經典"],
        "subpages": False,
    },
    {
        "wiki_title": "備急千金要方",
        "display_title": "備急千金要方",
        "tags": ["千金方", "孫思邈", "唐代"],
        "subpages": True,
        "subpage_list": [
            "序", "第一", "第二", "第三", "第四", "第五上", "第五下",
            "第六", "第七", "第八", "第九", "第十",
            "第十一", "第十二", "第十三", "第十四", "第十五", "第十六",
            "第十七", "第十八", "第十九", "第二十", "第二十一", "第二十二",
            "第二十三", "第二十四", "第二十五", "第二十六", "第二十七",
            "第二十八", "第二十九", "第三十",
        ],
    },
    {
        "wiki_title": "溫病條辨",
        "display_title": "溫病條辨",
        "tags": ["溫病", "吳鞠通", "清代"],
        "subpages": True,
        "subpage_list": ["自序", "原病篇", "卷一", "卷二", "卷三"],
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
                    "redirects": "true",
                },
            )
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", "10"))
                logger.warning(f"Rate limited on '{title}', waiting {wait}s")
                await asyncio.sleep(wait)
                continue
            if r.status_code != 200:
                logger.error(f"HTTP {r.status_code} on '{title}'")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
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


async def import_tcm(db_url: str, dry_run: bool):
    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)
    imported = 0
    failed = 0

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
                        failed += 1
                        continue

                    content = clean_wikitext(wikitext)
                    ch_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
                    if ch_chars < 20:
                        logger.warning(f"  Too short ({ch_chars} chars): {subpage}")
                        failed += 1
                        continue

                    if dry_run:
                        logger.info(f"  [DRY RUN] {doc_title}: {ch_chars} Chinese chars")
                        imported += 1
                        continue

                    tags = text_info["tags"] + [subpage]
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
                            failed += 1
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
                    failed += 1
                    continue

                content = clean_wikitext(wikitext)
                ch_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
                if ch_chars < 20:
                    logger.warning(f"  Too short ({ch_chars} chars)")
                    failed += 1
                    continue

                if dry_run:
                    logger.info(f"  [DRY RUN] {main_title}: {ch_chars} Chinese chars")
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
                        failed += 1

    await pool.close()
    print(f"\n{'Dry run' if dry_run else 'Import'} summary: {imported} imported, {failed} failed")


def main():
    parser = argparse.ArgumentParser(description="Import TCM texts from zh.wikisource.org")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(import_tcm(args.db_url, args.dry_run))


if __name__ == "__main__":
    main()
