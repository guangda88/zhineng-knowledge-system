#!/usr/bin/env python3
"""
ai01 remote GPU embedding worker.
Connects to zhineng_kb on zhineng-ai via pgbouncer or direct connection.
Processes embedding backfill tasks autonomously.

ai01 setup:
1. rsync -av /data/models/bge-small-zh ai01:/data/models/bge-small-zh
2. pip install sentence-transformers asyncpg torch
3. export DATABASE_URL=os.getenv("DATABASE_URL")
4. python3 ai01_embedding_worker.py [--table doc_chunks] [--batch-size 500]
"""

import asyncio
import asyncpg
import sys
import time
import os
import socket

os.environ.setdefault("TRANSFORMERS_ATTN_IMPLEMENTATION", "eager")
os.environ.setdefault("PYTORCH_NO_CUDA_MEMORY_CACHING", "1")
os.environ.setdefault("PYTORCH_NVML_BASED_CUDA_CHECK", "0")

MODEL_PATH = os.getenv("EMBEDDING_MODEL", "/data/models/bge-small-zh")
DB_URL = os.getenv("DATABASE_URL", os.getenv("DATABASE_URL"))
HOSTNAME = socket.gethostname()
BATCH_SIZE = 500

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

PRIORITY_ORDER = [
    "doc_chunks",
    "documents",
    "documents_new",
    "guoxue_content",
    "guji_documents",
    "qigong_knowledge",
    "sys_book_chunks",
    "textbook_blocks",
    "textbook_blocks_v2",
    "audio_segments",
    "books",
    "corrections",
]


def parse_args():
    args = sys.argv[1:]
    table = None
    batch_size = BATCH_SIZE
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


async def backfill_table(conn, model, table, batch_size, device):
    text_col = TABLE_TEXT_COLUMNS.get(table)
    title_col = TABLE_TITLE_COLUMNS.get(table)
    if not text_col:
        return 0

    missing = await get_missing_count(conn, table, text_col)
    if missing == 0:
        print(f"  {table}: ✅ no missing", flush=True)
        return 0

    print(f"  {table}: {missing} missing, processing (batch={batch_size})...", flush=True)
    total = 0
    batch_num = 0

    while True:
        cols = f"id, {text_col}"
        if title_col:
            cols += f", {title_col}"
        rows = await conn.fetch(
            f"SELECT {cols} FROM {table} "
            f"WHERE embedding IS NULL AND {text_col} IS NOT NULL "
            f"ORDER BY id LIMIT {batch_size}"
        )
        if not rows:
            break

        ids = [r["id"] for r in rows]
        texts = []
        for r in rows:
            t = r[text_col] or ""
            if title_col and r.get(title_col):
                t = r[title_col] + " " + t
            texts.append(t)

        t0 = time.time()
        embs = model.encode(texts, batch_size=128, show_progress_bar=False, normalize_embeddings=True)
        enc_time = time.time() - t0

        vecs = ["[" + ",".join(f"{v:.6f}" for v in e) + "]" for e in embs]
        t0 = time.time()
        async with conn.transaction():
            await conn.execute(
                f"""UPDATE {table} t SET embedding = v.vec::vector
                    FROM (SELECT unnest($1::bigint[]) as id, unnest($2::text[]) as vec) v
                    WHERE t.id = v.id""",
                ids, vecs,
            )
        db_time = time.time() - t0

        total += len(ids)
        batch_num += 1
        rate = total / (time.time() - t0 + 0.001)
        print(
            f"    Batch {batch_num}: {len(ids)} "
            f"(enc={enc_time:.2f}s db={db_time:.2f}s) "
            f"Total: {total}/{missing} Rate: {len(ids)/enc_time:.0f}/s",
            flush=True,
        )

    print(f"  {table}: ✅ {total} done", flush=True)
    return total


async def main():
    target_table, batch_size, dry_run = parse_args()
    import torch

    print(f"=== ai01 Embedding Worker ===", flush=True)
    print(f"Host: {HOSTNAME} | GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE'}", flush=True)
    print(f"CUDA: {torch.cuda.is_available()} | DB: {DB_URL.split('@')[-1]}", flush=True)

    from sentence_transformers import SentenceTransformer
    import transformers.models.bert.modeling_bert as bert_mod

    device = "cuda" if torch.cuda.is_available() else "cpu"
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
    print(f"Model: {MODEL_PATH} ({device}) dim={model.get_sentence_embedding_dimension()}", flush=True)

    conn = await asyncpg.connect(DB_URL)

    tables = [target_table] if target_table else PRIORITY_ORDER
    t0 = time.time()
    grand = 0

    for table in tables:
        if dry_run:
            text_col = TABLE_TEXT_COLUMNS.get(table)
            if text_col:
                missing = await get_missing_count(conn, table, text_col)
                print(f"  {table}: {missing} missing", flush=True)
        else:
            grand += await backfill_table(conn, model, table, batch_size, device)

    await conn.close()
    print(f"=== Done: {grand} embeddings in {time.time()-t0:.1f}s ({HOSTNAME}) ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
