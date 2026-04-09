#!/usr/bin/env python3
"""
性能基准测试工具

用于收集和记录性能基准数据，支持历史对比
"""

import argparse
import asyncio
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import httpx


class BenchmarkCollector:
    """性能基准数据收集器"""

    def __init__(self, host: str, output_dir: str = "reports"):
        self.host = host.rstrip("/")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results = {}

    async def measure_endpoint(
        self, client: httpx.AsyncClient, method: str, path: str, **kwargs
    ) -> Dict[str, Any]:
        """测量单个端点的性能"""
        times = []
        errors = 0

        # 预热
        for _ in range(3):
            try:
                await client.request(method, f"{self.host}{path}", timeout=30.0, **kwargs)
            except Exception:
                pass

        # 正式测量
        for _ in range(50):
            try:
                start = datetime.now()
                response = await client.request(
                    method, f"{self.host}{path}", timeout=30.0, **kwargs
                )
                end = datetime.now()
                elapsed = (end - start).total_seconds() * 1000

                if response.status_code in [200, 404]:
                    times.append(elapsed)
                else:
                    errors += 1
            except Exception:
                errors += 1

        if not times:
            return {"error": "All requests failed", "errors": errors}

        return {
            "count": len(times),
            "errors": errors,
            "min": min(times),
            "max": max(times),
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "stdev": statistics.stdev(times) if len(times) > 1 else 0,
            "p95": statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times),
            "p99": statistics.quantiles(times, n=100)[98] if len(times) > 100 else max(times),
        }

    async def collect(self) -> Dict[str, Any]:
        """收集所有端点的性能数据"""
        self.results = {"timestamp": datetime.now().isoformat(), "host": self.host, "endpoints": {}}

        async with httpx.AsyncClient() as client:
            # 健康检查
            try:
                response = await client.get(f"{self.host}/health", timeout=5.0)
                self.results["health_check"] = {
                    "status": response.status_code,
                    "response_time": (datetime.now() - datetime.now()).total_seconds() * 1000,
                }
            except Exception as e:
                self.results["health_check"] = {"error": str(e)}

            # GET /api/v1/documents
            self.results["endpoints"]["GET /api/v1/documents"] = await self.measure_endpoint(
                client, "GET", "/api/v1/documents", params={"limit": 20}
            )

            # GET /api/v1/search
            self.results["endpoints"]["GET /api/v1/search"] = await self.measure_endpoint(
                client, "GET", "/api/v1/search", params={"q": "气功", "limit": 10}
            )

            # POST /api/v1/ask
            self.results["endpoints"]["POST /api/v1/ask"] = await self.measure_endpoint(
                client,
                "POST",
                "/api/v1/ask",
                json={"question": "什么是气功？", "session_id": "benchmark"},
            )

            # POST /api/v1/search/hybrid
            self.results["endpoints"]["POST /api/v1/search/hybrid"] = await self.measure_endpoint(
                client,
                "POST",
                "/api/v1/search/hybrid",
                json={"query": "气功", "top_k": 10, "use_vector": True, "use_bm25": True},
            )

        return self.results

    def save_results(self) -> str:
        """保存基准数据"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = self.output_dir / f"benchmark_{timestamp}.json"

        with open(json_file, "w") as f:
            json.dump(self.results, f, indent=2)

        return str(json_file)

    def compare_with_baseline(self, baseline_file: str) -> Dict[str, Any]:
        """与基准数据对比"""
        with open(baseline_file, "r") as f:
            baseline = json.load(f)

        comparison = {
            "timestamp": datetime.now().isoformat(),
            "baseline_timestamp": baseline.get("timestamp"),
            "regressions": [],
            "improvements": [],
        }

        for endpoint, current_data in self.results.get("endpoints", {}).items():
            if endpoint in baseline.get("endpoints", {}):
                baseline_data = baseline["endpoints"][endpoint]

                current_p95 = current_data.get("p95", 0)
                baseline_p95 = baseline_data.get("p95", 0)

                if current_p95 > baseline_p95 * 1.1:  # 10% threshold
                    comparison["regressions"].append(
                        {
                            "endpoint": endpoint,
                            "baseline_p95": baseline_p95,
                            "current_p95": current_p95,
                            "diff_pct": (
                                ((current_p95 - baseline_p95) / baseline_p95 * 100)
                                if baseline_p95 > 0
                                else 0
                            ),
                        }
                    )
                elif current_p95 < baseline_p95 * 0.9:
                    comparison["improvements"].append(
                        {
                            "endpoint": endpoint,
                            "baseline_p95": baseline_p95,
                            "current_p95": current_p95,
                            "diff_pct": (
                                ((current_p95 - baseline_p95) / baseline_p95 * 100)
                                if baseline_p95 > 0
                                else 0
                            ),
                        }
                    )

        return comparison


async def main():
    parser = argparse.ArgumentParser(description="性能基准测试工具")
    parser.add_argument("--host", default="http://localhost:8000", help="目标主机")
    parser.add_argument("--output-dir", default="reports", help="输出目录")
    parser.add_argument("--baseline", help="基准文件路径（用于对比）")
    parser.add_argument("--set-baseline", action="store_true", help="将结果保存为新的基准")
    args = parser.parse_args()

    collector = BenchmarkCollector(args.host, args.output_dir)

    print(f"收集性能基准数据: {args.host}")
    results = await collector.collect()

    # 保存结果
    result_file = collector.save_results()
    print(f"结果已保存: {result_file}")

    # 输出摘要
    print("\n性能摘要:")
    print("-" * 60)
    for endpoint, data in results.get("endpoints", {}).items():
        if "error" not in data:
            print(f"{endpoint}")
            print(f"  P50: {data['median']:.0f}ms")
            print(f"  P95: {data['p95']:.0f}ms")
            print(f"  P99: {data['p99']:.0f}ms")
            print(f"  错误率: {data['errors']/data['count']*100:.1f}%")
        else:
            print(f"{endpoint}: {data.get('error', 'Unknown error')}")

    # 设置基准
    if args.set_baseline:
        baseline_file = Path(args.output_dir) / "baseline.json"
        with open(baseline_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n基准数据已更新: {baseline_file}")

    # 与基准对比
    if args.baseline:
        comparison = collector.compare_with_baseline(args.baseline)

        print("\n对比结果:")
        print("-" * 60)

        if comparison["regressions"]:
            print("⚠️ 性能回归:")
            for reg in comparison["regressions"]:
                print(f"  {reg['endpoint']}")
                print(
                    f"    基准: {reg['baseline_p95']:.0f}ms -> 当前: {reg['current_p95']:.0f}ms ({reg['diff_pct']:+.1f}%)"
                )
        else:
            print("✅ 无性能回归")

        if comparison["improvements"]:
            print("✨ 性能提升:")
            for imp in comparison["improvements"]:
                print(f"  {imp['endpoint']}")
                print(
                    f"    基准: {imp['baseline_p95']:.0f}ms -> 当前: {imp['current_p95']:.0f}ms ({imp['diff_pct']:+.1f}%)"
                )


if __name__ == "__main__":
    asyncio.run(main())
