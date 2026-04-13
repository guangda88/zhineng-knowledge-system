"""Import texts for missing domains (武术/哲学/科学/心理学) from zh.wikisource.org.

Usage:
    # Dry-run
    python scripts/import_missing_domains.py --dry-run

    # Execute
    python scripts/import_missing_domains.py

    # Specific domain only
    python scripts/import_missing_domains.py --domain 武术
"""

import argparse
import asyncio
import logging
import os
import re

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb",
)
UA = "ZhiNengKnowledgeSystem/1.0 (educational use; https://github.com/zhineng)"

WIKISOURCE_API = "https://zh.wikisource.org/w/api.php"

DOMAINS = {
    "武术": [
        {
            "wiki_title": "孫子兵法",
            "display_title": "孙子兵法",
            "subpages": False,
            "subpage_list": [],
        },
        {
            "wiki_title": "吳子",
            "display_title": "吴子",
            "subpages": False,
            "subpage_list": [],
        },
        {
            "wiki_title": "六韜",
            "display_title": "六韬",
            "subpages": False,
            "subpage_list": [],
        },
        {
            "wiki_title": "三略",
            "display_title": "三略",
            "subpages": False,
            "subpage_list": [],
        },
        {
            "wiki_title": "尉繚子",
            "display_title": "尉缭子",
            "subpages": False,
            "subpage_list": [],
        },
        {
            "wiki_title": "李衛公問對",
            "display_title": "李卫公问对",
            "subpages": False,
            "subpage_list": [],
        },
        {
            "wiki_title": "少林拳術秘訣",
            "display_title": "少林拳术秘诀",
            "subpages": True,
            "subpage_list": [],
        },
        {
            "wiki_title": "手臂錄",
            "display_title": "手臂录",
            "subpages": False,
            "subpage_list": [],
        },
        {
            "wiki_title": "意拳正軌",
            "display_title": "意拳正轨",
            "subpages": False,
            "subpage_list": [],
        },
    ],
    "哲学": [
        {
            "wiki_title": "墨子",
            "display_title": "墨子",
            "subpages": True,
            "subpage_list": [],
        },
        {
            "wiki_title": "荀子",
            "display_title": "荀子",
            "subpages": True,
            "subpage_list": [],
        },
        {
            "wiki_title": "韓非子",
            "display_title": "韩非子",
            "subpages": True,
            "subpage_list": [],
        },
        {
            "wiki_title": "公孫龍子",
            "display_title": "公孙龙子",
            "subpages": False,
            "subpage_list": [],
        },
        {
            "wiki_title": "管子",
            "display_title": "管子",
            "subpages": True,
            "subpage_list": [],
        },
    ],
    "科学": [
        {
            "wiki_title": "天工開物",
            "display_title": "天工开物",
            "subpages": True,
            "subpage_list": [],
        },
        {
            "wiki_title": "夢溪筆談",
            "display_title": "梦溪笔谈",
            "subpages": True,
            "subpage_list": [],
        },
        {
            "wiki_title": "齊民要術",
            "display_title": "齐民要术",
            "subpages": True,
            "subpage_list": [],
        },
        {
            "wiki_title": "本草綱目",
            "display_title": "本草纲目",
            "subpages": True,
            "subpage_list": [],
        },
        {
            "wiki_title": "水經注",
            "display_title": "水经注",
            "subpages": True,
            "subpage_list": [],
        },
        {
            "wiki_title": "農政全書",
            "display_title": "农政全书",
            "subpages": True,
            "subpage_list": [],
        },
    ],
    "心理学": [
        {
            "wiki_title": "鬼谷子",
            "display_title": "鬼谷子",
            "subpages": False,
            "subpage_list": [],
        },
        {
            "wiki_title": "人物志",
            "display_title": "人物志 (刘劭)",
            "subpages": False,
            "subpage_list": [],
        },
        {
            "wiki_title": "冰鑑",
            "display_title": "冰鉴",
            "subpages": False,
            "subpage_list": [],
        },
        {
            "wiki_title": "呻吟語",
            "display_title": "呻吟语",
            "subpages": True,
            "subpage_list": [],
        },
    ],
}


async def fetch_wikitext(client: httpx.AsyncClient, title: str) -> str | None:
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "format": "json",
    }
    try:
        resp = await client.get(WIKISOURCE_API, params=params)
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for pid, page in pages.items():
            if "missing" in page:
                return None
            revs = page.get("revisions", [])
            if revs:
                return revs[0]["*"]
    except Exception as e:
        logger.error(f"Failed to fetch '{title}': {e}")
    return None


async def get_subpages(client: httpx.AsyncClient, parent_title: str) -> list[str]:
    sroffset = None
    subpages = []
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "apprefix": parent_title + "/",
            "apnamespace": 0,
            "aplimit": 500,
            "format": "json",
        }
        if sroffset:
            params["apcontinue"] = sroffset
        try:
            resp = await client.get(WIKISOURCE_API, params=params)
            data = resp.json()
            for page in data.get("query", {}).get("allpages", []):
                title = page["title"]
                subpage_name = title[len(parent_title) + 1:]
                subpages.append(subpage_name)
            sroffset = data.get("continue", {}).get("apcontinue")
            if not sroffset:
                break
        except Exception as e:
            logger.error(f"Failed to list subpages for '{parent_title}': {e}")
            break
    return subpages


def clean_wikitext(wikitext: str) -> str:
    text = wikitext
    text = re.sub(r"\{\{[^\}]*\}\}", "", text)
    text = re.sub(r"\{\|[^\}]*\|\}", "", text, flags=re.DOTALL)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^;.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^-{2,}.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^=+\s*.*?\s*=+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def import_domain(
    client: httpx.AsyncClient,
    pool: asyncpg.Pool,
    domain: str,
    texts: list[dict],
    dry_run: bool,
) -> int:
    imported = 0
    for text_info in texts:
        main_title = text_info["display_title"]

        if text_info["subpages"] and not text_info["subpage_list"]:
            logger.info(f"[{domain}] Discovering subpages for {text_info['wiki_title']}...")
            subpages = await get_subpages(client, text_info["wiki_title"])
            text_info["subpage_list"] = subpages
            logger.info(f"[{domain}] Found {len(subpages)} subpages for {text_info['wiki_title']}")

        if text_info["subpage_list"]:
            for subpage in text_info["subpage_list"]:
                full_title = f"{text_info['wiki_title']}/{subpage}"
                doc_title = f"{main_title}·{subpage}"
                logger.info(f"[{domain}] Fetching {full_title}")
                wikitext = await fetch_wikitext(client, full_title)
                if not wikitext:
                    logger.warning(f"[{domain}] Page not found: {full_title}")
                    continue
                content = clean_wikitext(wikitext)
                if len(content) < 50:
                    logger.warning(f"[{domain}] Too short ({len(content)} chars): {full_title}")
                    continue

                logger.info(
                    f"[{domain}] {doc_title}: {len(content)} chars"
                    + (" (dry-run)" if dry_run else "")
                )
                imported += 1

                if not dry_run:
                    try:
                        await pool.execute(
                            "INSERT INTO documents (title, content, category) "
                            "VALUES ($1, $2, $3) ON CONFLICT (title) DO NOTHING",
                            doc_title,
                            content,
                            domain,
                        )
                    except Exception as e:
                        logger.error(f"Insert failed for {doc_title}: {e}")

                await asyncio.sleep(0.5)
        else:
            logger.info(f"[{domain}] Fetching {text_info['wiki_title']}")
            wikitext = await fetch_wikitext(client, text_info["wiki_title"])
            if not wikitext:
                logger.warning(f"[{domain}] Page not found: {text_info['wiki_title']}")
                continue
            content = clean_wikitext(wikitext)
            if len(content) < 50:
                logger.warning(f"[{domain}] Too short ({len(content)} chars): {text_info['wiki_title']}")
                continue

            logger.info(
                f"[{domain}] {main_title}: {len(content)} chars"
                + (" (dry-run)" if dry_run else "")
            )
            imported += 1

            if not dry_run:
                try:
                    await pool.execute(
                        "INSERT INTO documents (title, content, category) "
                        "VALUES ($1, $2, $3) ON CONFLICT (title) DO NOTHING",
                        main_title,
                        content,
                        domain,
                    )
                except Exception as e:
                    logger.error(f"Insert failed for {main_title}: {e}")

            await asyncio.sleep(0.5)

    return imported


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't insert")
    parser.add_argument("--domain", default=None, help="Import only this domain (武术/哲学/科学/心理学)")
    args = parser.parse_args()

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2)

    try:
        async with httpx.AsyncClient(
            timeout=30, follow_redirects=True, headers={"User-Agent": UA}
        ) as client:
            domains_to_import = (
                {args.domain: DOMAINS[args.domain]}
                if args.domain
                else DOMAINS
            )

            total_imported = 0
            for domain, texts in domains_to_import.items():
                logger.info(f"\n{'='*60}")
                logger.info(f"Importing domain: {domain} ({len(texts)} texts)")
                logger.info(f"{'='*60}")

                count = await import_domain(client, pool, domain, texts, args.dry_run)
                total_imported += count
                logger.info(f"[{domain}] Imported {count} documents")

            logger.info(f"\nTotal imported: {total_imported} documents")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
