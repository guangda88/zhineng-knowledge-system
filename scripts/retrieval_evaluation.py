"""检索质量评估脚本 — 通过 API HTTP 端点

避开宿主机 numpy 兼容性问题，直接调用 Docker 内 API。
"""

import json
import time
import urllib.request
import urllib.error

API_BASE = "http://localhost:8000"

CATEGORIES = ["气功", "中医", "儒家", "佛家", "道家", "武术", "哲学", "科学", "心理学"]

TEST_QUERIES = [
    # 气功
    {"query": "混元气的本质是什么", "category": "气功", "type": "精确"},
    {"query": "练功时杂念很多怎么办", "category": "气功", "type": "模糊"},
    {"query": "气功与中医经络的关系", "category": "气功", "type": "跨领域"},
    # 中医
    {"query": "五脏六腑的功能", "category": "中医", "type": "精确"},
    {"query": "体质虚寒如何调理", "category": "中医", "type": "模糊"},
    {"query": "中医与哲学阴阳五行", "category": "中医", "type": "跨领域"},
    # 儒家
    {"query": "仁义礼智信的含义", "category": "儒家", "type": "精确"},
    {"query": "如何修身齐家", "category": "儒家", "type": "模糊"},
    {"query": "儒家思想对现代教育的影响", "category": "儒家", "type": "跨领域"},
    # 佛家
    {"query": "四圣谛八正道", "category": "佛家", "type": "精确"},
    {"query": "禅修入门方法", "category": "佛家", "type": "模糊"},
    {"query": "佛教与心理学正念", "category": "佛家", "type": "跨领域"},
    # 道家
    {"query": "道德经第一章解读", "category": "道家", "type": "精确"},
    {"query": "无为而治在管理中的应用", "category": "道家", "type": "模糊"},
    {"query": "道家养生与气功", "category": "道家", "type": "跨领域"},
    # 武术
    {"query": "太极拳的基本功法", "category": "武术", "type": "精确"},
    {"query": "如何提高武术实战能力", "category": "武术", "type": "模糊"},
    {"query": "武术与中医筋骨理论", "category": "武术", "type": "跨领域"},
    # 哲学
    {"query": "存在主义的核心观点", "category": "哲学", "type": "精确"},
    {"query": "意识与物质的关系", "category": "哲学", "type": "模糊"},
    {"query": "中西方哲学比较", "category": "哲学", "type": "跨领域"},
    # 科学
    {"query": "量子力学基本原理", "category": "科学", "type": "精确"},
    {"query": "人工智能的发展趋势", "category": "科学", "type": "模糊"},
    {"query": "科学与哲学的认识论", "category": "科学", "type": "跨领域"},
    # 心理学
    {"query": "认知行为疗法CBT原理", "category": "心理学", "type": "精确"},
    {"query": "如何缓解焦虑情绪", "category": "心理学", "type": "模糊"},
    {"query": "心理学与佛学冥想", "category": "心理学", "type": "跨领域"},
]


def call_hybrid_search(query, category=None, top_k=10):
    """调用混合检索 API"""
    payload = {"query": query, "top_k": top_k, "use_query_expansion": False}
    if category:
        payload["category"] = category

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/api/v1/search/hybrid",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def evaluate():
    print("=" * 80)
    print("检索质量评估 — 灵知知识库 (via API)")
    print(f"测试查询: {len(TEST_QUERIES)} 条 ({len(CATEGORIES)} 领域 × 3 类型)")
    print("=" * 80)

    results = []
    for i, q in enumerate(TEST_QUERIES):
        label = f"[{i+1}/{len(TEST_QUERIES)}] {q['category']}/{q['type']}: {q['query'][:25]}"
        print(f"{label}... ", end="", flush=True)

        # 跨领域查询不强制category filter（结果可能分布在多个领域）
        search_category = q["category"] if q["type"] != "跨领域" else None
        start = time.perf_counter()
        resp = call_hybrid_search(q["query"], category=search_category, top_k=10)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if resp is None:
            print(f"✗ ERROR {elapsed_ms:.0f}ms")
            results.append({
                "query": q["query"], "category": q["category"], "type": q["type"],
                "hit": False, "result_count": 0, "latency_ms": elapsed_ms,
                "top1_sim": 0, "top3_avg_sim": 0, "top5_avg_sim": 0,
                "source_tables": [], "top_categories": [],
            })
            continue

        items = resp.get("results", [])
        hit = len(items) > 0
        count = len(items)

        sims = []
        tables = []
        cats = []
        for r in items:
            sim = r.get("similarity", r.get("score", 0.0)) or 0.0
            sims.append(sim)
            tbl = r.get("source_table", "unknown")
            if tbl not in tables:
                tables.append(tbl)
            cat = r.get("category", "")
            if cat and cat not in cats:
                cats.append(cat)

        top1 = sims[0] if sims else 0
        top3 = sum(sims[:3]) / min(len(sims), 3) if sims else 0
        top5 = sum(sims[:5]) / min(len(sims), 5) if sims else 0

        status = "✓" if hit else "✗"
        print(f"{status} {count}条 {elapsed_ms:.0f}ms top1={top1:.3f}")

        results.append({
            "query": q["query"], "category": q["category"], "type": q["type"],
            "hit": hit, "result_count": count, "latency_ms": elapsed_ms,
            "top1_sim": top1, "top3_avg_sim": top3, "top5_avg_sim": top5,
            "source_tables": tables, "top_categories": cats,
        })

    # ============ 汇总 ============
    total = len(results)
    hits = sum(1 for r in results if r["hit"])
    hit_rate = hits / total * 100
    avg_lat = sum(r["latency_ms"] for r in results) / total
    avg_top1 = sum(r["top1_sim"] for r in results if r["hit"]) / max(hits, 1)
    avg_top3 = sum(r["top3_avg_sim"] for r in results if r["hit"]) / max(hits, 1)
    avg_top5 = sum(r["top5_avg_sim"] for r in results if r["hit"]) / max(hits, 1)

    print("\n" + "=" * 80)
    print("总体指标")
    print("=" * 80)
    print(f"  命中率: {hits}/{total} ({hit_rate:.1f}%)")
    print(f"  平均延迟: {avg_lat:.0f}ms")
    print(f"  Top-1 相似度: {avg_top1:.4f}")
    print(f"  Top-3 平均相似度: {avg_top3:.4f}")
    print(f"  Top-5 平均相似度: {avg_top5:.4f}")

    print(f"\n按领域统计:")
    print(f"{'领域':<8} {'命中率':>8} {'平均结果':>8} {'Top-1':>8} {'Top-3':>8} {'延迟ms':>8}")
    print("-" * 56)
    for cat in CATEGORIES:
        cr = [r for r in results if r["category"] == cat]
        ch = sum(1 for r in cr if r["hit"])
        ct = len(cr)
        ac = sum(r["result_count"] for r in cr) / max(ct, 1)
        t1 = sum(r["top1_sim"] for r in cr if r["hit"]) / max(ch, 1)
        t3 = sum(r["top3_avg_sim"] for r in cr if r["hit"]) / max(ch, 1)
        lat = sum(r["latency_ms"] for r in cr) / max(ct, 1)
        print(f"{cat:<8} {ch}/{ct:>4} {ac:>8.1f} {t1:>8.4f} {t3:>8.4f} {lat:>8.0f}")

    print(f"\n按查询类型统计:")
    print(f"{'类型':<8} {'命中率':>8} {'Top-1':>8} {'Top-3':>8} {'延迟ms':>8}")
    print("-" * 44)
    for qt in ["精确", "模糊", "跨领域"]:
        tr = [r for r in results if r["type"] == qt]
        th = sum(1 for r in tr if r["hit"])
        tt = len(tr)
        t1 = sum(r["top1_sim"] for r in tr if r["hit"]) / max(th, 1)
        t3 = sum(r["top3_avg_sim"] for r in tr if r["hit"]) / max(th, 1)
        lat = sum(r["latency_ms"] for r in tr) / max(tt, 1)
        print(f"{qt:<8} {th}/{tt:>4} {t1:>8.4f} {t3:>8.4f} {lat:>8.0f}")

    low_q = [r for r in results if not r["hit"] or r["top1_sim"] < 0.3]
    if low_q:
        print(f"\n低质量查询 ({len(low_q)} 条, top1 < 0.3 或无结果):")
        for r in low_q:
            print(f"  [{r['category']}/{r['type']}] {r['query']}")
            print(f"    命中={r['hit']} 结果数={r['result_count']} top1={r['top1_sim']:.4f}")

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {
            "total_queries": total, "hit_rate": hit_rate,
            "avg_latency_ms": avg_lat,
            "avg_top1_sim": avg_top1, "avg_top3_sim": avg_top3, "avg_top5_sim": avg_top5,
        },
        "results": results,
    }
    with open("/home/ai/lingzhi/data/retrieval_evaluation.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到 data/retrieval_evaluation.json")


if __name__ == "__main__":
    evaluate()
