#!/usr/bin/env python3
"""
Universal GPU embedding backfill — supports all tables with embedding column.
Runs on host with CUDA. Usage:
  python gpu_backfill.py                          # all tables
  python gpu_backfill.py doc_chunks               # single table
  python gpu_backfill.py --dry-run                # report only
  python gpu_backfill.py --batch-size 512         # custom batch
"""

import asyncio
import asyncpg
import sys
import time
import os

os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL"))
os.environ.setdefault("TRANSFORMERS_ATTN_IMPLEMENTATION", "eager")
os.environ.setdefault("PYTORCH_NO_CUDA_MEMORY_CACHING", "1")
os.environ.setdefault("PYTORCH_NVML_BASED_CUDA_CHECK", "0")

DB_URL = os.environ["DATABASE_URL"]
MODEL_PATH = "/data/models/bge-small-zh"

TABLE_TEXT_COLUMNS = {
    "doc_chunks": "content",
    "documents": "content",
    "documents_new": "content",
    "guoxue_content": "body",
    "guji_documents": "content",
    "qigong_knowledge": "content",
    "sys_book_chunks": "content",
    "textbook_blocks": "content",
    "textbook_blocks_v2": "content",
    "audio_segments": "text",
    "books": "title",
    "corrections": "context",
}

TABLE_TITLE_COLUMNS = {
    "documents": "title",
    "documents_new": "title",
    "guji_documents": "title",
    "qigong_knowledge": "title",
    "books": "title",
}


def parse_args():
    args = sys.argv[1:]
    table = None
    batch_size = 200
    dry_run = False
    for a in args:
        if a == "--dry-run":
            dry_run = True
        elif a.startswith("--batch-size="):
            batch_size = int(a.split("=")[1])
        elif not a.startswith("-"):
            table = a
    return table, batch_size, dry_run


async def get_missing_count(conn, table, text_col):
    return await conn.fetchval(
        f"SELECT COUNT(*) FROM {table} WHERE embedding IS NULL AND {text_col} IS NOT NULL"
    )


async def get_missing_rows(conn, table, text_col, title_col, limit):
    if title_col:
        query = f"""
            SELECT id, {text_col}, {title_col}
            FROM {table}
            WHERE embedding IS NULL AND {text_col} IS NOT NULL
            ORDER BY id LIMIT {limit}
        """
    else:
        query = f"""
            SELECT id, {text_col}
            FROM {table}
            WHERE embedding IS NULL AND {text_col} IS NOT NULL
            ORDER BY id LIMIT {limit}
        """
    return await conn.fetch(query)


async def update_embeddings(conn, table, chunk_ids, embeddings):
    vecs = ["[" + ",".join(f"{v:.6f}" for v in emb) + "]" for emb in embeddings]
    async with conn.transaction():
        await conn.execute(
            f"""
            UPDATE {table} t SET embedding = v.vec::vector
            FROM (SELECT unnest($1::bigint[]) as id, unnest($2::text[]) as vec) v
            WHERE t.id = v.id
            """,
            chunk_ids,
            vecs,
        )


async def backfill_table(conn, model, table, batch_size):
    text_col = TABLE_TEXT_COLUMNS.get(table)
    title_col = TABLE_TITLE_COLUMNS.get(table)
    if not text_col:
        print(f"  SKIP {table}: no text column mapped", flush=True)
        return 0

    missing = await get_missing_count(conn, table, text_col)
    if missing == 0:
        print(f"  {table}: ✅ no missing embeddings", flush=True)
        return 0

    print(f"  {table}: {missing} missing embeddings, backfilling...", flush=True)
    total_updated = 0
    batch_num = 0

    while True:
        rows = await get_missing_rows(conn, table, text_col, title_col, batch_size)
        if not rows:
            break

        chunk_ids = [r["id"] for r in rows]
        texts = []
        for r in rows:
            t = r[text_col] or ""
            if title_col and r.get(title_col):
                t = r[title_col] + " " + t
            texts.append(t)

        t0 = time.time()
        embeddings = model.encode(texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True)
        encode_time = time.time() - t0

        t0 = time.time()
        await update_embeddings(conn, table, chunk_ids, embeddings)
        db_time = time.time() - t0

        total_updated += len(chunk_ids)
        batch_num += 1
        print(
            f"    Batch {batch_num}: {len(chunk_ids)} "
            f"(encode={encode_time:.1f}s, db={db_time:.1f}s) "
            f"| Total: {total_updated}/{missing}",
            flush=True,
        )

    print(f"  {table}: ✅ {total_updated} embeddings backfilled", flush=True)
    return total_updated


async def main():
    target_table, batch_size, dry_run = parse_args()
    print(f"=== GPU Embedding Backfill ===", flush=True)
    print(f"Device: CUDA | Batch: {batch_size} | Dry-run: {dry_run}", flush=True)

    from sentence_transformers import SentenceTransformer
    import torch
    import transformers.models.bert.modeling_bert as bert_mod

    force_cpu = os.environ.get("FORCE_CPU", "0") == "1"
    device = "cpu" if force_cpu else ("cuda" if torch.cuda.is_available() else "cpu")

    if device == "cuda":
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_mem_efficient_sdp(False)
        _orig = bert_mod.BertSelfAttention.forward

        def _patched(self, hidden_states, attention_mask=None, head_mask=None,
                     encoder_hidden_states=None, encoder_attention_mask=None,
                     past_key_value=None, output_attentions=False):
            with torch.backends.cuda.sdp_kernel(enable_flash=False, enable_mem_efficient=False, enable_math=True):
                return _orig(self, hidden_states, attention_mask, head_mask,
                             encoder_hidden_states, encoder_attention_mask,
                             past_key_value, output_attentions)

        bert_mod.BertSelfAttention.forward = _patched

    model = SentenceTransformer(MODEL_PATH).to(device)
    print(f"Model: {MODEL_PATH} on {device}", flush=True)

    conn = await asyncpg.connect(DB_URL)

    tables = [target_table] if target_table else list(TABLE_TEXT_COLUMNS.keys())
    total_start = time.time()
    grand_total = 0

    for table in tables:
        if dry_run:
            text_col = TABLE_TEXT_COLUMNS.get(table, "?")
            missing = await get_missing_count(conn, table, text_col) if text_col != "?" else -1
            print(f"  {table}: {missing} missing (text_col={text_col})", flush=True)
        else:
            updated = await backfill_table(conn, model, table, batch_size)
            grand_total += updated

    await conn.close()
    elapsed = time.time() - total_start
    print(f"=== Done: {grand_total} embeddings in {elapsed:.1f}s ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
