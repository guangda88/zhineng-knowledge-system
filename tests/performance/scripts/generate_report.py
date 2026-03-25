#!/usr/bin/env python3
"""
性能测试报告生成器

从 Locust CSV 报告生成详细的性能分析报告
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def parse_stats_file(csv_file: Path) -> Dict[str, Any]:
    """解析 Locust stats CSV 文件"""
    stats = {
        "endpoints": {},
        "total": {
            "requests": 0,
            "failures": 0,
            "avg_response_time": 0,
            "min_response_time": float("inf"),
            "max_response_time": 0,
        },
    }

    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["Name"]
            stats["endpoints"][name] = {
                "requests": int(row["Request Count"]),
                "failures": int(row["Failure Count"]),
                "median": float(row["Median Response Time"]),
                "avg": float(row["Average Response Time"]),
                "min": float(row["Min Response Time"]),
                "max": float(row["Max Response Time"]),
                "p95": float(row["95%"]),
                "p99": float(row["99%"]),
            }

            # 累计总数
            stats["total"]["requests"] += int(row["Request Count"])
            stats["total"]["failures"] += int(row["Failure Count"])
            stats["total"]["avg_response_time"] += float(row["Average Response Time"]) * int(
                row["Request Count"]
            )
            stats["total"]["min_response_time"] = min(
                stats["total"]["min_response_time"], float(row["Min Response Time"])
            )
            stats["total"]["max_response_time"] = max(
                stats["total"]["max_response_time"], float(row["Max Response Time"])
            )

    # 计算整体平均
    if stats["total"]["requests"] > 0:
        stats["total"]["avg_response_time"] /= stats["total"]["requests"]

    if stats["total"]["min_response_time"] == float("inf"):
        stats["total"]["min_response_time"] = 0

    return stats


def parse_history_file(csv_file: Path) -> List[Dict[str, Any]]:
    """解析 Locust stats_history CSV 文件"""
    history = []

    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            history.append(
                {
                    "timestamp": row["Timestamp"],
                    "user_count": int(row["User Count"]),
                    "requests_per_second": float(row.get("Requests/s", 0)),
                    "failures_per_second": float(row.get("Failures/s", 0)),
                    "median_response_time": float(row.get("Median Response Time", 0)),
                    "avg_response_time": float(row.get("Average Response Time", 0)),
                }
            )

    return history


def generate_markdown_report(stats: Dict[str, Any], history: List[Dict], output_file: Path) -> None:
    """生成 Markdown 格式的性能报告"""

    # 性能目标
    targets = {"p50": 200, "p95": 1000, "p99": 2000}

    report_lines = [
        "# 性能测试报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## 概要",
        "",
        f"- **总请求数**: {stats['total']['requests']:,}",
        f"- **失败请求数**: {stats['total']['failures']:,}",
        f"- **成功率**: {(1 - stats['total']['failures'] / max(stats['total']['requests'], 1)) * 100:.2f}%",
        f"- **平均响应时间**: {stats['total']['avg_response_time']:.0f}ms",
        f"- **最小响应时间**: {stats['total']['min_response_time']:.0f}ms",
        f"- **最大响应时间**: {stats['total']['max_response_time']:.0f}ms",
        "",
        "---",
        "",
        "## 性能目标",
        "",
        "| 指标 | 目标值 | 状态 |",
        "|------|--------|------|",
    ]

    # 检查整体性能目标
    overall_p50 = stats["total"]["avg_response_time"]  # 使用平均作为近似
    target_status_p50 = "✅ 通过" if overall_p50 < targets["p50"] else "❌ 未达标"
    report_lines.append(f"| P50 响应时间 | <{targets['p50']}ms | {target_status_p50} |")

    # 计算整体 P95/P99
    all_p95 = [e["p95"] for e in stats["endpoints"].values()]
    all_p99 = [e["p99"] for e in stats["endpoints"].values()]

    if all_p95:
        avg_p95 = sum(all_p95) / len(all_p95)
        target_status_p95 = "✅ 通过" if avg_p95 < targets["p95"] else "❌ 未达标"
        report_lines.append(f"| P95 响应时间 | <{targets['p95']}ms | {target_status_p95} |")

    if all_p99:
        avg_p99 = sum(all_p99) / len(all_p99)
        target_status_p99 = "✅ 通过" if avg_p99 < targets["p99"] else "❌ 未达标"
        report_lines.append(f"| P99 响应时间 | <{targets['p99']}ms | {target_status_p99} |")

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## 端点详细分析",
            "",
            "| 端点 | 请求数 | 失败数 | P50 | P95 | P99 | 状态 |",
            "|------|--------|--------|-----|-----|-----|------|",
        ]
    )

    for endpoint, data in stats["endpoints"].items():
        # 检查状态
        status = "✅"
        if data["p95"] > targets["p95"]:
            status = "⚠️ P95超标"
        if data["p99"] > targets["p99"]:
            status = "❌ P99超标"

        report_lines.append(
            f"| {endpoint} | {data['requests']:,} | {data['failures']} | "
            f"{data['median']:.0f}ms | {data['p95']:.0f}ms | {data['p99']:.0f}ms | {status} |"
        )

    # 性能建议
    report_lines.extend(
        [
            "",
            "---",
            "",
            "## 性能建议",
            "",
        ]
    )

    needs_optimization = False
    for endpoint, data in stats["endpoints"].items():
        suggestions = []
        if data["p95"] > targets["p95"]:
            needs_optimization = True
            suggestions.append(f"P95响应时间 ({data['p95']:.0f}ms) 超过目标 ({targets['p95']}ms)")
        if data["p99"] > targets["p99"]:
            needs_optimization = True
            suggestions.append(f"P99响应时间 ({data['p99']:.0f}ms) 超过目标 ({targets['p99']}ms)")

        if suggestions:
            report_lines.append(f"### {endpoint}")
            for suggestion in suggestions:
                report_lines.append(f"- {suggestion}")
            report_lines.append("")

    if not needs_optimization:
        report_lines.append("✅ 所有端点性能均达到目标，无需优化。")

    # 时间序列分析（如果有历史数据）
    if history and len(history) > 1:
        report_lines.extend(
            [
                "",
                "---",
                "",
                "## 时间序列分析",
                "",
                "| 时间 | 用户数 | RPS | 平均响应时间 |",
                "|------|--------|-----|-------------|",
            ]
        )

        # 只显示部分数据点
        step = max(1, len(history) // 20)
        for i in range(0, len(history), step):
            row = history[i]
            report_lines.append(
                f"| {row['timestamp']} | {row['user_count']} | "
                f"{row['requests_per_second']:.1f} | {row['avg_response_time']:.0f}ms |"
            )

    # 报告尾部
    report_lines.extend(
        [
            "",
            "---",
            "",
            "## 附加信息",
            "",
            "### 测试配置",
            f"- **并发用户数**: 根据测试配置",
            f"- **测试时长**: 根据测试配置",
            f"- **目标主机**: ${TARGET_HOST:-http://localhost:8000}",
            "",
            "### 性能优化建议",
            "",
            "如果性能未达标，可以考虑以下优化措施:",
            "",
            "1. **数据库优化**",
            "   - 添加适当的索引",
            "   - 优化查询语句",
            "   - 增加连接池大小",
            "",
            "2. **缓存策略**",
            "   - 启用 Redis 缓存",
            "   - 实现查询结果缓存",
            "   - 设置合理的过期时间",
            "",
            "3. **应用层优化**",
            "   - 使用异步处理",
            "   - 批量操作减少请求次数",
            "   - 压缩响应数据",
            "",
            "4. **基础设施**",
            "   - 增加服务器资源",
            "   - 使用负载均衡",
            "   - CDN 加速静态资源",
            "",
            "---",
            "",
            f"*报告由 generate_report.py 自动生成*",
        ]
    )

    # 写入文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"报告已生成: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="生成性能测试报告")
    parser.add_argument("prefix", help="Locust CSV 文件前缀 (如: reports/standard_20240101_120000)")
    parser.add_argument(
        "-o", "--output", help="输出报告文件 (默认: PREFIX_report.md)", default=None
    )

    args = parser.parse_args()

    # 确定文件路径
    prefix_path = Path(args.prefix)
    stats_file = prefix_path.with_suffix("_stats.csv")
    history_file = prefix_path.with_suffix("_stats_history.csv")

    if not stats_file.exists():
        print(f"错误: 找不到统计文件 {stats_file}")
        sys.exit(1)

    # 解析数据
    stats = parse_stats_file(stats_file)
    history = []
    if history_file.exists():
        history = parse_history_file(history_file)

    # 确定输出文件
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = prefix_path.with_suffix("_report.md")

    # 生成报告
    generate_markdown_report(stats, history, output_file)


if __name__ == "__main__":
    main()
