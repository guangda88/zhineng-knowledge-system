#!/usr/bin/env python3
"""
从 zh.wikisource.org 导入新一批经典到 documents 表

覆盖：
- 儒家：孟子、春秋公羊传、春秋穀梁传、爾雅
- 道家：道德經
- 中医：針灸甲乙經、脈經、中藏經、瀕湖脈學

用法:
    python scripts/import_classics_batch2.py --dry-run
    python scripts/import_classics_batch2.py
"""

import argparse
import asyncio
import logging
import os
import re

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = os.getenv("DATABASE_URL")
API_BASE = "https://zh.wikisource.org/w/api.php"
UA = "ZhiNengKnowledgeSystem/1.0 (educational use)"

MENCIUS_SUBPAGES = [
    "梁惠王上", "梁惠王下", "公孫丑上", "公孫丑下",
    "滕文公上", "滕文公下", "離婁上", "離婁下",
    "萬章上", "萬章下", "告子上", "告子下",
    "盡心上", "盡心下",
]

GONGYANG_SUBPAGES = [
    "隱公", "桓公", "莊公", "閔公", "僖公",
    "文公", "宣公", "成公", "襄公", "昭公",
    "定公", "哀公",
]

GULIANG_SUBPAGES = [
    "隱公", "桓公", "莊公", "閔公", "僖公",
    "文公", "宣公", "成公", "襄公", "昭公",
    "定公", "哀公", "序",
]

TEXTS = [
    {
        "category": "儒家",
        "wiki_title": "孟子",
        "display_title": "孟子",
        "tags": ["孟子", "儒家經典", "四書", "先秦"],
        "subpages": True,
        "subpage_list": MENCIUS_SUBPAGES,
    },
    {
        "category": "儒家",
        "wiki_title": "春秋公羊傳",
        "display_title": "春秋公羊傳",
        "tags": ["春秋公羊傳", "儒家經典", "十三經", "先秦"],
        "subpages": True,
        "subpage_list": GONGYANG_SUBPAGES,
    },
    {
        "category": "儒家",
        "wiki_title": "春秋穀梁傳",
        "display_title": "春秋穀梁傳",
        "tags": ["春秋穀梁傳", "儒家經典", "十三經", "先秦"],
        "subpages": True,
        "subpage_list": GULIANG_SUBPAGES,
    },
    {
        "category": "儒家",
        "wiki_title": "爾雅",
        "display_title": "爾雅",
        "tags": ["爾雅", "儒家經典", "十三經", "先秦"],
        "subpages": False,
    },
    {
        "category": "道家",
        "wiki_title": "老子",
        "display_title": "道德經",
        "tags": ["道德經", "老子", "道家經典", "先秦"],
        "subpages": False,
    },
    {
        "category": "道家",
        "wiki_title": "淮南子",
        "display_title": "淮南子",
        "tags": ["淮南子", "道家", "西漢"],
        "subpages": True,
        "subpage_list": [
            "原道訓", "俶真訓", "天文訓", "墬形訓", "時則訓",
            "覽冥訓", "精神訓", "本經訓", "主術訓", "繆稱訓",
            "齊俗訓", "道應訓", "氾論訓", "詮言訓", "兵略訓",
            "說山訓", "說林訓", "人間訓", "修務訓", "泰族訓",
            "要略",
        ],
    },
    {
        "category": "中医",
        "wiki_title": "針灸甲乙經",
        "display_title": "針灸甲乙經",
        "tags": ["針灸甲乙經", "皇甫謐", "中醫經典", "魏晉"],
        "subpages": True,
        "subpage_list": [
            "卷一", "卷二", "卷三", "卷四", "卷五",
            "卷六", "卷七", "卷八", "卷九", "卷十",
            "卷十一", "卷十二",
        ],
    },
    {
        "category": "中医",
        "wiki_title": "脈經",
        "display_title": "脈經",
        "tags": ["脈經", "王叔和", "中醫經典", "西晉"],
        "subpages": True,
        "subpage_list": [
            "卷第一", "卷第二", "卷第三", "卷第四", "卷第五",
            "卷第六", "卷第七", "卷第八", "卷第九", "卷第十",
        ],
    },
    {
        "category": "中医",
        "wiki_title": "中藏經",
        "display_title": "中藏經",
        "tags": ["中藏經", "華佗", "中醫經典", "東漢"],
        "subpages": False,
    },
    {
        "category": "中医",
        "wiki_title": "瀕湖脈學",
        "display_title": "瀕湖脈學",
        "tags": ["瀕湖脈學", "李時珍", "明代"],
        "subpages": False,
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


async def import_classics(db_url: str, dry_run: bool):
    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)
    imported = 0
    failed = 0

    async with httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers={"User-Agent": UA}
    ) as client:
        for text_info in TEXTS:
            category = text_info["category"]
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
                                doc_title, content, category, tags,
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
                            main_title, content, category, text_info["tags"],
                        )
                        imported += 1
                        logger.info(f"  Imported: {main_title} ({ch_chars} chars)")
                    except Exception as e:
                        logger.error(f"  Insert error: {e}")
                        failed += 1

    await pool.close()
    print(f"\n{'Dry run' if dry_run else 'Import'} summary: {imported} imported, {failed} failed")


def main():
    parser = argparse.ArgumentParser(description="Import classics batch 2 from zh.wikisource.org")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(import_classics(args.db_url, args.dry_run))


if __name__ == "__main__":
    main()
