#!/usr/bin/env python3
"""持续数据导入后台进程

分阶段执行数据补全和导入任务:
  Phase 1: 修复 documents 缺失的 search_vector (FTS) — ~25K 气功文档
  Phase 2: 修复 doc_chunks 缺失的 embedding — ~144 条
  Phase 3: 修复 guji_documents 缺失的 embedding — ~72K 条
  Phase 4: sys_books 内容提取 (TXT优先, 分批) — 智能气功/中医 核心域
  Phase 5: 新导入文档生成 FTS + embedding

用法:
  python scripts/continuous_import.py                 # 全量运行
  python scripts/continuous_import.py --phase 1       # 只运行指定阶段
  python scripts/continuous_import.py --batch-size 500 # 调整批次大小
  python scripts/continuous_import.py --dry-run        # 只显示不执行
  python scripts/continuous_import.py --gpu            # 使用本地 GPU (推荐, 34x更快)
"""

import argparse
import asyncio
import logging
import sys
import time

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("importer")

DB_URL = "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
EMBEDDING_URL = "http://localhost:8001"

BATCH_SIZE = 500


async def get_pool():
    return await asyncpg.create_pool(DB_URL, min_size=2, max_size=4, command_timeout=120)


def _get_gpu_model():
    """加载 GPU 模型 (BGE-small-zh on CUDA)"""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("/data/models/bge-small-zh")
    model = model.to("cuda")
    return model


def _serialize_embedding(emb):
    """将 numpy array 序列化为 pgvector 接受的字符串"""
    return "[" + ",".join(str(x) for x in emb.tolist()) + "]"


async def _embed_and_write_gpu(pool, table, rows, text_fn, model):
    """使用 GPU 批量 embed 并写入 DB"""
    texts = [text_fn(r) for r in rows]
    texts = [t[:500] for t in texts]
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=False)

    ids = [r["id"] for r in rows]
    emb_strs = [_serialize_embedding(emb) for emb in embeddings]

    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE {table} SET embedding = data.vec::vector
            FROM (SELECT unnest($1::int[]) as id, unnest($2::text[]) as vec) as data
            WHERE {table}.id = data.id
            """,
            ids,
            emb_strs,
        )


async def _embed_and_write_cpu(pool, table, rows, text_fn):
    """使用 CPU embedding 服务批量 embed 并写入 DB"""
    import httpx

    texts = [text_fn(r) for r in rows]
    texts = [t[:500] for t in texts]

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{EMBEDDING_URL}/embed_batch",
            json={"texts": texts},
            timeout=120,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"embedding 服务错误: {resp.status_code}")
        embeddings = resp.json().get("embeddings", [])

    async with pool.acquire() as conn:
        for row, emb in zip(rows, embeddings):
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            await conn.execute(
                f"UPDATE {table} SET embedding = $1::vector WHERE id = $2",
                emb_str,
                row["id"],
            )


# ============================================================
# Phase 1: 修复缺失的 search_vector (FTS)
# ============================================================


async def phase1_fix_fts(pool, batch_size, dry_run, **kwargs):
    """为 documents 中 search_vector IS NULL 的行生成 tsvector"""
    log.info("Phase 1: 修复缺失的 search_vector")

    async with pool.acquire() as conn:
        missing = await conn.fetchval(
            "SELECT count(*) FROM documents WHERE search_vector IS NULL"
        )
    if missing == 0:
        log.info("  ✅ 所有文档已有 search_vector")
        return 0

    log.info(f"  缺失 FTS 的文档: {missing}")
    if dry_run:
        return 0

    fixed = 0
    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                UPDATE documents
                SET search_vector = to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(content,''))
                WHERE id IN (
                    SELECT id FROM documents WHERE search_vector IS NULL LIMIT $1
                )
                RETURNING id
                """,
                batch_size,
            )
        if not rows:
            break
        fixed += len(rows)
        log.info(f"  FTS: {fixed}/{missing}")

    log.info(f"  ✅ 修复完成: {fixed} 条文档")
    return fixed


# ============================================================
# Phase 2: 修复 doc_chunks 缺失 embedding
# ============================================================


async def phase2_fix_chunk_embeddings(pool, batch_size, dry_run, use_gpu=False, **kwargs):
    """为 doc_chunks 中 embedding IS NULL 的行生成向量"""
    log.info("Phase 2: 修复 doc_chunks 缺失 embedding")

    async with pool.acquire() as conn:
        missing = await conn.fetchval(
            "SELECT count(*) FROM doc_chunks WHERE embedding IS NULL"
        )
    if missing == 0:
        log.info("  ✅ 所有 doc_chunks 已有 embedding")
        return 0

    log.info(f"  缺失 embedding 的 chunks: {missing}")
    if dry_run:
        return 0

    model = _get_gpu_model() if use_gpu else None
    fixed = 0

    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, content FROM doc_chunks WHERE embedding IS NULL LIMIT $1",
                batch_size,
            )
        if not rows:
            break

        text_fn = lambda r: (r["content"] or "")[:500]

        if use_gpu:
            await _embed_and_write_gpu(pool, "doc_chunks", rows, text_fn, model)
        else:
            await _embed_and_write_cpu(pool, "doc_chunks", rows, text_fn)

        fixed += len(rows)
        log.info(f"  chunk embeddings: {fixed}/{missing}")

    log.info(f"  ✅ 修复完成: {fixed} 条 chunks")
    return fixed


# ============================================================
# Phase 3: 修复 guji_documents 缺失 embedding
# ============================================================


async def phase3_fix_guji_embeddings(pool, batch_size, dry_run, use_gpu=False, **kwargs):
    """为 guji_documents 中 embedding IS NULL 的行生成向量"""
    log.info("Phase 3: 修复 guji_documents 缺失 embedding")

    async with pool.acquire() as conn:
        missing = await conn.fetchval(
            "SELECT count(*) FROM guji_documents WHERE embedding IS NULL"
        )
    if missing == 0:
        log.info("  ✅ 所有 guji_documents 已有 embedding")
        return 0

    log.info(f"  缺失 embedding 的 guji: {missing}")
    if dry_run:
        return 0

    model = _get_gpu_model() if use_gpu else None
    fixed = 0

    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, coalesce(content, '') as content
                FROM guji_documents
                WHERE embedding IS NULL
                ORDER BY id
                LIMIT $1
                """,
                batch_size,
            )
        if not rows:
            break

        text_fn = lambda r: ((r["title"] or "") + " " + (r["content"] or ""))[:500]

        if use_gpu:
            await _embed_and_write_gpu(pool, "guji_documents", rows, text_fn, model)
        else:
            await _embed_and_write_cpu(pool, "guji_documents", rows, text_fn)

        fixed += len(rows)
        pct = fixed * 100 // max(missing, 1)
        log.info(f"  guji embeddings: {fixed}/{missing} ({pct}%)")

    log.info(f"  ✅ 修复完成: {fixed} 条 guji_documents")
    return fixed


# ============================================================
# Phase 4: sys_books 内容提取 (TXT 文件优先)
# ============================================================


async def phase4_extract_sysbooks_txt(pool, batch_size, dry_run, **kwargs):
    """从 sys_books 提取 TXT 文件内容到 sys_book_contents"""
    log.info("Phase 4: sys_books TXT 内容提取")

    core_domains = ("智能气功", "中医", "儒家", "佛家", "道家")

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            """
            SELECT count(*) FROM sys_books
            WHERE extension = 'txt'
              AND domain = ANY($1)
              AND extraction_status = 'pending'
              AND size > 0
            """,
            core_domains,
        )
    if total == 0:
        log.info("  ✅ 核心 TXT 文件已全部提取")
        return 0

    log.info(f"  待提取 TXT 文件 (核心域): {total}")
    if dry_run:
        return 0

    import hashlib
    import os

    fixed = 0
    errors = 0
    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, path, filename, domain
                FROM sys_books
                WHERE extension = 'txt'
                  AND domain = ANY($1)
                  AND extraction_status = 'pending'
                  AND size > 0
                ORDER BY domain, id
                LIMIT $2
                """,
                core_domains,
                batch_size,
            )
        if not rows:
            break

        batch_errors = 0
        async with pool.acquire() as conn:
            for row in rows:
                try:
                    book_path = row["path"].replace("\\", "/")
                    full_path = f"/data/external/{book_path}/{row['filename']}"

                    if not os.path.exists(full_path):
                        batch_errors += 1
                        continue

                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    content_hash = hashlib.md5(content.encode()).hexdigest()

                    await conn.execute(
                        """
                        INSERT INTO sys_book_contents
                            (sys_book_id, content, content_hash, extraction_method, char_count)
                        VALUES ($1, $2, $3, 'txt', $4)
                        ON CONFLICT (sys_book_id) DO UPDATE
                            SET content = $2, content_hash = $3, char_count = $4
                        """,
                        row["id"],
                        content[:1000000],
                        content_hash,
                        len(content),
                    )
                    await conn.execute(
                        """
                        UPDATE sys_books SET extraction_status = 'completed',
                            extracted_at = now(), content_length = $1, content_hash = $2
                        WHERE id = $3
                        """,
                        len(content),
                        content_hash,
                        row["id"],
                    )
                except Exception as e:
                    batch_errors += 1
                    if batch_errors <= 3:
                        log.warning(f"  提取失败 id={row['id']}: {e}")

        fixed += len(rows) - batch_errors
        errors += batch_errors
        log.info(f"  TXT 提取: {fixed}/{total} ({fixed*100//max(total,1)}%) errors={errors}")

    log.info(f"  ✅ TXT 提取完成: {fixed} 成功, {errors} 失败")
    return fixed


# ============================================================
# Phase 5: 检查并补全新导入文档的 FTS + embedding
# ============================================================


async def phase5_ensure_complete(pool, batch_size, dry_run, use_gpu=False, **kwargs):
    """确保所有文档都有 FTS 和 embedding"""
    log.info("Phase 5: 确保文档完整性")

    async with pool.acquire() as conn:
        missing_fts = await conn.fetchval(
            "SELECT count(*) FROM documents WHERE search_vector IS NULL"
        )
        missing_emb = await conn.fetchval(
            "SELECT count(*) FROM documents WHERE embedding IS NULL"
        )

    log.info(f"  缺失 FTS: {missing_fts}, 缺失 embedding: {missing_emb}")

    if missing_fts > 0 and not dry_run:
        await phase1_fix_fts(pool, batch_size, False)

    if missing_emb > 0 and not dry_run:
        log.info("  修复 documents embedding...")
        model = _get_gpu_model() if use_gpu else None
        fixed = 0

        while True:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, coalesce(title,'') || ' ' || coalesce(content,'') as text
                    FROM documents WHERE embedding IS NULL LIMIT $1
                    """,
                    batch_size,
                )
            if not rows:
                break

            text_fn = lambda r: r["text"][:500]

            if use_gpu:
                await _embed_and_write_gpu(pool, "documents", rows, text_fn, model)
            else:
                await _embed_and_write_cpu(pool, "documents", rows, text_fn)

            fixed += len(rows)
            log.info(f"  doc embedding: {fixed}/{missing_emb}")

        log.info(f"  ✅ documents embedding 修复: {fixed}")

    return missing_fts + missing_emb


# ============================================================
# Summary
# ============================================================


async def print_summary(pool):
    log.info("=" * 60)
    log.info("数据导入状态总览:")
    log.info("=" * 60)

    tables_with_embedding = [
        ("documents", "category"),
        ("doc_chunks", None),
        ("guji_documents", None),
        ("guoxue_content", None),
        ("textbook_blocks_v2", None),
    ]
    tables_count_only = [
        "sys_book_contents",
    ]

    async with pool.acquire() as conn:
        for table, _ in tables_with_embedding:
            total = await conn.fetchval(f"SELECT count(*) FROM {table}")
            has_emb = await conn.fetchval(
                f"SELECT count(*) FROM {table} WHERE embedding IS NOT NULL"
            )
            log.info(f"  {table:<25} total={total:>10,}  embedding={has_emb:>10,}")

        for table in tables_count_only:
            total = await conn.fetchval(f"SELECT count(*) FROM {table}")
            log.info(f"  {table:<25} total={total:>10,}")

        fts_total = await conn.fetchval(
            "SELECT count(*) FROM documents WHERE search_vector IS NOT NULL"
        )
        log.info(f"  {'documents FTS':<25} {fts_total:>10,}")

        extracted = await conn.fetchval(
            "SELECT count(*) FROM sys_books WHERE extraction_status = 'completed'"
        )
        log.info(f"  {'sys_books extracted':<25} {extracted:>10,} / 3,024,429")

    log.info("=" * 60)


# ============================================================
# Main
# ============================================================


async def main():
    parser = argparse.ArgumentParser(description="持续数据导入")
    parser.add_argument("--phase", type=int, default=None, help="只运行指定阶段 (1-5)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="批次大小")
    parser.add_argument("--dry-run", action="store_true", help="只显示统计不执行")
    parser.add_argument("--gpu", action="store_true", help="使用本地 GPU (CUDA) 做 embedding")
    parser.add_argument("--loop", action="store_true", help="循环运行模式")
    parser.add_argument("--interval", type=int, default=300, help="循环间隔(秒)")
    args = parser.parse_args()

    log.info("智能知识系统 — 持续数据导入")
    log.info(f"  batch_size={args.batch_size}  gpu={args.gpu}  dry_run={args.dry_run}")

    pool = await get_pool()

    phases = [
        ("FTS修复", phase1_fix_fts),
        ("chunk embedding", phase2_fix_chunk_embeddings),
        ("guji embedding", phase3_fix_guji_embeddings),
        ("sys_books TXT提取", phase4_extract_sysbooks_txt),
        ("完整性检查", phase5_ensure_complete),
    ]

    while True:
        await print_summary(pool)

        if args.phase:
            name, fn = phases[args.phase - 1]
            log.info(f"\n▶ 运行阶段 {args.phase}: {name}")
            t0 = time.perf_counter()
            await fn(pool, args.batch_size, args.dry_run, use_gpu=args.gpu)
            log.info(f"  耗时: {time.perf_counter()-t0:.1f}s")
        else:
            for i, (name, fn) in enumerate(phases):
                log.info(f"\n▶ 阶段 {i+1}/{len(phases)}: {name}")
                t0 = time.perf_counter()
                try:
                    await fn(pool, args.batch_size, args.dry_run, use_gpu=args.gpu)
                except Exception as e:
                    log.error(f"  阶段 {i+1} 失败: {e}", exc_info=True)
                log.info(f"  耗时: {time.perf_counter()-t0:.1f}s")

        await print_summary(pool)

        if not args.loop:
            break

        log.info(f"\n⏳ 等待 {args.interval}s 后进入下一轮...")
        await asyncio.sleep(args.interval)

    await pool.close()
    log.info("导入完成")


if __name__ == "__main__":
    asyncio.run(main())
