#!/usr/bin/env python3
"""
Batch embed doc_chunks for 佛家/道家 (1.68M chunks, GPU accelerated)

Usage:
    python3 scripts/batch_embed_chunks.py --dry-run
    python3 scripts/batch_embed_chunks.py --category 佛家
    python3 scripts/batch_embed_chunks.py --category 道家
    python3 scripts/batch_embed_chunks.py  # all missing

GPU: ~100 chunks/batch, 0.3s/batch → ~1.4h for 1.68M
CPU: ~18 chunks/s → ~26h for 1.68M
"""

import argparse
import json
import os
import sys
import time
import logging

import psycopg2
import torch
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", os.getenv("DATABASE_URL"))
MODEL_PATH = "/data/models/bge-small-zh"
EMB_API = "http://localhost:8001/embed_batch"
BATCH_SIZE = 256


def get_connection():
    return psycopg2.connect(DB_URL)


def count_missing(conn, category=None):
    cur = conn.cursor()
    if category:
        cur.execute("""
            SELECT COUNT(*) FROM doc_chunks c
            JOIN documents d ON c.doc_id = d.id
            WHERE c.embedding IS NULL AND d.category = %s
        """, (category,))
    else:
        cur.execute("SELECT COUNT(*) FROM doc_chunks WHERE embedding IS NULL")
    return cur.fetchone()[0]


def fetch_batch(conn, category=None, last_id=0, limit=BATCH_SIZE):
    cur = conn.cursor()
    if category:
        cur.execute("""
            SELECT c.id, c.content
            FROM doc_chunks c
            JOIN documents d ON c.doc_id = d.id
            WHERE c.embedding IS NULL AND d.category = %s AND c.id > %s
            ORDER BY c.id
            LIMIT %s
        """, (category, last_id, limit))
    else:
        cur.execute("""
            SELECT id, content FROM doc_chunks
            WHERE embedding IS NULL AND id > %s
            ORDER BY id
            LIMIT %s
        """, (last_id, limit))
    return cur.fetchall()


def update_embeddings(conn, ids, embeddings):
    cur = conn.cursor()
    # Use temp table for batch upsert
    cur.execute("CREATE TEMP TABLE IF NOT EXISTS _emb_tmp (id INT PRIMARY KEY, emb vector(512)) ON COMMIT DROP")
    cur.execute("TRUNCATE _emb_tmp")
    for chunk_id, emb in zip(ids, embeddings):
        emb_str = "[" + ",".join(str(float(v)) for v in emb) + "]"
        cur.execute("INSERT INTO _emb_tmp (id, emb) VALUES (%s, %s::vector)", (chunk_id, emb_str))
    cur.execute("""
        UPDATE doc_chunks d SET embedding = t.emb
        FROM _emb_tmp t
        WHERE d.id = t.id
    """)
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Batch embed doc_chunks")
    parser.add_argument("--category", choices=["佛家", "道家"], help="Only embed specific category")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without embedding")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=0, help="Max chunks to embed (0=unlimited)")
    args = parser.parse_args()

    conn = get_connection()

    missing = count_missing(conn, args.category)
    logger.info(f"Chunks missing embeddings: {missing}")

    if args.category:
        logger.info(f"Category filter: {args.category}")

    if args.dry_run:
        logger.info("Dry run - exiting")
        conn.close()
        return

    if missing == 0:
        logger.info("No chunks to embed")
        conn.close()
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Loading model from {MODEL_PATH} on {device}")
    model = SentenceTransformer(MODEL_PATH).to(device)
    logger.info(f"Model loaded. Device: {device}")

    total_embedded = 0
    start_time = time.time()
    last_id = 0

    while True:
        batch = fetch_batch(conn, args.category, last_id=last_id, limit=args.batch_size)
        if not batch:
            break

        if args.limit > 0 and total_embedded >= args.limit:
            logger.info(f"Reached limit of {args.limit}")
            break

        ids = [row[0] for row in batch]
        texts = [row[1] for row in batch]
        last_id = ids[-1]

        t0 = time.time()
        embeddings = model.encode(texts, batch_size=len(texts), show_progress_bar=False, normalize_embeddings=True)
        emb_time = time.time() - t0

        update_embeddings(conn, ids, embeddings)

        total_embedded += len(ids)
        elapsed = time.time() - start_time
        rate = total_embedded / elapsed if elapsed > 0 else 0
        eta = (missing - total_embedded) / rate if rate > 0 else 0

        logger.info(f"Embedded {total_embedded}/{missing} ({total_embedded/missing*100:.1f}%) "
                     f"| {len(ids)} chunks in {emb_time:.2f}s "
                     f"| {rate:.0f} chunks/s "
                     f"| ETA: {eta/60:.1f}min")

    elapsed = time.time() - start_time
    logger.info(f"Done. {total_embedded} chunks embedded in {elapsed:.1f}s ({total_embedded/elapsed:.0f} chunks/s)")
    conn.close()


if __name__ == "__main__":
    main()
