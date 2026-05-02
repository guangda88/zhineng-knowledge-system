#!/usr/bin/env python3
"""
检索性能基准测试 — 直接数据库层 + API 层
不依赖 backend 模块，直接用 asyncpg 和 httpx 测量。

用法:
  python scripts/bench_retrieval.py              # 完整测试
  python scripts/bench_retrieval.py --quick       # 快速模式
  python scripts/bench_retrieval.py --explain     # 只跑 EXPLAIN ANALYZE
"""

import argparse
import asyncio
import json
import os
import statistics
import time
from typing import Dict, List, Optional

import asyncpg

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb",
)


def _pct(data: List[float], pct: int) -> Optional[float]:
    if not data:
        return None
    s = sorted(data)
    return s[int(len(s) * pct / 100)]


def fmt(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    return f"{val:.1f}ms" if val >= 1 else f"{val:.3f}ms"


def print_result(name: str, samples: List[float], errors: int = 0):
    if not samples:
        print(f"  {name}: 无数据 (errors={errors})")
        return
    print(
        f"  {name}\n"
        f"    n={len(samples)}  err={errors}  "
        f"min={fmt(min(samples))}  p50={fmt(_pct(samples, 50))}  "
        f"p90={fmt(_pct(samples, 90))}  p95={fmt(_pct(samples, 95))}  "
        f"p99={fmt(_pct(samples, 99))}  max={fmt(max(samples))}  "
        f"mean={fmt(statistics.mean(samples))}"
    )


async def get_sample_embedding(pool: asyncpg.Pool, table: str) -> Optional[str]:
    row = await pool.fetchval(
        f"SELECT embedding FROM {table} WHERE embedding IS NOT NULL LIMIT 1"
    )
    return str(row) if row else None


# ============================================================
# 1. 向量搜索
# ============================================================


async def bench_vector(conn, table: str, emb: str, iters: int) -> List[float]:
    times = []
    for _ in range(iters):
        t0 = time.perf_counter()
        await conn.fetch(
            f"""
            SELECT id, 1 - (embedding <=> $1::vector) as sim
            FROM {table}
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT 10
            """,
            emb,
        )
        times.append((time.perf_counter() - t0) * 1000)
    return times


# ============================================================
# 2. BM25 搜索
# ============================================================


async def bench_bm25(conn, table: str, query_text: str, iters: int) -> List[float]:
    times = []
    for _ in range(iters):
        t0 = time.perf_counter()
        await conn.fetch(
            f"""
            SELECT id, ts_rank_cd(search_vector, query) AS score
            FROM {table}, plainto_tsquery('simple', $1) query
            WHERE search_vector @@ query
            ORDER BY score DESC
            LIMIT 10
            """,
            query_text,
        )
        times.append((time.perf_counter() - t0) * 1000)
    return times


# ============================================================
# 3. 并行搜索（模拟 hybrid）
# ============================================================


async def bench_parallel_vector(pool, emb: str, iters: int) -> List[float]:
    tables = ["documents", "guoxue_content", "textbook_blocks_v2", "doc_chunks"]
    times = []

    async def _search(tbl):
        async with pool.acquire() as c:
            return await c.fetch(
                """
                SELECT id, 1 - (embedding <=> $1::vector) as sim
                FROM {} WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector LIMIT 10
                """.format(tbl),
                emb,
            )

    for _ in range(iters):
        t0 = time.perf_counter()
        await asyncio.gather(*[_search(t) for t in tables])
        times.append((time.perf_counter() - t0) * 1000)
    return times


async def bench_parallel_bm25(pool, query_text: str, iters: int) -> List[float]:
    tables = ["documents", "guoxue_content", "doc_chunks"]
    times = []

    async def _search(tbl):
        async with pool.acquire() as c:
            return await c.fetch(
                """
                SELECT id, ts_rank_cd(search_vector, q) AS score
                FROM {}, plainto_tsquery('simple', $1) q
                WHERE search_vector @@ q
                ORDER BY score DESC LIMIT 10
                """.format(tbl),
                query_text,
            )

    for _ in range(iters):
        t0 = time.perf_counter()
        await asyncio.gather(*[_search(t) for t in tables])
        times.append((time.perf_counter() - t0) * 1000)
    return times


# ============================================================
# 4. Embedding 生成
# ============================================================


async def bench_embedding(iters: int) -> tuple:
    import httpx

    text = "智能气功的混元气理论是庞明教授提出的整体生命观"
    single_times = []
    batch_times = []
    single_err = 0
    batch_err = 0

    async with httpx.AsyncClient() as client:
        # 单条
        for _ in range(iters):
            t0 = time.perf_counter()
            resp = await client.post(
                "http://localhost:8001/embed", json={"text": text}, timeout=30
            )
            ms = (time.perf_counter() - t0) * 1000
            if resp.status_code == 200:
                single_times.append(ms)
            else:
                single_err += 1

        # 批量10条
        texts = [text] * 10
        for _ in range(iters):
            t0 = time.perf_counter()
            resp = await client.post(
                "http://localhost:8001/embed_batch", json={"texts": texts}, timeout=30
            )
            ms = (time.perf_counter() - t0) * 1000
            if resp.status_code == 200:
                batch_times.append(ms)
            else:
                batch_err += 1

    return single_times, single_err, batch_times, batch_err


# ============================================================
# 5. EXPLAIN ANALYZE
# ============================================================


async def run_explain(conn, label: str, sql: str) -> dict:
    try:
        row = await conn.fetchval(sql)
        if isinstance(row, str):
            row = json.loads(row)
        plan = row[0] if isinstance(row, list) else row
        p = plan.get("Plan", {})
        return {
            "label": label,
            "exec_ms": round(plan.get("Execution Time", 0), 2),
            "plan_ms": round(plan.get("Planning Time", 0), 2),
            "node": p.get("Node Type"),
            "index": p.get("Index Name"),
            "rows": p.get("Actual Rows"),
            "cost": round(p.get("Total Cost", 0), 2),
            "shared_hit": p.get("Shared Hit Blocks"),
            "shared_read": p.get("Shared Read Blocks"),
            "read_time_ms": round(p.get("I/O Read Time", 0), 2),
        }
    except Exception as e:
        return {"label": label, "error": str(e)}


# ============================================================
# 6. IO 统计
# ============================================================


async def get_io_stats(pool) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT relname as tbl,
                   round(100.0 * heap_blks_hit / nullif(heap_blks_hit + heap_blks_read, 0), 1) as heap_hit_pct,
                   round(100.0 * idx_blks_hit / nullif(idx_blks_hit + idx_blks_read, 0), 1) as idx_hit_pct,
                   heap_blks_read + heap_blks_hit as heap_total,
                   idx_blks_read + idx_blks_hit as idx_total
            FROM pg_statio_user_tables
            WHERE relname IN ('documents','guoxue_content','doc_chunks',
                              'textbook_blocks_v2','sys_books','guji_documents')
            ORDER BY relname
            """
        )
        return [dict(r) for r in rows]


# ============================================================
# 7. 并发吞吐
# ============================================================


async def bench_concurrent(pool, emb: str, concurrency: int, total: int) -> dict:
    sem = asyncio.Semaphore(concurrency)
    times = []
    errors = 0

    async def _q():
        nonlocal errors
        async with sem:
            t0 = time.perf_counter()
            try:
                async with pool.acquire() as c:
                    await c.fetch(
                        """
                        SELECT id FROM documents
                        WHERE embedding IS NOT NULL
                        ORDER BY embedding <=> $1::vector LIMIT 10
                        """,
                        emb,
                    )
            except Exception:
                errors += 1
            times.append((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    await asyncio.gather(*[_q() for _ in range(total)])
    wall = (time.perf_counter() - t0) * 1000

    return {
        "concurrency": concurrency,
        "total": total,
        "qps": round(total / (wall / 1000), 1),
        "wall_ms": round(wall, 0),
        "p50": _pct(times, 50),
        "p95": _pct(times, 95),
        "p99": _pct(times, 99),
        "errors": errors,
    }


# ============================================================
# 8. API 端到端
# ============================================================


async def bench_api(endpoint: str, payload: dict, iters: int) -> tuple:
    import httpx

    times = []
    errors = 0
    async with httpx.AsyncClient() as client:
        for _ in range(iters):
            t0 = time.perf_counter()
            try:
                resp = await client.post(endpoint, json=payload, timeout=60)
                ms = (time.perf_counter() - t0) * 1000
                times.append(ms)
                if resp.status_code != 200:
                    errors += 1
            except Exception:
                errors += 1
                times.append((time.perf_counter() - t0) * 1000)
    return times, errors


# ============================================================
# 主函数
# ============================================================


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--iters", type=int, default=None)
    args = parser.parse_args()

    iters = args.iters or (5 if args.quick else 20)

    print("=" * 72)
    print("  智能知识系统 — 检索性能基准测试")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  存储: HDD (sda1)  |  迭代: {iters}  |  模式: {'快速' if args.quick else '标准'}")
    print("=" * 72)

    pool = await asyncpg.create_pool(DB_URL, min_size=4, max_size=20, command_timeout=60)

    try:
        # 准备 embedding
        async with pool.acquire() as conn:
            emb = await conn.fetchval(
                "SELECT embedding FROM documents WHERE embedding IS NOT NULL LIMIT 1"
            )
            emb_str = str(emb)
            print(f"\n  采样 embedding: OK (dim={len(emb.to_list()) if hasattr(emb, 'to_list') else '?'})")

        if args.explain:
            print("\n## EXPLAIN ANALYZE ##\n")
            async with pool.acquire() as conn:
                tests = [
                    ("向量搜索 documents (HNSW)", f"""
                        EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                        SELECT id FROM documents WHERE embedding IS NOT NULL
                        ORDER BY embedding <=> '{emb_str}'::vector LIMIT 10
                    """),
                    ("向量搜索 guoxue_content (HNSW, 26万行)", f"""
                        EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                        SELECT id FROM guoxue_content WHERE embedding IS NOT NULL
                        ORDER BY embedding <=> '{emb_str}'::vector LIMIT 10
                    """),
                    ("向量搜索 doc_chunks (HNSW)", f"""
                        EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                        SELECT id FROM doc_chunks WHERE embedding IS NOT NULL
                        ORDER BY embedding <=> '{emb_str}'::vector LIMIT 10
                    """),
                    ("向量搜索 textbook_blocks_v2 (HNSW)", f"""
                        EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                        SELECT id FROM textbook_blocks_v2 WHERE embedding IS NOT NULL
                        ORDER BY embedding <=> '{emb_str}'::vector LIMIT 10
                    """),
                    ("BM25 搜索 documents (GIN)", """
                        EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                        SELECT id FROM documents, plainto_tsquery('simple', '气功 混元气') q
                        WHERE search_vector @@ q ORDER BY ts_rank_cd(search_vector, q) DESC LIMIT 10
                    """),
                    ("BM25 搜索 guoxue_content (GIN, 26万行)", """
                        EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                        SELECT id FROM guoxue_content, plainto_tsquery('simple', '道德经 天道') q
                        WHERE search_vector @@ q ORDER BY ts_rank_cd(search_vector, q) DESC LIMIT 10
                    """),
                    ("BM25 搜索 doc_chunks (GIN)", """
                        EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                        SELECT id FROM doc_chunks, plainto_tsquery('simple', '站桩 气功') q
                        WHERE search_vector @@ q ORDER BY ts_rank_cd(search_vector, q) DESC LIMIT 10
                    """),
                ]

                for label, sql in tests:
                    r = await run_explain(conn, label, sql)
                    print(f"  [{r['label']}]")
                    if "error" in r:
                        print(f"    ERROR: {r['error']}")
                    else:
                        print(
                            f"    执行={r['exec_ms']}ms  规划={r['plan_ms']}ms  "
                            f"节点={r['node']}  索引={r['index']}\n"
                            f"    行数={r['rows']}  cost={r['cost']}  "
                            f"hit={r['shared_hit']}  read={r['shared_read']}  "
                            f"IO读耗时={r['read_time_ms']}ms"
                        )
                    print()

            await pool.close()
            return

        # ---- 1. 向量搜索 ----
        print("\n## 1. 向量搜索（单表）##")
        async with pool.acquire() as conn:
            for tbl in ["documents", "guoxue_content", "doc_chunks", "textbook_blocks_v2"]:
                has_emb = await conn.fetchval(
                    f"SELECT COUNT(*) FROM {tbl} WHERE embedding IS NOT NULL"
                )
                if has_emb == 0:
                    print(f"  {tbl}: 跳过（无 embedding）")
                    continue
                times = await bench_vector(conn, tbl, emb_str, iters)
                print_result(f"{tbl} ({has_emb:,} rows)", times)

        # ---- 2. BM25 ----
        print("\n## 2. BM25 全文搜索（单表）##")
        bm25_queries = {
            "documents": "气功 混元气",
            "guoxue_content": "道德经 天道",
            "doc_chunks": "站桩 气功",
        }
        async with pool.acquire() as conn:
            for tbl, q in bm25_queries.items():
                has_sv = await conn.fetchval(
                    f"SELECT COUNT(*) FROM {tbl} WHERE search_vector IS NOT NULL"
                )
                if has_sv == 0:
                    print(f"  {tbl}: 跳过（无 search_vector）")
                    continue
                times = await bench_bm25(conn, tbl, q, iters)
                print_result(f"{tbl} ({has_sv:,} rows) query='{q}'", times)

        # ---- 3. 并行搜索 ----
        print("\n## 3. 并行搜索（模拟 hybrid）##")
        p_vec = await bench_parallel_vector(pool, emb_str, iters)
        print_result("4表并行向量搜索", p_vec)

        p_bm25 = await bench_parallel_bm25(pool, "气功 混元气", iters)
        print_result("3表并行BM25搜索", p_bm25)

        # ---- 4. EXPLAIN ANALYZE ----
        print("\n## 4. EXPLAIN ANALYZE（查询计划详情）##")
        async with pool.acquire() as conn:
            tests = [
                ("向量 documents", f"""
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    SELECT id FROM documents WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> '{emb_str}'::vector LIMIT 10
                """),
                ("向量 guoxue", f"""
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    SELECT id FROM guoxue_content WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> '{emb_str}'::vector LIMIT 10
                """),
                ("BM25 documents", """
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    SELECT id FROM documents, plainto_tsquery('simple', '气功 混元气') q
                    WHERE search_vector @@ q ORDER BY ts_rank_cd(search_vector, q) DESC LIMIT 10
                """),
                ("BM25 guoxue", """
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    SELECT id FROM guoxue_content, plainto_tsquery('simple', '道德经 天道') q
                    WHERE search_vector @@ q ORDER BY ts_rank_cd(search_vector, q) DESC LIMIT 10
                """),
            ]

            for label, sql in tests:
                r = await run_explain(conn, label, sql)
                if "error" in r:
                    print(f"  [{label}] ERROR: {r['error']}")
                else:
                    print(
                        f"  [{label}] exec={r['exec_ms']}ms plan={r['plan_ms']}ms "
                        f"idx={r['index']} hit={r['shared_hit']} read={r['shared_read']} "
                        f"io_time={r['read_time_ms']}ms"
                    )

        # ---- 5. IO 缓冲区 ----
        print("\n## 5. IO 缓冲区命中率 ##")
        io = await get_io_stats(pool)
        print(f"  {'表':<25} {'堆命中%':>8} {'索引命中%':>10} {'堆IO总块':>10} {'索引IO总块':>10}")
        for s in io:
            print(
                f"  {s['tbl']:<25} {str(s['heap_hit_pct']):>8} {str(s['idx_hit_pct']):>10} "
                f"{s['heap_total']:>10} {s['idx_total']:>10}"
            )

        # ---- 6. Embedding 生成 ----
        print("\n## 6. Embedding 生成 ##")
        s_times, s_err, b_times, b_err = await bench_embedding(iters)
        print_result("单条 embedding (BGE-small-zh)", s_times, s_err)
        print_result("批量10条 embedding", b_times, b_err)

        # ---- 7. 并发吞吐 ----
        print("\n## 7. 并发向量搜索吞吐 ##")
        for c in [1, 5, 10, 20]:
            r = await bench_concurrent(pool, emb_str, c, 50 if not args.quick else 20)
            print(
                f"  并发={r['concurrency']:>2}  QPS={r['qps']:>6.1f}  "
                f"p50={fmt(r['p50'])}  p95={fmt(r['p95'])}  "
                f"p99={fmt(r['p99'])}  err={r['errors']}"
            )

        # ---- 8. API 端到端 ----
        print("\n## 8. API 端到端（如可用）##")
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get("http://localhost:8000/health", timeout=5)
                api_up = resp.status_code == 200
        except Exception:
            api_up = False

        if api_up:
            api_times, api_err = await bench_api(
                "http://localhost:8000/api/v1/search/hybrid",
                {
                    "query": "混元整体理论",
                    "top_k": 10,
                    "use_vector": True,
                    "use_bm25": True,
                    "use_query_expansion": False,
                },
                iters,
            )
            print_result("POST /api/v1/search/hybrid", api_times, api_err)

            api_times_noexp, _ = await bench_api(
                "http://localhost:8000/api/v1/search/hybrid",
                {
                    "query": "中医阴阳五行",
                    "top_k": 10,
                    "use_vector": True,
                    "use_bm25": True,
                    "use_query_expansion": True,
                },
                max(iters // 2, 3),
            )
            print_result("POST /search/hybrid (含query expansion)", api_times_noexp)
        else:
            print("  API 服务不可用（跳过端到端测试）")

        # ---- 汇总 ----
        print("\n" + "=" * 72)
        print("  性能基线汇总（HDD）")
        print("=" * 72)

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
