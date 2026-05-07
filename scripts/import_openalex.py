#!/usr/bin/env python3
"""
从 OpenAlex API 导入中文学术论文到 documents 表

覆盖弱势类别：科学、心理学、哲学、武术
OpenAlex 是免费开放的学术文献API，无需API key

用法:
    python scripts/import_openalex.py --dry-run                # 预览全部
    python scripts/import_openalex.py --dry-run --category 科学  # 预览单类别
    python scripts/import_openalex.py                          # 执行导入
    python scripts/import_openalex.py --category 心理学         # 导入单类别

数据来源: https://openalex.org
License: OpenAlex 数据以 CC0 许可发布
"""

import argparse
import os
import asyncio
import json
import logging
import re
import sys
import time

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = os.getenv("DATABASE_URL")

OPENALEX_BASE = "https://api.openalex.org"
UA = "ZhiNengKnowledgeSystem/1.0 (educational; mailto:zhineng@example.com)"

CATEGORY_CONFIG = {
    "科学": {
        "concept_id": "C121332964",
        "concept_name": "Physics",
        "extra_concepts": ["C41008148", "C192562357"],
        "extra_names": ["Computer Science", "Materials science"],
        "max_docs": 2000,
        "search_terms": ["科学", "技术", "物理", "化学", "生物", "数学", "天文", "医学"],
    },
    "心理学": {
        "concept_id": "C15744967",
        "concept_name": "Psychology",
        "extra_concepts": ["C17741044"],
        "extra_names": ["Clinical psychology"],
        "max_docs": 1500,
        "search_terms": ["心理", "认知", "情绪", "行为", "意识", "心理治疗", "心理咨询"],
    },
    "哲学": {
        "concept_id": "C169760540",
        "concept_name": "Philosophy",
        "extra_concepts": ["C95330714"],
        "extra_names": ["Ethics"],
        "max_docs": 1000,
        "search_terms": ["哲学", "思想", "伦理", "逻辑", "美学", "认识论", "形而上学"],
    },
    "武术": {
        "concept_id": None,
        "concept_name": None,
        "extra_concepts": [],
        "extra_names": [],
        "max_docs": 500,
        "search_terms": ["武术", "功夫", "太极", "拳法", "格斗", "武术训练", "传统武术"],
    },
    "道家": {
        "concept_id": "C2781334924",
        "concept_name": "Taoism",
        "extra_concepts": ["C26832752"],
        "extra_names": ["Chinese philosophy"],
        "max_docs": 1000,
        "search_terms": ["道教", "道家", "老子", "庄子", "内丹", "养生", "修炼", "道", "气功"],
    },
}

ABSTRACT_MIN_CHARS = 50
TITLE_MIN_CHARS = 5
BATCH_SIZE = 50
PER_PAGE = 200


def invert_abstract(inv_idx: dict | None) -> str:
    if not inv_idx:
        return ""
    words = [""] * (max(pos for positions in inv_idx.values() for pos in positions) + 1)
    for word, positions in inv_idx.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words)


async def fetch_works(
    client: httpx.AsyncClient,
    filter_str: str,
    per_page: int = PER_PAGE,
    cursor: str | None = None,
) -> tuple[list[dict], str | None]:
    params = {
        "filter": filter_str,
        "per_page": per_page,
        "select": "id,title,abstract_inverted_index,publication_year,primary_location,concepts",
        "sort": "relevance_score:desc",
    }
    if cursor:
        params["cursor"] = cursor

    r = await client.get(f"{OPENALEX_BASE}/works", params=params)
    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", "2"))
        logger.warning(f"Rate limited, waiting {retry_after}s")
        await asyncio.sleep(retry_after)
        return await fetch_works(client, filter_str, per_page, cursor)

    r.raise_for_status()
    data = r.json()
    results = data.get("results", [])
    next_cursor = data.get("meta", {}).get("next_cursor")
    return results, next_cursor


def build_filter(config: dict, search_term: str | None = None) -> str:
    parts = ["language:zh", "type:article"]

    concept_ids = []
    if config.get("concept_id"):
        concept_ids.append(config["concept_id"])
    concept_ids.extend(config.get("extra_concepts", []))

    if concept_ids and not search_term:
        parts.append(f"concepts.id:{'|'.join(concept_ids)}")

    if search_term:
        parts.append(f"title.search:{search_term}")

    return ",".join(parts)


async def import_category(
    client: httpx.AsyncClient,
    pool,
    category: str,
    config: dict,
    dry_run: bool,
    max_docs: int | None = None,
) -> int:
    limit = max_docs or config["max_docs"]
    imported = 0
    seen_titles = set()

    search_terms = config.get("search_terms", [])

    for term in search_terms:
        if imported >= limit:
            break

        remaining = limit - imported
        filter_str = build_filter(config, search_term=term)
        logger.info(f"[{category}] Searching: '{term}' (need {remaining} more)")

        cursor = "*"
        page_count = 0

        while cursor and imported < limit:
            remaining = limit - imported
            fetch_count = min(PER_PAGE, remaining + 50)

            try:
                works, next_cursor = await fetch_works(client, filter_str, fetch_count, cursor)
            except Exception as e:
                logger.error(f"  Fetch error: {e}")
                break

            page_count += 1

            for work in works:
                if imported >= limit:
                    break

                title = work.get("title", "")
                if not title or len(title) < TITLE_MIN_CHARS:
                    continue

                if title in seen_titles:
                    continue
                seen_titles.add(title)

                abstract = invert_abstract(work.get("abstract_inverted_index"))
                year = work.get("publication_year", "")

                if abstract:
                    content = f"{title}\n\n{abstract}"
                else:
                    continue

                if len(abstract) < ABSTRACT_MIN_CHARS:
                    continue

                source_name = ""
                pl = work.get("primary_location") or {}
                src = pl.get("source") or {}
                source_name = src.get("display_name", "")

                tags = [category]
                if year:
                    tags.append(str(year))
                if source_name:
                    tags.append(source_name)

                metadata = {
                    "openalex_id": work.get("id", ""),
                    "year": year,
                    "source": source_name,
                }

                if dry_run:
                    if imported < 5 or imported % 100 == 0:
                        logger.info(f"  [{category}] {title[:60]}... ({len(abstract)} chars)")
                    imported += 1
                    continue

                try:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO documents (title, content, category, tags, source_file, metadata)
                            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                            ON CONFLICT (title) DO NOTHING
                            """,
                            title,
                            content,
                            category,
                            tags,
                            f"openalex:{category}",
                            json.dumps(metadata, ensure_ascii=False),
                        )
                    imported += 1
                except Exception as e:
                    if "unique" not in str(e).lower():
                        logger.error(f"  Insert error: {e}")

            cursor = next_cursor
            await asyncio.sleep(0.5)

        logger.info(f"[{category}] After '{term}': {imported} docs")

    return imported


async def main():
    parser = argparse.ArgumentParser(description="Import Chinese academic works from OpenAlex")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--category", choices=list(CATEGORY_CONFIG.keys()), help="Import only this category")
    parser.add_argument("--max-docs", type=int, help="Override max docs per category")
    args = parser.parse_args()

    import asyncpg

    pool = await asyncpg.create_pool(args.db_url, min_size=1, max_size=3) if not args.dry_run else None

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": UA},
    ) as client:
        categories = {args.category: CATEGORY_CONFIG[args.category]} if args.category else CATEGORY_CONFIG

        total = 0
        for cat, config in categories.items():
            logger.info(f"=== Processing category: {cat} ===")
            count = await import_category(client, pool, cat, config, args.dry_run, args.max_docs)
            total += count
            logger.info(f"=== {cat}: {count} docs ===\n")

    if pool:
        await pool.close()

    print(f"\n{'Dry run' if args.dry_run else 'Import'} complete: {total} total documents")


if __name__ == "__main__":
    asyncio.run(main())
