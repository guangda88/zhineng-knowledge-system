#!/usr/bin/env python3
"""
GPU embedding backfill script.
Reads chunks without embeddings, generates them on CUDA, writes back.
Batch processing with progress reporting.
"""

import asyncio
import asyncpg
import numpy as np
import sys
import time
import os

os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL"))
os.environ.setdefault("TRANSFORMERS_ATTN_IMPLEMENTATION", "eager")
os.environ.setdefault("PYTORCH_NO_CUDA_MEMORY_CACHING", "1")
os.environ.setdefault("PYTORCH_NVML_BASED_CUDA_CHECK", "0")

BATCH_SIZE = 200
EMBEDDING_DIM = 512
MODEL_PATH = "/data/models/bge-small-zh"
DB_URL = os.environ["DATABASE_URL"]


def get_category_from_args():
    if len(sys.argv) > 1:
        return sys.argv[1]
    return None


async def get_chunks_without_embedding(conn, category=None, limit=None):
    if category:
        query = """
            SELECT dc.id, dc.content
            FROM doc_chunks dc
            JOIN documents d ON dc.doc_id = d.id
            WHERE dc.embedding IS NULL AND d.category = $1
            ORDER BY dc.id
        """
        args = [category]
    else:
        query = """
            SELECT dc.id, dc.content
            FROM doc_chunks dc
            WHERE dc.embedding IS NULL
            ORDER BY dc.id
        """
        args = []

    if limit:
        query += f" LIMIT {limit}"

    return await conn.fetch(query, *args)


async def update_embeddings(conn, chunk_ids, embeddings):
    if not chunk_ids:
        return
    vecs = ["[" + ",".join(f"{v:.6f}" for v in emb) + "]" for emb in embeddings]
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE doc_chunks d SET embedding = v.vec::vector
            FROM (SELECT unnest($1::bigint[]) as id, unnest($2::text[]) as vec) v
            WHERE d.id = v.id
            """,
            chunk_ids,
            vecs,
        )


async def main():
    category = get_category_from_args()
    print(f"=== Embedding Backfill ===", flush=True)
    print(f"Category: {category or 'ALL'}", flush=True)

    from sentence_transformers import SentenceTransformer
    import torch
    import transformers.models.bert.modeling_bert as bert_mod

    force_cpu = os.environ.get("FORCE_CPU", "0") == "1"
    device = "cpu" if force_cpu else ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}", flush=True)

    if device == "cuda":
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_mem_efficient_sdp(False)
        _orig_bert_fwd = bert_mod.BertSelfAttention.forward
        def _patched_bert_fwd(self, hidden_states, attention_mask=None, head_mask=None,
                              encoder_hidden_states=None, encoder_attention_mask=None,
                              past_key_value=None, output_attentions=False):
            with torch.backends.cuda.sdp_kernel(enable_flash=False, enable_mem_efficient=False, enable_math=True):
                return _orig_bert_fwd(self, hidden_states, attention_mask, head_mask,
                                     encoder_hidden_states, encoder_attention_mask,
                                     past_key_value, output_attentions)
        bert_mod.BertSelfAttention.forward = _patched_bert_fwd

    model = SentenceTransformer(MODEL_PATH).to(device)
    print(f"Model loaded: {MODEL_PATH}", flush=True)

    conn = await asyncpg.connect(DB_URL)
    print(f"DB connected", flush=True)

    total_start = time.time()
    total_updated = 0
    batch_num = 0

    while True:
        rows = await get_chunks_without_embedding(conn, category, limit=BATCH_SIZE)
        if not rows:
            print(f"\nDone. Total: {total_updated} chunks in {time.time()-total_start:.1f}s", flush=True)
            break

        chunk_ids = [r["id"] for r in rows]
        texts = [r["content"] for r in rows]

        t0 = time.time()
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
        encode_time = time.time() - t0

        t0 = time.time()
        await update_embeddings(conn, chunk_ids, embeddings)
        db_time = time.time() - t0

        total_updated += len(chunk_ids)
        batch_num += 1
        remaining = await conn.fetchval(
            """
            SELECT COUNT(*) FROM doc_chunks dc
            JOIN documents d ON dc.doc_id = d.id
            WHERE dc.embedding IS NULL AND ($1::text IS NULL OR d.category = $1)
            """,
            category,
        )

        elapsed = time.time() - total_start
        rate = total_updated / elapsed if elapsed > 0 else 0
        eta = remaining / rate if rate > 0 else 0

        print(
            f"  Batch {batch_num}: {len(chunk_ids)} chunks "
            f"(encode={encode_time:.1f}s, db={db_time:.1f}s) "
            f"| Total: {total_updated} | Remaining: {remaining} "
            f"| Rate: {rate:.0f}/s | ETA: {eta/60:.1f}min",
            flush=True,
        )

    await conn.close()
    print(f"=== Complete: {total_updated} embeddings backfilled ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
