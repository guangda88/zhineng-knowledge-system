#!/usr/bin/env python3
"""
CBETA XML-P5 导入管线 — 将 CBETA 佛典 TEI XML 导入 documents 表

用法:
    # 先克隆 CBETA XML-P5 仓库
    git clone --depth 1 https://github.com/cbeta-org/xml-p5.git /data/cbeta/xml-p5

    # 导入大正藏 (T) 全部经文
    python scripts/import_cbeta.py --source /data/cbeta/xml-p5 --canon T

    # 导入特定卷
    python scripts/import_cbeta.py --source /data/cbeta/xml-p5 --canon T --volumes T01,T02,T09

    # 仅解析不导入 (dry-run)
    python scripts/import_cbeta.py --source /data/cbeta/xml-p5 --canon T --dry-run

    # 指定数据库
    python scripts/import_cbeta.py --source /data/cbeta/xml-p5 --canon T --db-url postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb

数据结构:
    - 每个 XML 文件 = 一部经
    - title: 经名 (从 <title> 或 <teiHeader> 提取)
    - content: 纯文本 (去掉所有 XML 标记)
    - category: '佛家'
    - tags: [canon_abbreviation, vol_number, sutra_number]

CBETA TEI P5 结构:
    <TEI>
      <teiHeader>
        <fileDesc>
          <titleStmt>
            <title>經名</title>
          </titleStmt>
          <sourceDesc>
            <bibl>...</bibl>
          </sourceDesc>
        </fileDesc>
      </teiHeader>
      <text>
        <body>
          <div type="jing" n="1">   <!-- 卷 -->
            <div type="pin" n="1"> <!-- 品 -->
              <p>正文...</p>
            </div>
          </div>
        </body>
      </text>
    </TEI>
"""

import argparse
import glob
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
CATEGORY = "佛家"

TEI_NS = "http://www.tei-c.org/ns/1.0"
CBETA_NS = "http://www.cbeta.org/ns/1.0"


def strip_ns(tag: str) -> str:
    """Remove XML namespace from tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def extract_text_recursive(elem: ET.Element) -> str:
    """Extract all text content from element tree, preserving structure."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        child_tag = strip_ns(child.tag)
        if child_tag in ("app", "note", "lem", "rdg"):
            # Skip apparatus criticus and notes
            if child.tail:
                parts.append(child.tail)
            continue
        child_text = extract_text_recursive(child)
        if child_text.strip():
            parts.append(child_text)
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def clean_text(raw: str) -> str:
    """Clean extracted text: normalize whitespace, remove CBETA markers."""
    text = raw
    # Remove CBETA column/line markers like [0001a01]
    text = re.sub(r"\[\d{4}[a-c]\d{2}\]", "", text)
    # Remove CBETA page breaks
    text = re.sub(r"＊", "", text)
    # Remove inline editorial markers
    text = re.sub(r"〔.*?〕", "", text)
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def parse_sutra_xml(filepath: str) -> dict | None:
    """Parse a single CBETA XML file and extract sutra data."""
    try:
        tree = ET.parse(filepath)
    except ET.ParseError as e:
        logger.warning(f"XML parse error in {filepath}: {e}")
        return None

    root = tree.getroot()

    # Extract title from teiHeader
    title = ""
    # Prefer level="m" (monograph-level) title
    for elem in root.findall(f".//{{{TEI_NS}}}titleStmt/{{{TEI_NS}}}title"):
        if elem.get("level") == "m" and elem.text:
            title = elem.text.strip()
            break
    # Fallback: find title with "No." pattern (e.g., "No. 1 長阿含經")
    if not title:
        for elem in root.findall(f".//{{{TEI_NS}}}titleStmt/{{{TEI_NS}}}title"):
            text = (elem.text or "").strip()
            if "No." in text:
                m = re.search(r"No\.\s*\d+\s*(.+)", text)
                if m:
                    title = m.group(1).strip()
                    break
    # Fallback: first title with Chinese characters
    if not title:
        for elem in root.iter():
            if strip_ns(elem.tag) == "title" and elem.text:
                text = elem.text.strip()
                if re.search(r"[\u4e00-\u9fff]", text):
                    title = text
                    break

    # Extract sutra number from filename (e.g., T01n0001 -> T0001)
    basename = Path(filepath).stem
    sutra_id = basename

    # Extract body text
    body_elem = root.find(f".//{{{TEI_NS}}}body")
    if body_elem is None:
        # Try without namespace
        body_elem = root.find(".//body")

    if body_elem is None:
        logger.warning(f"No body element in {filepath}")
        return None

    raw_text = extract_text_recursive(body_elem)
    content = clean_text(raw_text)

    if len(content) < 50:
        logger.debug(f"Skipping {filepath}: content too short ({len(content)} chars)")
        return None

    # Extract canon and volume from filename
    match = re.match(r"^([A-Z]{1,3})(\d+)n(\d+)$", basename)
    canon = match.group(1) if match else ""
    vol = f"{canon}{match.group(2)}" if match else ""
    num = match.group(3) if match else ""

    tags = []
    if canon:
        tags.append(f"CBETA_{canon}")
    if vol:
        tags.append(f"vol_{vol}")
    if num:
        tags.append(f"n{num}")

    doc_title = f"[{sutra_id}] {title}" if title else f"CBETA {sutra_id}"

    # Chunk large sutras to avoid tsvector 1MB limit (tsv_content is GENERATED ALWAYS AS)
    # Chinese text ≈ 3 bytes/char, tsvector ≈ similar size. 200K chars ≈ 600KB, safe.
    MAX_CHUNK = 200000
    if len(content) <= MAX_CHUNK:
        return [{
            "title": doc_title,
            "content": content,
            "category": CATEGORY,
            "tags": tags,
            "sutra_id": sutra_id,
            "canon": canon,
            "volume": vol,
        }]

    chunks = []
    n_chunks = (len(content) + MAX_CHUNK - 1) // MAX_CHUNK
    for i in range(n_chunks):
        start = i * MAX_CHUNK
        end = min(start + MAX_CHUNK, len(content))
        chunk_title = f"{doc_title} ({i+1}/{n_chunks})"
        chunks.append({
            "title": chunk_title,
            "content": content[start:end],
            "category": CATEGORY,
            "tags": tags,
            "sutra_id": f"{sutra_id}_p{i+1}",
            "canon": canon,
            "volume": vol,
        })
    return chunks


def find_xml_files(source_dir: str, canon: str, volumes: list[str] | None) -> list[str]:
    """Find all XML files matching the canon and optional volume filter."""
    canon_dir = os.path.join(source_dir, canon)
    if not os.path.isdir(canon_dir):
        logger.error(f"Canon directory not found: {canon_dir}")
        return []

    if volumes:
        files = []
        for vol in volumes:
            vol_dir = os.path.join(canon_dir, vol)
            if os.path.isdir(vol_dir):
                files.extend(sorted(glob.glob(os.path.join(vol_dir, "*.xml"))))
            else:
                logger.warning(f"Volume directory not found: {vol_dir}")
    else:
        files = sorted(glob.glob(os.path.join(canon_dir, "*", "*.xml")))

    return files


async def import_to_db(sutras: list[dict], db_url: str, batch_size: int = 50) -> int:
    """Import parsed sutras into documents table via asyncpg."""
    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=4)
    imported = 0
    errors = 0

    async with pool.acquire() as conn:
        # Check existing sutra_ids to avoid duplicates
        existing = set()
        rows = await conn.fetch("SELECT title FROM documents WHERE category = $1", CATEGORY)
        for r in rows:
            existing.add(r["title"])

        # Prepare batch
        batch = []
        for sutra in sutras:
            if sutra["title"] in existing:
                logger.debug(f"Skip duplicate: {sutra['title']}")
                continue
            batch.append(sutra)

            if len(batch) >= batch_size:
                count = await _insert_batch(conn, batch)
                imported += count
                errors += len(batch) - count
                batch = []

        if batch:
            count = await _insert_batch(conn, batch)
            imported += count
            errors += len(batch) - count

    await pool.close()
    logger.info(f"Import complete: {imported} imported, {errors} errors")
    return imported


async def _insert_batch(conn, batch: list[dict]) -> int:
    """Insert a batch of sutras using UNNEST for efficiency."""
    titles = [s["title"] for s in batch]
    contents = [s["content"] for s in batch]
    categories = [s["category"] for s in batch]
    tags = [s["tags"] for s in batch]

    try:
        result = await conn.execute(
            """
            INSERT INTO documents (title, content, category)
            SELECT * FROM UNNEST(
                $1::varchar(500)[],
                $2::text[],
                $3::varchar(50)[]
            )
            ON CONFLICT (title) DO NOTHING
            """,
            titles,
            contents,
            categories,
        )
        count_match = re.search(r"(\d+)$", result)
        return int(count_match.group(1)) if count_match else len(batch)
    except Exception as e:
        logger.error(f"Batch insert error: {e}")
        # Fall back to row-by-row
        count = 0
        for s in batch:
            try:
                result = await conn.execute(
                    """
                    INSERT INTO documents (title, content, category, tags)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (title) DO NOTHING
                    """,
                    s["title"],
                    s["content"],
                    s["category"],
                    s["tags"],
                )
                if result and "0" not in result.split()[-1:]:
                    count += 1
            except Exception as e2:
                logger.error(f"Row insert error for {s['sutra_id']}: {e2}")
        return count


def main():
    parser = argparse.ArgumentParser(description="Import CBETA XML-P5 sutras into documents table")
    parser.add_argument("--source", required=True, help="Path to xml-p5 clone directory")
    parser.add_argument("--canon", required=True, help="Canon code (T, X, A, etc.)")
    parser.add_argument("--volumes", default=None, help="Comma-separated volume list (e.g., T01,T02,T09)")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL, help="PostgreSQL connection string")
    parser.add_argument("--batch-size", type=int, default=50, help="DB insert batch size")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't import")
    parser.add_argument("--limit", type=int, default=None, help="Max sutras to process")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"])
    args = parser.parse_args()

    logging.getLogger().setLevel(args.log_level)

    # Find XML files
    volumes = args.volumes.split(",") if args.volumes else None
    xml_files = find_xml_files(args.source, args.canon, volumes)

    if not xml_files:
        logger.error("No XML files found")
        sys.exit(1)

    logger.info(f"Found {len(xml_files)} XML files in canon {args.canon}")

    if args.limit:
        xml_files = xml_files[: args.limit]

    # Parse all XML files
    sutras = []
    parse_errors = 0
    total_content_len = 0
    start = time.time()

    for i, filepath in enumerate(xml_files):
        result = parse_sutra_xml(filepath)
        if result is None:
            parse_errors += 1
            continue
        for s in result:
            sutras.append(s)
            total_content_len += len(s["content"])

        if (i + 1) % 100 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            logger.info(f"Parsed {i + 1}/{len(xml_files)} ({rate:.1f} files/sec)")

    elapsed = time.time() - start
    n_xml = len(xml_files)
    logger.info(
        f"Parsed {n_xml} XML -> {len(sutras)} docs ({parse_errors} errors) in {elapsed:.1f}s "
        f"({total_content_len / 1024 / 1024:.1f} MB total text)"
    )

    if args.dry_run:
        print(f"\n--- Dry Run Summary ---")
        print(f"Canon: {args.canon}")
        print(f"XML files: {len(xml_files)}")
        print(f"Sutras parsed: {len(sutras)}")
        print(f"Parse errors: {parse_errors}")
        print(f"Total text: {total_content_len / 1024 / 1024:.1f} MB")
        print(f"Avg text per sutra: {total_content_len / max(len(sutras), 1):.0f} chars")
        if sutras:
            print(f"\nSample titles (first 10):")
            for s in sutras[:10]:
                print(f"  {s['sutra_id']}: {s['title'][:60]} ({len(s['content'])} chars)")
        return

    # Import to database
    import asyncio

    asyncio.run(import_to_db(sutras, args.db_url, args.batch_size))


if __name__ == "__main__":
    main()
