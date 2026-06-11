#!/usr/bin/env python3
"""检索精度评估脚本 — 跑50条eval query，计算category命中率和κ值。

用法: python3 scripts/eval_retrieval_kappa.py [--api http://localhost:8001] [--top-k 10]
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data" / "eval"))
from retrieval_eval_set import EVAL_QUERIES


def search(api_base: str, query: str, top_k: int = 10) -> list:
    import requests as sync_requests
    r = sync_requests.post(
        f"{api_base}/api/v1/search/hybrid",
        json={"query": query, "top_k": top_k, "use_vector": True, "use_bm25": True},
        timeout=60,
    )
    r.raise_for_status()
    return r.json().get("results", [])


def category_hit_rate(results: list, expected_categories: list) -> dict:
    top_cats = [r.get("category", "") for r in results[:5]]
    hits = [1 if c in expected_categories else 0 for c in top_cats]
    return {
        "top1_hit": hits[0] if hits else 0,
        "top3_hit": max(hits[:3]) if len(hits) >= 1 else 0,
        "top5_hit": max(hits[:5]) if len(hits) >= 1 else 0,
        "top5_avg": sum(hits) / len(hits) if hits else 0,
    }


def concept_hit_rate(results: list, expected_concepts: list) -> float:
    if not expected_concepts:
        return 1.0
    all_text = " ".join(r.get("content", "") + r.get("title", "") for r in results[:5])
    hits = sum(1 for c in expected_concepts if c in all_text)
    return hits / len(expected_concepts)


def cohen_kappa(p_o: float, p_e: float) -> float:
    if p_e >= 1.0:
        return 0.0
    return (p_o - p_e) / (1.0 - p_e)


def run_eval(api_base: str, top_k: int) -> dict:
    all_categories = ["气功", "中医", "儒家", "佛家", "道家", "武术", "哲学", "科学", "心理学"]
    n_categories = len(all_categories)
    p_e = 1.0 / n_categories

    results = []
    for i, q in enumerate(EVAL_QUERIES):
        t0 = time.time()
        try:
            search_results = search(api_base, q["query"], top_k)
        except Exception as e:
            print(f"  [{i+1}/50] ERROR {q['id']}: {e}")
            results.append({"id": q["id"], "error": str(e)})
            continue
        dt = time.time() - t0

        cat_hits = category_hit_rate(search_results, q["expected_categories"])
        concept_hit = concept_hit_rate(search_results, q["expected_concepts"])

        row = {
            "id": q["id"],
            "query": q["query"],
            "type": q["type"],
            "latency_s": round(dt, 2),
            "n_results": len(search_results),
            "top1_cat": search_results[0].get("category", "") if search_results else "",
            "top1_hit": cat_hits["top1_hit"],
            "top3_hit": cat_hits["top3_hit"],
            "top5_hit": cat_hits["top5_hit"],
            "top5_avg": round(cat_hits["top5_avg"], 3),
            "concept_hit": round(concept_hit, 3),
        }
        results.append(row)
        status = "✓" if cat_hits["top1_hit"] else "✗"
        print(f"  [{i+1}/50] {status} {q['id']} {q['query'][:20]:20s} top1={row['top1_cat']:6s} cat_hit={cat_hits['top1_hit']} concept={concept_hit:.2f} {dt:.1f}s")

    valid = [r for r in results if "error" not in r]
    if not valid:
        print("ERROR: no valid results")
        return {"kappa": 0, "results": results}

    p_o_top1 = sum(r["top1_hit"] for r in valid) / len(valid)
    p_o_top3 = sum(r["top3_hit"] for r in valid) / len(valid)
    p_o_top5 = sum(r["top5_hit"] for r in valid) / len(valid)
    p_o_concept = sum(r["concept_hit"] for r in valid) / len(valid)

    kappa_top1 = cohen_kappa(p_o_top1, p_e)
    kappa_top3 = cohen_kappa(p_o_top3, p_e)

    by_type = {}
    for t in ["精确", "模糊", "跨领域"]:
        tv = [r for r in valid if r.get("type") == t]
        if tv:
            by_type[t] = {
                "count": len(tv),
                "top1_hit_rate": round(sum(r["top1_hit"] for r in tv) / len(tv), 3),
                "concept_hit_rate": round(sum(r["concept_hit"] for r in tv) / len(tv), 3),
            }

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "api_base": api_base,
        "top_k": top_k,
        "n_queries": len(EVAL_QUERIES),
        "n_valid": len(valid),
        "category_accuracy": {
            "top1": round(p_o_top1, 4),
            "top3": round(p_o_top3, 4),
            "top5": round(p_o_top5, 4),
        },
        "concept_accuracy": round(p_o_concept, 4),
        "kappa_top1": round(kappa_top1, 4),
        "kappa_top3": round(kappa_top3, 4),
        "avg_latency": round(sum(r["latency_s"] for r in valid) / len(valid), 2),
        "by_type": by_type,
    }

    print(f"\n{'='*50}")
    print(f"检索精度评估结果 ({len(valid)} queries)")
    print(f"{'='*50}")
    print(f"  Category Top1 命中率: {p_o_top1:.1%}")
    print(f"  Category Top3 命中率: {p_o_top3:.1%}")
    print(f"  Category Top5 命中率: {p_o_top5:.1%}")
    print(f"  Concept 命中率:       {p_o_concept:.1%}")
    print(f"  κ (Top1):             {kappa_top1:.4f}")
    print(f"  κ (Top3):             {kappa_top3:.4f}")
    print(f"  平均延迟:             {summary['avg_latency']}s")
    print(f"{'='*50}")

    return {"summary": summary, "results": results}


def main():
    parser = argparse.ArgumentParser(description="检索精度评估")
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--top-k", type=int, default=10, help="top_k for search")
    parser.add_argument("--output", default="data/eval/kappa_results.json", help="output file")
    args = parser.parse_args()

    report = run_eval(args.api, args.top_k)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
