"""变更影响评估脚本

自进化计划 E4: 从问题修复到系统性预防
评估代码变更的影响范围和风险等级

用法:
    python scripts/change_impact.py --files backend/auth/middleware.py backend/api/v1/search.py
    python scripts/change_impact.py --staged
"""

import argparse
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

HIGH_IMPACT_PATTERNS = {
    "auth": {"risk": "high", "desc": "认证/授权模块"},
    "middleware": {"risk": "high", "desc": "中间件"},
    "lifespan": {"risk": "high", "desc": "启动生命周期"},
    "config": {"risk": "high", "desc": "配置"},
    "models.py": {"risk": "medium", "desc": "数据模型"},
    "init__.py": {"risk": "medium", "desc": "包初始化"},
    "conftest.py": {"risk": "low", "desc": "测试配置"},
}

DOMAIN_IMPACT = {
    "backend/auth/": "认证系统",
    "backend/api/": "API路由",
    "backend/core/": "核心启动",
    "backend/middleware/": "中间件",
    "backend/monitoring/": "监控",
    "backend/services/retrieval/": "检索系统",
    "backend/services/knowledge_graph/": "知识图谱",
    "backend/cache/": "缓存",
    "backend/domains/": "领域逻辑",
    "backend/common/": "公共工具",
    "scripts/": "运维脚本",
    "tests/": "测试",
}


def get_staged_files():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_changed_files():
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def assess_file(filepath):
    risk = "low"
    reasons = []
    domains_affected = set()

    for pattern, info in HIGH_IMPACT_PATTERNS.items():
        if pattern in filepath:
            risk = info["risk"]
            reasons.append(info["desc"])

    for prefix, domain in DOMAIN_IMPACT.items():
        if filepath.startswith(prefix):
            domains_affected.add(domain)

    resolved = (PROJECT_ROOT / filepath).resolve()
    if resolved.is_relative_to(PROJECT_ROOT / "tests") or filepath.endswith("_test.py"):
        risk = min(risk, "low")
        reasons.append("测试文件")

    if filepath.endswith((".sql", "init.sql", "migration")):
        risk = "high"
        reasons.append("数据库变更")

    fp = PROJECT_ROOT / filepath
    lines_changed = 0
    if fp.exists():
        diff = subprocess.run(
            ["git", "diff", "HEAD", "--", filepath],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        lines_changed = sum(1 for line in diff.stdout.split("\n") if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))

    return {
        "file": filepath,
        "risk": risk,
        "reasons": reasons,
        "domains": list(domains_affected),
        "lines_changed": lines_changed,
    }


def assess_impact(files):
    if not files:
        print("没有变更文件")
        return

    assessments = [assess_file(f) for f in files]

    risk_order = {"high": 0, "medium": 1, "low": 2}
    assessments.sort(key=lambda a: risk_order.get(a["risk"], 3))

    high = [a for a in assessments if a["risk"] == "high"]
    medium = [a for a in assessments if a["risk"] == "medium"]
    low = [a for a in assessments if a["risk"] == "low"]

    all_domains = set()
    for a in assessments:
        all_domains.update(a["domains"])

    total_lines = sum(a["lines_changed"] for a in assessments)

    print("=" * 60)
    print("  变更影响评估")
    print("=" * 60)
    print(f"  文件数: {len(files)} | 变更行数: ~{total_lines}")
    print(f"  风险分布: {len(high)} HIGH / {len(medium)} MEDIUM / {len(low)} LOW")
    print(f"  影响域: {', '.join(all_domains) or '无'}")
    print()

    if high:
        print("  HIGH RISK:")
        for a in high:
            print(f"    {a['file']}")
            for r in a["reasons"]:
                print(f"      - {r}")

    if medium:
        print("  MEDIUM RISK:")
        for a in medium:
            print(f"    {a['file']} ({', '.join(a['reasons'])})")

    if low:
        print(f"  LOW RISK: {len(low)} files")

    print()
    print("  建议检查:")
    if high:
        print("    - 高风险文件需要交叉审查")
    if len(all_domains) > 2:
        print("    - 跨多个域变更，建议逐域测试")
    if total_lines > 200:
        print("    - 大量行变更，建议分批提交")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="变更影响评估")
    parser.add_argument("--files", nargs="+", help="指定文件列表")
    parser.add_argument("--staged", action="store_true", help="评估暂存文件")
    parser.add_argument("--unstaged", action="store_true", help="评估未暂存变更")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    if args.staged:
        files = get_staged_files()
    elif args.unstaged:
        files = get_changed_files()
    elif args.files:
        files = args.files
    else:
        files = get_changed_files()

    if args.json:
        assessments = [assess_file(f) for f in files]
        print(json.dumps(assessments, indent=2, ensure_ascii=False))
    else:
        assess_impact(files)


if __name__ == "__main__":
    main()
