# -*- coding: utf-8 -*-
"""性能分析工具 — asyncpg 版

分析系统性能，包括查询响应时间、吞吐量、并发能力等
"""

import asyncio
import json
import logging
import os
import statistics
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

import aiohttp
import asyncpg

from backend.core.dependency_injection import get_db_pool

logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8000"
OUTPUT_DIR = Path("/home/ai/lingzhi/analytics/reports")


class PerformanceAnalyzer:
    def __init__(self, pool: asyncpg.Pool, output_dir: Path = OUTPUT_DIR):
        self.pool = pool
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def analyze_query_performance(self) -> Dict[str, Any]:
        logger.info("Analyzing query performance...")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT response_time_ms, search_type FROM search_history ORDER BY created_at DESC LIMIT 10000"
            )

            if not rows:
                return {"error": "No search history found"}

            response_times = [r["response_time_ms"] for r in rows]

            stats = {
                "count": len(response_times),
                "min_ms": min(response_times),
                "max_ms": max(response_times),
                "mean_ms": statistics.mean(response_times),
                "median_ms": statistics.median(response_times),
                "stdev_ms": statistics.stdev(response_times) if len(response_times) > 1 else 0,
                "p50_ms": self._percentile(response_times, 50),
                "p90_ms": self._percentile(response_times, 90),
                "p95_ms": self._percentile(response_times, 95),
                "p99_ms": self._percentile(response_times, 99),
            }

            type_stats: Dict[str, List[float]] = {}
            for r in rows:
                st = r["search_type"]
                type_stats.setdefault(st, []).append(r["response_time_ms"])

            stats["by_search_type"] = {
                st: {
                    "count": len(times),
                    "mean_ms": statistics.mean(times),
                    "median_ms": statistics.median(times),
                    "p95_ms": self._percentile(times, 95),
                }
                for st, times in type_stats.items()
            }

        logger.info("Done: query performance analysis")
        return stats

    async def analyze_throughput(self, duration_seconds: int = 60) -> Dict[str, Any]:
        logger.info(f"Analyzing throughput for {duration_seconds}s...")

        concurrent_levels = [1, 5, 10, 20, 50]
        results = {}

        async with aiohttp.ClientSession() as session:
            for concurrency in concurrent_levels:
                logger.info(f"Testing concurrency level: {concurrency}")
                tasks: List[float] = []
                start_time = time.time()
                request_count = 0

                while time.time() - start_time < duration_seconds:
                    batch_tasks = [self._make_search_request(session) for _ in range(concurrency)]
                    request_count += concurrency
                    batch_times = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    successful_times = [t for t in batch_times if isinstance(t, float) and t > 0]
                    tasks.extend(successful_times)
                    if time.time() - start_time >= duration_seconds:
                        break

                if tasks:
                    results[concurrency] = {
                        "requests": request_count,
                        "successful": len(tasks),
                        "failed": request_count - len(tasks),
                        "throughput_rps": len(tasks) / duration_seconds,
                        "avg_response_time_ms": statistics.mean(tasks),
                        "p95_response_time_ms": self._percentile(tasks, 95),
                    }
                else:
                    results[concurrency] = {
                        "requests": request_count,
                        "successful": 0,
                        "failed": request_count,
                        "throughput_rps": 0,
                    }

        logger.info("Done: throughput analysis")
        return results

    async def _make_search_request(self, session: aiohttp.ClientSession) -> float:
        start_time = time.time()
        try:
            async with session.get(
                f"{API_BASE_URL}/api/search",
                params={"query": "测试", "limit": 10},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    return (time.time() - start_time) * 1000
                return 0
        except Exception:
            return 0

    async def analyze_database_performance(self) -> Dict[str, Any]:
        logger.info("Analyzing database performance...")
        stats = {}

        async with self.pool.acquire() as conn:
            for table_name in ["users", "documents", "document_chunks"]:
                t0 = time.time()
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM {table_name}")
                elapsed = (time.time() - t0) * 1000
                stats[f"{table_name}_scan_ms"] = elapsed
                stats[f"{table_name}_count"] = row["cnt"]

            for table_name in ["users", "documents"]:
                t0 = time.time()
                await conn.fetchrow(f"SELECT id FROM {table_name} ORDER BY id LIMIT 1")
                elapsed = (time.time() - t0) * 1000
                stats[f"{table_name}_index_scan_ms"] = elapsed

            t0 = time.time()
            rows = await conn.fetch(
                "SELECT u.id as user_id, d.id as doc_id FROM users u JOIN documents d ON u.id = d.uploader_id LIMIT 100"
            )
            elapsed = (time.time() - t0) * 1000
            stats["join_query_ms"] = elapsed
            stats["join_query_count"] = len(rows)

        logger.info("Done: database performance analysis")
        return stats

    async def analyze_system_health(self) -> Dict[str, Any]:
        logger.info("Analyzing system health...")
        stats = {}

        async with self.pool.acquire() as conn:
            for table in ["users", "documents", "search_history"]:
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM {table}")
                stats[f"{table}_count"] = row["cnt"]

            row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM users WHERE is_active")
            stats["active_users"] = row["cnt"]

            recent = datetime.now() - timedelta(days=1)
            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM search_history WHERE created_at >= $1", recent
            )
            stats["recent_searches_24h"] = row["cnt"]

        logger.info("Done: system health analysis")
        return stats

    def _percentile(self, data: List[float], p: int) -> float:
        sorted_data = sorted(data)
        index = (len(data) - 1) * p / 100
        return sorted_data[int(index)]

    async def generate_report(self) -> Dict[str, Any]:
        logger.info("=" * 50)
        logger.info("Generating Performance Analysis Report (asyncpg)")
        logger.info("=" * 50)

        report: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "query_performance": await self.analyze_query_performance(),
            "system_health": await self.analyze_system_health(),
        }

        try:
            report["database_performance"] = await self.analyze_database_performance()
        except Exception as e:
            logger.warning(f"Database performance analysis skipped: {e}")

        report_file = self.output_dir / f"performance_report_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"Performance report saved to {report_file}")

        summary_file = self.output_dir / "performance_summary.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("=" * 50 + "\n性能分析摘要\n" + "=" * 50 + "\n\n")
            f.write(f"报告时间: {report['timestamp']}\n\n")

            query_perf = report.get("query_performance", {})
            if "mean_ms" in query_perf:
                f.write("【查询性能】\n")
                f.write(f"平均响应时间: {query_perf['mean_ms']:.2f}ms\n")
                f.write(f"P95响应时间: {query_perf['p95_ms']:.2f}ms\n")
                f.write(f"最大响应时间: {query_perf['max_ms']:.2f}ms\n")
                f.write(f"最小响应时间: {query_perf['min_ms']:.2f}ms\n\n")

            health = report.get("system_health", {})
            f.write("【系统健康】\n")
            f.write(f"用户总数: {health.get('users_count', 0)}\n")
            f.write(f"活跃用户: {health.get('active_users', 0)}\n")
            f.write(f"文档总数: {health.get('documents_count', 0)}\n")
            f.write(f"搜索总数: {health.get('search_history_count', 0)}\n")
            f.write(f"最近24小时搜索: {health.get('recent_searches_24h', 0)}\n\n")

        logger.info(f"Summary saved to {summary_file}")
        return report


async def main():
    logger.info("=" * 50)
    logger.info("Starting Performance Analysis (asyncpg)")
    logger.info("=" * 50)

    pool = get_db_pool()
    try:
        analyzer = PerformanceAnalyzer(pool)
        await analyzer.generate_report()
        logger.info("Performance Analysis Complete")
    except Exception as e:
        logger.error(f"Error analyzing performance: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
