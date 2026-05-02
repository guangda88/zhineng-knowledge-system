#!/usr/bin/env python3
"""
苏颂研究 — 数据补全脚本
1. Heavenly_Clockwork 分段 + 补嵌入
2. 古籍 OCR 文本入库（道光本、年表、目录）
3. 批量嵌入生成（GPU CUDA）

用法:
    python scripts/susong_data_completion.py --all
    python scripts/susong_data_completion.py --chunk-only    # 只分段，不嵌入
    python scripts/susong_data_completion.py --embed-only    # 只嵌入（对已存在但缺嵌入的）
"""

import argparse
import asyncio
import os
import sys
import time

import asyncpg
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_DSN = "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "susong_import")

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200
EMBED_BATCH_SIZE = 64

# Files to import into DB (OCR texts that haven't been imported yet)
OCR_FILES = [
    {
        "path": os.path.join(DATA_DIR, "道光本", "GJ27471-1.ocr.txt"),
        "title": "苏魏公文集·道光本·第1册(卷前~目录)",
        "category": "儒家",
        "tags": ["苏颂研究", "苏魏公文集", "道光本"],
    },
    {
        "path": os.path.join(DATA_DIR, "道光本", "GJ27471-2.ocr.txt"),
        "title": "苏魏公文集·道光本·第2册",
        "category": "儒家",
        "tags": ["苏颂研究", "苏魏公文集", "道光本"],
    },
    {
        "path": os.path.join(DATA_DIR, "苏颂年表.ocr.txt"),
        "title": "苏颂年表",
        "category": "哲学",
        "tags": ["苏颂研究", "生平年考", "年表"],
    },
    {
        "path": os.path.join(DATA_DIR, "目录_苏魏公文集.ocr.txt"),
        "title": "苏魏公文集目录",
        "category": "儒家",
        "tags": ["苏颂研究", "苏魏公文集", "目录"],
    },
]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if end < len(text):
            last_period = max(
                chunk.rfind("。"),
                chunk.rfind("，"),
                chunk.rfind("；"),
                chunk.rfind("\n"),
                chunk.rfind(". "),
            )
            if last_period > chunk_size // 2:
                chunk = chunk[: last_period + 1]
                end = start + last_period + 1

        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(text) else end

    return chunks


def load_embedding_model():
    import torch
    from sentence_transformers import SentenceTransformer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_path = "/data/models/bge-small-zh"
    if not os.path.exists(model_path):
        model_path = "BAAI/bge-small-zh-v1.5"
    log(f"Loading embedding model: {model_path} on {device}")
    model = SentenceTransformer(model_path, device=device)
    return model


def generate_embeddings(model, texts):
    embeddings = model.encode(texts, batch_size=EMBED_BATCH_SIZE, show_progress_bar=True)
    return embeddings


async def chunk_heavenly_clockwork(pool):
    """Split Heavenly_Clockwork into chunks and re-insert."""
    log("=== Step 1: Chunking Heavenly_Clockwork ===")

    row = await pool.fetchrow(
        "SELECT id, title, content, category, tags FROM documents WHERE id = 354101"
    )
    if not row:
        log("  Heavenly_Clockwork not found, skipping")
        return

    content = row["content"]
    category = row["category"]
    tags = row["tags"]
    log(f"  Original: {len(content)} chars")

    chunks = chunk_text(content)
    log(f"  Split into {len(chunks)} chunks")

    inserted = 0
    for i, chunk in enumerate(chunks):
        title = f"Heavenly_Clockwork·Part{i + 1:03d}" if len(chunks) > 1 else "Heavenly_Clockwork"
        chunk_tags = list(tags) + [f"Part{i + 1}"] if len(chunks) > 1 else list(tags)

        doc_id = await pool.fetchval(
            """INSERT INTO documents (title, content, category, tags, source_file)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT DO NOTHING
               RETURNING id""",
            title, chunk, category, chunk_tags, "Heavenly_Clockwork.txt",
        )
        if doc_id:
            inserted += 1
            log(f"  [{i + 1}/{len(chunks)}] Inserted: {title} ({len(chunk)} chars) -> ID {doc_id}")
        else:
            log(f"  [{i + 1}/{len(chunks)}] Exists: {title}")

    await pool.execute("DELETE FROM documents WHERE id = 354101")
    log(f"  Deleted original record (ID 354101)")
    log(f"  Chunked: {inserted} new records")
    return inserted


async def import_ocr_texts(pool):
    """Import OCR text files into documents table."""
    log("=== Step 2: Importing OCR texts ===")
    total = 0

    for entry in OCR_FILES:
        path = entry["path"]
        if not os.path.exists(path):
            log(f"  SKIP (not found): {path}")
            continue

        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        if not text or len(text.strip()) < 50:
            log(f"  SKIP (too short): {entry['title']}")
            continue

        log(f"  {entry['title']}: {len(text)} chars")

        chunks = chunk_text(text)
        log(f"    Split into {len(chunks)} chunks")

        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                title = f"{entry['title']}·Part{i + 1:03d}"
                tags = list(entry["tags"]) + [f"Part{i + 1}"]
            else:
                title = entry["title"]
                tags = entry["tags"]

            doc_id = await pool.fetchval(
                """INSERT INTO documents (title, content, category, tags, source_file)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT DO NOTHING
                   RETURNING id""",
                title, chunk, entry["category"], tags, os.path.basename(path),
            )
            if doc_id:
                total += 1
                log(f"    [{i + 1}/{len(chunks)}] Inserted: {title} -> ID {doc_id}")
            else:
                log(f"    [{i + 1}/{len(chunks)}] Exists: {title}")

    log(f"  Imported: {total} new records")
    return total


async def embed_missing(pool, model=None):
    """Generate embeddings for documents tagged 苏颂研究 that lack them."""
    log("=== Step 3: Generating embeddings ===")

    rows = await pool.fetch(
        """SELECT id, content FROM documents
           WHERE embedding IS NULL
           AND ('苏颂研究' = ANY(tags) OR source_file LIKE '%susong%' OR source_file LIKE '%Heavenly%')
           ORDER BY id"""
    )
    log(f"  Found {len(rows)} documents without embeddings")

    if not rows:
        return 0

    if model is None:
        model = load_embedding_model()

    total = 0
    batch_size = EMBED_BATCH_SIZE

    for batch_start in range(0, len(rows), batch_size):
        batch = rows[batch_start:batch_start + batch_size]
        texts = [r["content"] for r in batch]
        ids = [r["id"] for r in batch]

        embeddings = generate_embeddings(model, texts)

        for doc_id, emb in zip(ids, embeddings):
            emb_str = "[" + ",".join(f"{v:.6f}" for v in emb) + "]"
            await pool.execute(
                "UPDATE documents SET embedding = $1::vector WHERE id = $2",
                emb_str, doc_id,
            )
            total += 1

        log(f"  Embedded {total}/{len(rows)}")

    log(f"  Total embedded: {total}")
    return total


async def run_all(do_chunk=True, do_import=True, do_embed=True):
    pool = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=5)
    model = None

    try:
        if do_embed:
            model = load_embedding_model()

        if do_chunk:
            await chunk_heavenly_clockwork(pool)

        if do_import:
            await import_ocr_texts(pool)

        if do_embed:
            await embed_missing(pool, model)

        log("=== Done ===")
    finally:
        await pool.close()


async def embed_only():
    pool = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=5)
    try:
        model = load_embedding_model()
        await embed_missing(pool, model)
    finally:
        await pool.close()


async def chunk_only():
    pool = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=5)
    try:
        await chunk_heavenly_clockwork(pool)
        await import_ocr_texts(pool)
    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser(description="苏颂研究数据补全")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="执行全部步骤（分段+导入+嵌入）")
    group.add_argument("--chunk-only", action="store_true", help="只分段和导入，不嵌入")
    group.add_argument("--embed-only", action="store_true", help="只补嵌入")
    args = parser.parse_args()

    if args.all:
        asyncio.run(run_all(do_chunk=True, do_import=True, do_embed=True))
    elif args.chunk_only:
        asyncio.run(chunk_only())
    elif args.embed_only:
        asyncio.run(embed_only())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
