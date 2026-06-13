#!/usr/bin/env python3
"""
RAG交叉验证脚本 — 将关键词分类的健康声明用知识库检索交叉验证

输入：data/health_claims/health_claim_verification_report.json
输出：data/health_claims/rag_cross_validation_report.json

逻辑：
  1. 读取所有中风险声明
  2. 用声明文本作为query调用 /api/v1/search
  3. 分析top结果的相似度，判断知识库是否有支撑
  4. 相似度 >= 0.6 → 有支撑（可降级为低风险）
  5. 相似度 < 0.6 → 无支撑（维持中风险）

用法：
  python3 scripts/rag_cross_verify.py                     # 验证所有中风险
  python3 scripts/rag_cross_verify.py --min-risk medium   # 指定最低风险级别
  python3 scripts/rag_cross_verify.py --threshold 0.55    # 自定义相似度阈值
  python3 scripts/rag_cross_verify.py --dry-run           # 只统计不写文件
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000"
SEARCH_URL = f"{API_BASE}/api/v1/search"
HEALTH_URL = f"{API_BASE}/health"

INPUT_PATH = Path("data/health_claims/health_claim_verification_report.json")
OUTPUT_PATH = Path("data/health_claims/rag_cross_validation_report.json")

SIMILARITY_THRESHOLD = 0.6
TOP_K = 5
REQUEST_DELAY = 0.3


def check_api_health() -> bool:
    try:
        r = httpx.get(HEALTH_URL, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def load_claims(report_path: Path, min_risk: str) -> list[dict]:
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    risk_order = {"low": 0, "medium": 1, "high": 2}
    min_level = risk_order.get(min_risk, 1)

    claims = []
    for ep_id, ep_data in report.get("episodes", {}).items():
        for claim in ep_data.get("claims", []):
            claim_risk = risk_order.get(claim.get("risk_level", claim.get("risk", "low")), 0)
            if claim_risk >= min_level:
                claim["_episode"] = ep_id
                claim["_line"] = claim.get("line_number", claim.get("line", 0))
                claims.append(claim)
    return claims


async def search_knowledge_base(query: str, client: httpx.AsyncClient) -> dict:
    try:
        r = await client.get(
            SEARCH_URL,
            params={"q": query, "limit": TOP_K},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            top_sim = results[0].get("similarity", 0.0) if results else 0.0
            sources = []
            for res in results[:3]:
                sources.append({
                    "title": res.get("title", ""),
                    "similarity": round(res.get("similarity", 0.0), 4),
                    "source_table": res.get("source_table", ""),
                    "category": res.get("category", ""),
                })
            return {
                "top_similarity": round(top_sim, 4),
                "total_results": len(results),
                "sources": sources,
            }
    except Exception as e:
        return {"top_similarity": 0.0, "total_results": 0, "error": str(e)}
    return {"top_similarity": 0.0, "total_results": 0}


async def verify_claims(claims: list[dict], threshold: float) -> list[dict]:
    import asyncio

    verified = []
    async with httpx.AsyncClient() as client:
        for i, claim in enumerate(claims):
            text = claim.get("text", claim.get("claim_text", ""))
            if not text or len(text) < 4:
                claim["_rag"] = {"top_similarity": 0.0, "supported": False, "reason": "text_too_short"}
                verified.append(claim)
                continue

            rag_result = await search_knowledge_base(text, client)
            rag_result["supported"] = rag_result["top_similarity"] >= threshold
            rag_result["threshold"] = threshold

            claim_out = dict(claim)
            claim_out["_rag"] = rag_result
            verified.append(claim_out)

            if (i + 1) % 10 == 0:
                print(f"  进度: {i + 1}/{len(claims)}")

            await asyncio.sleep(REQUEST_DELAY)

    return verified


def generate_summary(verified: list[dict], threshold: float) -> dict:
    supported = [c for c in verified if c.get("_rag", {}).get("supported")]
    unsupported = [c for c in verified if not c.get("_rag", {}).get("supported")]

    by_risk = {}
    for c in verified:
        risk = c.get("risk_level", c.get("risk", "unknown"))
        by_risk.setdefault(risk, {"total": 0, "supported": 0})
        by_risk[risk]["total"] += 1
        if c.get("_rag", {}).get("supported"):
            by_risk[risk]["supported"] += 1

    by_category = {}
    for c in verified:
        cat = c.get("medium_subcategory", c.get("claim_type", "unknown"))
        by_category.setdefault(cat, {"total": 0, "supported": 0})
        by_category[cat]["total"] += 1
        if c.get("_rag", {}).get("supported"):
            by_category[cat]["supported"] += 1

    similarities = [c["_rag"]["top_similarity"] for c in verified if "_rag" in c]
    avg_sim = sum(similarities) / len(similarities) if similarities else 0.0

    return {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "verifier": "lingzhi",
        "method": "rag_cross_validation",
        "threshold": threshold,
        "totals": {
            "total_claims": len(verified),
            "supported": len(supported),
            "unsupported": len(unsupported),
            "support_rate": round(len(supported) / len(verified), 3) if verified else 0,
            "avg_similarity": round(avg_sim, 4),
        },
        "by_risk_level": by_risk,
        "by_category": by_category,
    }


async def main():
    parser = argparse.ArgumentParser(description="RAG交叉验证健康声明")
    parser.add_argument("--min-risk", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--threshold", type=float, default=SIMILARITY_THRESHOLD)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input", default=str(INPUT_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    print("=" * 60)
    print("RAG交叉验证 — 知识库检索验证健康声明")
    print("=" * 60)

    if not check_api_health():
        print("错误: API不可达，请先启动服务")
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 输入文件不存在 {input_path}")
        sys.exit(1)

    claims = load_claims(input_path, args.min_risk)
    print(f"  加载声明: {len(claims)} 条 (最低风险: {args.min_risk})")
    print(f"  相似度阈值: {args.threshold}")

    if not claims:
        print("  无符合条件的声明")
        return

    t0 = time.time()
    verified = await verify_claims(claims, args.threshold)
    elapsed = time.time() - t0

    summary = generate_summary(verified, args.threshold)
    summary["elapsed_seconds"] = round(elapsed, 1)

    print(f"\n{'=' * 60}")
    print(f"验证完成 ({elapsed:.1f}s)")
    print(f"{'=' * 60}")
    print(f"  总声明: {summary['totals']['total_claims']}")
    print(f"  有知识库支撑: {summary['totals']['supported']} ({summary['totals']['support_rate']:.1%})")
    print(f"  无支撑: {summary['totals']['unsupported']}")
    print(f"  平均相似度: {summary['totals']['avg_similarity']:.4f}")
    print("\n  按风险级别:")
    for risk, data in summary["by_risk_level"].items():
        print(f"    {risk}: {data['supported']}/{data['total']} 有支撑")
    print("\n  按类别:")
    for cat, data in summary["by_category"].items():
        print(f"    {cat}: {data['supported']}/{data['total']} 有支撑")

    if args.dry_run:
        print("\n  (dry-run, 不写入文件)")
        return

    report = {"summary": summary, "claims": verified}
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  报告: {output_path}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
