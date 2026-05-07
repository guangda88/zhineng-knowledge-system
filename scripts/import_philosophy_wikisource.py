#!/usr/bin/env python3
"""
从 zh.wikisource.org 导入哲学典籍到 documents 表

覆盖先秦诸子、宋明理学等中国哲学核心文献

用法:
    python scripts/import_philosophy_wikisource.py --dry-run
    python scripts/import_philosophy_wikisource.py

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
CATEGORY = "哲学"
API_BASE = "https://zh.wikisource.org/w/api.php"
UA = "ZhiNengKnowledgeSystem/1.0 (educational use)"

TEXTS = [
    {
        "wiki_title": "論語",
        "display_title": "論語",
        "tags": ["論語", "孔子", "儒家", "先秦"],
        "subpages": True,
        "subpage_list": [
            "學而第一", "為政第二", "八佾第三", "里仁第四", "公冶長第五",
            "雍也第六", "述而第七", "泰伯第八", "子罕第九", "鄉黨第十",
            "先進第十一", "顏淵第十二", "子路第十三", "憲問第十四", "衛靈公第十五",
            "季氏第十六", "陽貨第十七", "微子第十八", "子張第十九", "堯曰第二十",
        ],
    },
    {
        "wiki_title": "孟子",
        "display_title": "孟子",
        "tags": ["孟子", "儒家", "先秦"],
        "subpages": True,
        "subpage_list": [
            "梁惠王上", "梁惠王下", "公孫丑上", "公孫丑下",
            "滕文公上", "滕文公下", "離婁上", "離婁下",
            "萬章上", "萬章下", "告子上", "告子下",
            "盡心上", "盡心下",
        ],
    },
    {
        "wiki_title": "荀子",
        "display_title": "荀子",
        "tags": ["荀子", "儒家", "先秦"],
        "subpages": True,
        "subpage_list": [
            "勸學", "修身", "不苟", "榮辱", "非相", "非十二子",
            "仲尼", "儒效", "王制", "富國", "王霸", "君道",
            "臣道", "致士", "議兵", "彊國", "天論", "正論",
            "禮論", "樂論", "解蔽", "正名", "性惡", "君子",
            "成相", "賦", "大略", "宥坐", "子道", "哀公", "堯問",
        ],
    },
    {
        "wiki_title": "墨子",
        "display_title": "墨子",
        "tags": ["墨子", "墨家", "先秦"],
        "subpages": True,
        "subpage_list": [
            "親士", "修身", "所染", "法儀", "七患", "辭過", "三辯",
            "尚賢上", "尚賢中", "尚賢下", "尚同上", "尚同中", "尚同下",
            "兼愛上", "兼愛中", "兼愛下", "非攻上", "非攻中", "非攻下",
            "節用上", "節用中", "節葬下", "天志上", "天志中", "天志下",
            "明鬼下", "非樂上", "非命上", "非命中", "非命下",
            "非儒下", "經上", "經下", "經說上", "經說下",
            "大取", "小取", "耕柱", "貴義", "公孟", "魯問", "公輸",
        ],
    },
    {
        "wiki_title": "韓非子",
        "display_title": "韓非子",
        "tags": ["韓非子", "法家", "先秦"],
        "subpages": True,
        "subpage_list": [
            "初見秦", "存韓", "難言", "愛臣", "主道", "有度",
            "二柄", "揚權", "八奸", "十過", "孤憤", "說難",
            "和氏", "奸劫弒臣", "亡徵", "三守", "備內", "南面",
            "飾邪", "解老", "喻老", "說林上", "說林下",
            "觀行", "安危", "守道", "用人", "功名", "大體",
            "內儲說上", "內儲說下", "外儲說左上", "外儲說左下",
            "外儲說右上", "外儲說右下", "難一", "難二", "難三", "難四",
            "難勢", "問辯", "問田", "定法", "說疑", "詭使",
            "六反", "八說", "八經", "五蠹", "顯學", "忠孝",
            "人主", "飭令", "心度", "制分",
        ],
    },
    {
        "wiki_title": "孫子兵法",
        "display_title": "孫子兵法",
        "tags": ["孫子", "兵家", "先秦"],
        "subpages": False,
    },
    {
        "wiki_title": "公孫龍子",
        "display_title": "公孫龍子",
        "tags": ["公孫龍", "名家", "先秦"],
        "subpages": False,
    },
    {
        "wiki_title": "鬼谷子",
        "display_title": "鬼谷子",
        "tags": ["鬼谷子", "纵横家", "先秦"],
        "subpages": True,
        "subpage_list": [
            "序", "卷01", "卷02", "卷03",
            "鬼谷子附録", "鬼谷子篇目考", "跋",
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
            await asyncio.sleep(2.0)
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


async def import_philosophy(db_url: str, dry_run: bool):
    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)
    imported = 0

    # Only process texts that are not fully imported yet
    SKIP_BOOKS = {"論語", "孟子", "荀子", "墨子", "韓非子"}
    texts_to_import = [t for t in TEXTS if t["display_title"] not in SKIP_BOOKS]
    logger.info(f"Skipping already-imported: {SKIP_BOOKS}")
    logger.info(f"Will import: {[t['display_title'] for t in texts_to_import]}")

    async with httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers={"User-Agent": UA}
    ) as client:
        for text_info in texts_to_import:
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

    await pool.close()
    print(f"\n{'Dry run' if dry_run else 'Import'} summary: {imported} documents")


def main():
    parser = argparse.ArgumentParser(description="Import Philosophy texts from zh.wikisource.org")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(import_philosophy(args.db_url, args.dry_run))


if __name__ == "__main__":
    main()
