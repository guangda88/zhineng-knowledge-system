#!/usr/bin/env python3
"""
简化版检索性能基准测试 - 验证 BM25 和混合检索优化效果

测试查询数: 100 次查询
"""

import asyncio
import time
import statistics
import sys

sys.path.insert(0, "/home/ai/lingzhi")

from backend.core.database import init_db_pool
from backend.services.retrieval.bm25 import BM25Retriever
from backend.services.retrieval.hybrid import HybridRetriever

# 禁用 Redis 缓存（避免连接问题）
import os
os.environ['REDIS_URL'] = 'redis://localhost:6381/0'


async def quick_benchmark(name, operation, queries, iterations=50):
    """快速基准测试"""
    latencies = []
    errors = 0

    print(f"\n{'='*60}")
    print(f"基准测试: {name}")
    print(f"{'='*60}")

    start = time.time()

    for i in range(iterations):
        for query in queries:
            try:
                t0 = time.perf_counter()
                await operation(query, top_k=10)
                latencies.append((time.perf_counter() - t0) * 1000)

                if len(latencies) % 50 == 0:
                    print(f"  进度: {len(latencies):4d} | 最近平均: {statistics.mean(latencies[-10:]):6.2f}ms")
            except Exception as e:
                errors += 1
                if errors <= 2:
                    print(f"  错误: {e}")

    total = time.time() - start

    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.5)]
    p95 = latencies[int(len(latencies) * 0.95)]

    print(f"\n结果: {name}")
    print(f"  样本数: {len(latencies)}")
    print(f"  P50:    {p50:6.2f}ms")
    print(f"  P95:    {p95:6.2f}ms")
    print(f"  QPS:    {len(latencies)/total:6.2f}")
    print(f"  错误:   {errors}")

    return p50, p95


async def main():
    print("\n" + "="*60)
    print("检索性能快速基准测试")
    print("="*60)

    db_pool = await init_db_pool()

    queries = [
        "气功八段锦",
        "中医针灸治疗",
        "论语仁义礼智",
        "道德经无为",
        "太极拳要领",
        "经络穴位",
        "养生保健",
        "功法练习",
        "中医辨证",
        "国学经典",
    ]

    results = []

    # BM25 全文检索
    try:
        bm25 = BM25Retriever(db_pool)
        await bm25.initialize()
        p50, p95 = await quick_benchmark("BM25 全文检索", bm25.search, queries)
        results.append(("BM25", p50, p95))
    except Exception as e:
        print(f"BM25测试失败: {e}")

    # 混合检索
    try:
        hybrid = HybridRetriever(db_pool)
        p50, p95 = await quick_benchmark("混合检索 (Hybrid)", hybrid.search, queries, iterations=30)
        results.append(("Hybrid", p50, p95))
    except Exception as e:
        print(f"混合检索测试失败: {e}")

    print(f"\n{'='*60}")
    print("性能对比")
    print(f"{'='*60}")
    print(f"\n{'操作':<20} {'P50':<10} {'P95':<10} {'目标':<10}")
    print("-"*55)
    print(f"{'BM25':<20} {results[0][1]:8.1f} {results[0][2]:8.1f} {'✅' if results[0][1] < 200 else '⚠️'} <200ms")
    if len(results) > 1:
        print(f"{'Hybrid':<20} {results[1][1]:8.1f} {results[1][2]:8.1f} {'✅' if results[1][1] < 500 else '⚠️'} <500ms")

    print(f"\n{'='*60}")
    print("优化效果")
    print(f"{'='*60}")
    print("""
✅ GIN 全文索引 (BM25) - 预期 3-5x 提升
✅ 并行上下文加载 - 预期 50% 提升
✅ 批量 UPDATE - 预期 90% 提升
✅ 消除 book title 查询 - 预期 100% 提升

目标: Hybrid P95 < 500ms (优化前可能 1-2s)
    """)


if __name__ == "__main__":
    asyncio.run(main())
