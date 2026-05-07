#!/usr/bin/env python3
"""
从 zh.wikisource.org 导入道家核心典籍到 documents 表

通过 MediaWiki API 获取 维基文库 中道家典籍原文，清洗 wikitext 标记后导入。

用法:
    python scripts/import_daoist_wikisource.py --dry-run    # 预览
    python scripts/import_daoist_wikisource.py              # 执行导入

文本来源:
    - 老子 (匯校版) — 道德经全文 81 章
    - 莊子 — 33 篇 (內篇7 + 外篇15 + 雜篇11)
    - 列子 — 8 篇
    - 淮南子 — 21 篇
    - 文子 — 12 篇

License: 维基文库内容为公共领域
"""

import argparse
import os
import asyncio
import json
import logging
import re

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = os.getenv("DATABASE_URL")
CATEGORY = "道家"
API_BASE = "https://zh.wikisource.org/w/api.php"
UA = "ZhiNengKnowledgeSystem/1.0 (educational use; zhineng-knowledge-system)"


def clean_wikitext(wikitext: str) -> str:
    """Remove wikitext markup and extract pure Chinese text."""
    text = wikitext
    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Remove template calls like {{參|...}}, {{另|...}}
    text = re.sub(r"\{\{参\|", "", text)
    text = re.sub(r"\{\{另\|", "", text)
    # Remove other template calls
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    # Remove category links
    text = re.sub(r"\[\[Category:[^\]]*\]\]", "", text)
    # Convert wikilinks [[target|display]] → display
    text = re.sub(r"\[\[[^|\]]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove __TOC__ and similar
    text = re.sub(r"__[A-Z]+__", "", text)
    # Remove section headers markers (keep text)
    text = re.sub(r"^=+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*=+$", "", text, flags=re.MULTILINE)
    # Remove remaining markup
    text = re.sub(r"'''", "", text)
    text = re.sub(r"''", "", text)
    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text


# Texts to import: (wikisource title, display title, tags, has subpages)
TEXTS_TO_IMPORT = [
    {
        "wiki_title": "老子 (匯校版)",
        "display_title": "道德经",
        "tags": ["道德经", "老子", "先秦", "匯校版"],
        "subpages": False,
    },
    {
        "wiki_title": "莊子",
        "display_title": "莊子",
        "tags": ["莊子", "先秦"],
        "subpages": True,
        "subpage_list": [
            "逍遙遊", "齊物論", "養生主", "人間世", "德充符", "大宗師", "應帝王",
            "駢拇", "馬蹄", "胠篋", "在宥", "天地", "天道", "天運",
            "刻意", "繕性", "秋水", "至樂", "達生", "山木", "田子方", "知北遊",
            "庚桑楚", "徐無鬼", "則陽", "外物", "寓言", "讓王", "盜跖",
            "說劍", "漁父", "列禦寇", "天下",
        ],
    },
    {
        "wiki_title": "列子",
        "display_title": "列子",
        "tags": ["列子", "先秦"],
        "subpages": True,
        "subpage_list": [
            "天瑞篇", "黃帝篇", "周穆王篇", "仲尼篇", "湯問篇", "力命篇", "楊朱篇", "說符篇",
        ],
    },
    {
        "wiki_title": "淮南子",
        "display_title": "淮南子",
        "tags": ["淮南子", "西漢", "劉安"],
        "subpages": True,
        "subpage_list": [
            "原道訓", "俶真訓", "天文訓", "墬形訓", "時則訓", "覽冥訓",
            "精神訓", "本經訓", "主術訓", "繆稱訓", "齊俗訓", "道應訓",
            "氾論訓", "詮言訓", "兵略訓", "說山訓", "說林訓", "人間訓",
            "修務訓", "泰族訓", "要略",
        ],
    },
]


async def fetch_wikitext(client: httpx.AsyncClient, title: str, max_retries: int = 3) -> str | None:
    """Fetch wikitext content from Wikisource API with retry on 429."""
    for attempt in range(max_retries):
        try:
            await asyncio.sleep(1.5)
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
                wait = int(r.headers.get("Retry-After", "5"))
                logger.warning(f"Rate limited on '{title}', waiting {wait}s (attempt {attempt+1}/{max_retries})")
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
                await asyncio.sleep(3)
    return None


async def import_daoist(db_url: str, dry_run: bool):
    """Main import logic."""
    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)
    imported = 0

    async with httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers={"User-Agent": UA}
    ) as client:
        for text_info in TEXTS_TO_IMPORT:
            main_title = text_info["display_title"]

            if text_info["subpages"]:
                # Fetch each subpage separately
                for subpage in text_info["subpage_list"]:
                    full_title = f"{text_info['wiki_title']}/{subpage}"
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
                        continue

                    async with pool.acquire() as conn:
                        try:
                            await conn.execute(
                                """
                                INSERT INTO documents (title, content, category, tags)
                                VALUES ($1, $2, $3, $4)
                                ON CONFLICT (title) DO NOTHING
                                """,
                                doc_title,
                                content,
                                CATEGORY,
                                tags,
                            )
                            imported += 1
                            logger.info(f"  Imported: {doc_title} ({ch_chars} chars)")
                        except Exception as e:
                            logger.error(f"  Insert error: {e}")
            else:
                # Single page text
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
                    continue

                async with pool.acquire() as conn:
                    try:
                        await conn.execute(
                            """
                            INSERT INTO documents (title, content, category, tags)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (title) DO NOTHING
                            """,
                            main_title,
                            content,
                            CATEGORY,
                            text_info["tags"],
                        )
                        imported += 1
                        logger.info(f"  Imported: {main_title} ({ch_chars} chars)")
                    except Exception as e:
                        logger.error(f"  Insert error: {e}")

    await pool.close()
    if dry_run:
        print("\n=== Dry Run Summary ===")
        print(f"Texts to import: {sum(len(t.get('subpage_list', [])) if t['subpages'] else 1 for t in TEXTS_TO_IMPORT)}")
    else:
        print(f"\n=== Import Summary ===")
        print(f"Docs imported: {imported}")


def main():
    parser = argparse.ArgumentParser(description="Import Daoist texts from zh.wikisource.org")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(import_daoist(args.db_url, args.dry_run))


if __name__ == "__main__":
    main()
