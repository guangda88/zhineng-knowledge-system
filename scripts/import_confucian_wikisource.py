#!/usr/bin/env python3
"""
从 zh.wikisource.org 导入儒家典籍到 documents 表

覆盖儒家核心经典：禮記、易經、尚書、周禮、儀禮、今文孝經

子页面格式经过验证：
- 禮記：53 个子页面（禮記/大學, 禮記/中庸, 禮記/曲禮上, etc.）
- 易經：64 卦 + 十翼 子页面（易經/乾, 易經/坤, 易經/彖, etc.）
- 尚書：81 个子页面（尚書/堯典, 尚書/禹貢, etc.）
- 周禮：6 个子页面（周禮/天官冢宰, 周禮/地官司徒, etc.）
- 儀禮：17 个子页面（儀禮/士冠禮, 儀禮/士昬禮, etc.）
- 今文孝經：单页，无子页面

用法:
    python scripts/import_confucian_wikisource.py --dry-run
    python scripts/import_confucian_wikisource.py

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
CATEGORY = "儒家"
API_BASE = "https://zh.wikisource.org/w/api.php"
UA = "ZhiNengKnowledgeSystem/1.0 (educational use)"

LIJI_SUBPAGES = [
    "三年問", "中庸", "仲尼燕居", "儒行", "內則", "冠義", "哀公問", "問喪",
    "喪大記", "喪服四制", "喪服小記", "坊記", "大傳", "大學", "奔喪",
    "孔子閒居", "學記", "射義", "少儀", "投壺", "文王世子", "明堂位",
    "昏義", "曲禮上", "曲禮下", "曾子問", "月令", "服問", "雜記上",
    "雜記下", "樂記", "檀弓上", "檀弓下", "深衣", "燕義", "玉藻", "王制",
    "祭法", "祭統", "祭義", "禮器", "禮運", "經解", "緇衣", "聘義",
    "表記", "郊特牲", "鄉飲酒義", "間傳",
]

YIJING_HEXAGRAMS = [
    "乾", "坤", "屯", "蒙", "需", "訟", "師", "比", "小畜", "履",
    "泰", "否", "同人", "大有", "謙", "豫", "隨", "蠱", "臨", "觀",
    "噬嗑", "賁", "剝", "復", "无妄", "大畜", "頤", "大過", "坎", "離",
    "咸", "恒", "遯", "大壯", "晉", "明夷", "家人", "睽", "蹇", "解",
    "損", "益", "夬", "姤", "萃", "升", "困", "井", "革", "鼎",
    "震", "艮", "漸", "歸妹", "豐", "旅", "巽", "兌", "渙", "節",
    "中孚", "小過", "既濟", "未濟",
]

YIJING_COMMENTARIES = [
    ("周易", "彖"), ("周易", "大象"), ("周易", "小象"), ("周易", "文言"),
    ("易傳", "繫辭上"), ("易傳", "繫辭下"), ("易傳", "說卦"), ("易傳", "序卦"), ("易傳", "雜卦"),
]

SHANGSHU_SUBPAGES = [
    "堯典", "舜典", "大禹謨", "皐陶謨", "益稷", "禹貢", "甘誓", "五子之歌",
    "胤征", "湯誓", "仲虺之誥", "湯誥", "伊訓", "太甲上", "太甲中", "太甲下",
    "咸有一德", "說命上", "說命中", "說命下", "高宗肓日", "西伯戡黎", "微子",
    "泰誓上", "泰誓中", "泰誓下", "牧誓", "武成", "洪範", "旅獒",
    "金縢", "大誥", "微子之命", "康誥", "酒誥", "梓材", "召誥", "洛誥",
    "多士", "無逸", "君奭", "蔡仲之命", "多方", "立政", "周官", "君陳",
    "顧命", "康王之誥", "畢命", "君牙", "冏命", "費誓", "呂刑", "文侯之命",
    "秦誓", "尚書序",
]

ZHOU_LI_SUBPAGES = [
    "天官冢宰", "地官司徒", "春官宗伯", "夏官司馬", "秋官司寇", "冬官考工記",
]

YI_LI_SUBPAGES = [
    "士冠禮", "士昬禮", "士相見禮", "鄉飲酒禮", "鄉射禮", "燕禮", "大射",
    "聘禮", "公食大夫禮", "覲禮", "喪服", "士喪禮", "既夕禮", "士虞禮",
    "特牲饋食禮", "少牢饋食禮", "有司",
]

TEXTS = [
    {
        "wiki_title": "禮記",
        "display_title": "禮記",
        "tags": ["禮記", "儒家經典", "五經", "先秦"],
        "subpages": True,
        "subpage_list": LIJI_SUBPAGES,
    },
    {
        "wiki_title": "周易",
        "display_title": "易經",
        "tags": ["易經", "周易", "儒家經典", "五經", "先秦"],
        "subpages": True,
        "subpage_list": YIJING_HEXAGRAMS,
        "commentaries": YIJING_COMMENTARIES,
    },
    {
        "wiki_title": "尚書",
        "display_title": "尚書",
        "tags": ["尚書", "書經", "儒家經典", "五經", "先秦"],
        "subpages": True,
        "subpage_list": SHANGSHU_SUBPAGES,
    },
    {
        "wiki_title": "周禮",
        "display_title": "周禮",
        "tags": ["周禮", "儒家經典", "三禮", "先秦"],
        "subpages": True,
        "subpage_list": ZHOU_LI_SUBPAGES,
    },
    {
        "wiki_title": "儀禮",
        "display_title": "儀禮",
        "tags": ["儀禮", "儒家經典", "三禮", "先秦"],
        "subpages": True,
        "subpage_list": YI_LI_SUBPAGES,
    },
    {
        "wiki_title": "今文孝經",
        "display_title": "孝經",
        "tags": ["孝經", "儒家經典", "先秦"],
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


async def import_confucian(db_url: str, dry_run: bool):
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

                # Handle commentaries with different wiki prefixes (e.g., 易傳/繫辭上)
                if text_info.get("commentaries"):
                    for wiki_prefix, subpage in text_info["commentaries"]:
                        full_title = f"{wiki_prefix}/{subpage}"
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
    parser = argparse.ArgumentParser(description="Import Confucian classics from zh.wikisource.org")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(import_confucian(args.db_url, args.dry_run))


if __name__ == "__main__":
    main()
