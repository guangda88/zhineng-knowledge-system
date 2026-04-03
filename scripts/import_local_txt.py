#!/usr/bin/env python3
"""
Import local TXT files into PostgreSQL documents table.

Reads from data/textbooks/txt格式/ (170 files, ~34MB actual Chinese text).
These are the ONLY real text content assets currently available.
All files are 智能气功-related teaching materials, lectures, and essays.

Usage:
    source .env
    DATABASE_URL="postgresql://..." python scripts/import_local_txt.py [--dry-run]
"""

import asyncio
import os
import re
import sys
import time
import hashlib
from pathlib import Path

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg required. pip install asyncpg")
    sys.exit(1)

TXT_DIR = Path(__file__).parent.parent / "data" / "textbooks" / "txt格式"

CATEGORY = "气功"
TAGS = ["智能气功", "教材", "TXT导入"]

# Author extraction patterns
AUTHOR_PATTERNS = [
    re.compile(r"[（(]\s*庞明\s*[）)]"),
    re.compile(r"庞明\s*[著讲课]"),
    re.compile(r"作者[：:]\s*庞明"),
]

YEAR_PATTERNS = [
    re.compile(r"(19[89]\d|20[01]\d)\s*年"),
]


def extract_metadata(filename: str, content: str) -> dict:
    """Extract author, year, subcategory from filename + content preview."""
    meta = {"author": None, "year": None, "subcategory": None}

    # Author from filename
    author_match = re.search(r"[（(]\s*庞明\s*[）)]", filename)
    if author_match:
        meta["author"] = "庞明"

    # Author from first 2000 chars of content
    if not meta["author"]:
        preview = content[:2000]
        for pat in AUTHOR_PATTERNS:
            if pat.search(preview):
                meta["author"] = "庞明"
                break

    # Year from filename
    year_match = re.search(r"(19[89]\d|20[01]\d)", filename)
    if year_match:
        meta["year"] = int(year_match.group(1))

    # Year from content first 500 chars
    if not meta["year"]:
        for pat in YEAR_PATTERNS:
            m = pat.search(content[:500])
            if m:
                meta["year"] = int(m.group(1))
                break

    # Subcategory from filename keywords
    name = filename.lower()
    if any(k in name for k in ["功法", "捧气", "形神", "五元", "三心", "混元卧", "站庄", "喉呼吸"]):
        meta["subcategory"] = "功法"
    elif any(k in name for k in ["理论", "混元整体", "整体观", "概论", "精义"]):
        meta["subcategory"] = "理论"
    elif any(k in name for k in ["超常智能", "发达智力", "智能"]):
        meta["subcategory"] = "超常智能"
    elif any(k in name for k in ["道德", "修养", "涵养"]):
        meta["subcategory"] = "道德修养"
    elif any(k in name for k in ["医疗", "治病", "防治"]):
        meta["subcategory"] = "气功医疗"
    elif any(k in name for k in ["科研", "科学"]):
        meta["subcategory"] = "科学研究"
    elif any(k in name for k in ["文化", "人类文化", "历史", "发展史"]):
        meta["subcategory"] = "气功文化"
    elif any(k in name for k in ["传统", "综述"]):
        meta["subcategory"] = "传统气功"
    elif any(k in name for k in ["辅导", "辅导材料", "函授"]):
        meta["subcategory"] = "辅导材料"
    elif any(k in name for k in ["讲课", "讲课记录", "培训"]):
        meta["subcategory"] = "讲课记录"
    elif any(k in name for k in ["集训", "体会", "调查", "报告"]):
        meta["subcategory"] = "文集报告"
    elif any(k in name for k in ["诗歌", "命运"]):
        meta["subcategory"] = "文集报告"

    return meta


def clean_title(filename: str) -> str:
    """Derive a clean title from filename."""
    title = Path(filename).stem
    # Remove common suffixes
    title = re.sub(r"2010版\(?\d*\)?$", "", title)
    title = re.sub(r"\(\d+\)$", "", title)
    title = re.sub(r"^\d+", "", title)
    title = title.strip(" ()（）")
    if not title:
        title = Path(filename).stem
    return title


async def check_existing(conn, title: str) -> bool:
    """Check if a document with this title already exists."""
    row = await conn.fetchrow(
        "SELECT id FROM documents WHERE title = $1 AND category = $2 LIMIT 1",
        title, CATEGORY
    )
    return row is not None


async def import_documents(dry_run: bool = False):
    """Main import function."""
    if not TXT_DIR.exists():
        print(f"ERROR: TXT directory not found: {TXT_DIR}")
        sys.exit(1)

    txt_files = sorted(TXT_DIR.glob("*.txt"))
    print(f"Found {len(txt_files)} TXT files in {TXT_DIR}")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = await asyncpg.connect(database_url)

    # Check current state
    current_count = await conn.fetchval(
        "SELECT COUNT(*) FROM documents WHERE category = $1", CATEGORY
    )
    with_content = await conn.fetchval(
        "SELECT COUNT(*) FROM documents WHERE category = $1 AND length(content) > 100", CATEGORY
    )
    print(f"Current state: {current_count} 气功 docs, {with_content} with content>100 chars")
    print()

    imported = 0
    skipped_dup = 0
    skipped_empty = 0
    errors = 0
    start_time = time.time()

    for i, fpath in enumerate(txt_files):
        filename = fpath.name

        try:
            # Read file content with encoding detection
            content = None
            for enc in ["utf-8", "gbk", "gb18030", "utf-16"]:
                try:
                    content = fpath.read_text(encoding=enc)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

            if content is None:
                print(f"  [{i+1}/{len(txt_files)}] SKIP (encoding): {filename}")
                skipped_empty += 1
                continue

            content = content.replace('\x00', '').strip()
            if len(content) < 50:
                print(f"  [{i+1}/{len(txt_files)}] SKIP (too short, {len(content)} chars): {filename}")
                skipped_empty += 1
                continue

            title = clean_title(filename)
            meta = extract_metadata(filename, content)

            # Check for duplicates
            if await check_existing(conn, title):
                print(f"  [{i+1}/{len(txt_files)}] SKIP (duplicate title): {title[:50]}")
                skipped_dup += 1
                continue

            # Build tags
            tags = list(TAGS)
            if meta["subcategory"]:
                tags.append(meta["subcategory"])

            # Generate content hash
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

            if dry_run:
                print(
                    f"  [{i+1}/{len(txt_files)}] DRY: {title[:40]} | "
                    f"{len(content)} chars | author={meta['author']} | "
                    f"year={meta['year']} | sub={meta['subcategory']}"
                )
                imported += 1
                continue

            # Insert into documents
            # tsv_content is a GENERATED ALWAYS column, cannot set explicitly
            try:
                await conn.execute(
                    """
                    INSERT INTO documents (title, content, category, tags, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, NOW(), NOW())
                    """,
                    title,
                    content,
                    CATEGORY,
                    tags,
                )
            except Exception as insert_err:
                if "string too long" in str(insert_err).lower() or "tsvector" in str(insert_err).lower():
                    # Content too large for tsvector generated column - truncate
                    safe_len = 300000
                    print(f"  [{i+1}/{len(txt_files)}] WARN: truncating {len(content)} chars -> {safe_len} for tsvector: {filename}")
                    await conn.execute(
                        """
                        INSERT INTO documents (title, content, category, tags, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, NOW(), NOW())
                        """,
                        title,
                        content[:safe_len],
                        CATEGORY,
                        tags,
                    )
                else:
                    raise
            imported += 1

            if (i + 1) % 10 == 0 or (i + 1) == len(txt_files):
                elapsed = time.time() - start_time
                print(
                    f"  [{i+1}/{len(txt_files)}] Progress: {imported} imported, "
                    f"{skipped_dup} dup, {skipped_empty} empty | {elapsed:.1f}s"
                )

        except Exception as e:
            print(f"  [{i+1}/{len(txt_files)}] ERROR: {filename}: {e}")
            errors += 1

    elapsed = time.time() - start_time

    # Also import textbooks.db documents (304 rows with previews)
    tb_imported = 0
    tb_path = Path(__file__).parent.parent / "data" / "textbooks.db"
    if tb_path.exists() and not dry_run:
        import sqlite3
        print(f"\n--- Importing textbooks.db documents (with content previews) ---")
        sq_conn = sqlite3.connect(str(tb_path))
        sq_cur = sq_conn.cursor()
        sq_cur.execute(
            "SELECT title, content_preview, file_name, content_length "
            "FROM documents WHERE content_preview IS NOT NULL "
            "AND length(content_preview) > 100"
        )
        tb_rows = sq_cur.fetchall()
        print(f"Found {len(tb_rows)} documents with content in textbooks.db")

        for row in tb_rows:
            tb_title, preview, file_name, clen = row
            if not tb_title or not preview:
                continue

            # Clean title - use first 200 chars
            clean_tb_title = tb_title[:200].strip()
            if len(clean_tb_title) < 5:
                continue

            # Check duplicate
            if await check_existing(conn, clean_tb_title):
                continue

            # Use the preview as content (it's the best we have from textbooks.db)
            tags = ["智能气功", "教材", "textbooks.db导入"]

            try:
                clean_preview = preview.replace('\x00', '')
                await conn.execute(
                    """
                    INSERT INTO documents (title, content, category, tags, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, NOW(), NOW())
                    """,
                    clean_tb_title,
                    clean_preview,
                    CATEGORY,
                    tags,
                )
                tb_imported += 1
            except Exception as e:
                print(f"  ERROR importing textbook doc: {e}")

        sq_conn.close()

    await conn.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"Import complete in {elapsed:.1f}s")
    print(f"  TXT files imported:  {imported}")
    print(f"  TXT files skipped (dup): {skipped_dup}")
    print(f"  TXT files skipped (empty): {skipped_empty}")
    print(f"  TXT errors: {errors}")
    if tb_imported > 0:
        print(f"  textbooks.db docs:   {tb_imported}")
    print(f"  Total new documents: {imported + tb_imported}")

    if dry_run:
        print(f"\n[DRY RUN] No data was written to database.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN MODE ===\n")
    asyncio.run(import_documents(dry_run=dry_run))
