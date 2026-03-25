# -*- coding: utf-8 -*-
"""
性能分析工具
Performance Analyzer

分析系统性能，包括查询响应时间、吞吐量、并发能力等
"""

import sys
sys.path.insert(0, '/home/ai/zhineng-knowledge-system/services/web_app/backend')

import asyncio
import time
import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import json
from concurrent.futures import ThreadPoolExecutor
import aiohttp

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, text

from database.models import SearchHistory, Document, User
from common.logging_config import setup_logging

logger = setup_logging(__name__)

# =============================================================================
# 配置
# =============================================================================

DATABASE_URL = "postgresql+asyncpg://tcm_admin:tcm_secure_pass_2024@localhost:5432/tcm_kb"
API_BASE_URL = "http://localhost:8000"
OUTPUT_DIR = Path("/home/ai/zhineng-knowledge-system/analytics/reports")

# =============================================================================
# 性能测试类
# =============================================================================

class PerformanceAnalyzer:
    """性能分析器"""

    def __init__(self, engine, output_dir: Path = OUTPUT_DIR):
        self.engine = engine
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async def analyze_query_performance(self) -> Dict[str, Any]:
        """分析查询性能"""
        logger.info("Analyzing query performance...")

        async with self.session_factory() as session:
            # 获取搜索历史数据
            result = await session.execute(
                select(SearchHistory)
                .order_by(SearchHistory.created_at.desc())
                .limit(10000)
            )
            histories = result.scalars().all()

            if not histories:
                return {"error": "No search history found"}

            # 计算响应时间统计
            response_times = [h.response_time_ms for h in histories]

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

            # 按搜索类型分组
            type_stats = {}
            for hist in histories:
                search_type = hist.search_type
                if search_type not in type_stats:
                    type_stats[search_type] = []
                type_stats[search_type].append(hist.response_time_ms)

            for search_type, times in type_stats.items():
                type_stats[search_type] = {
                    "count": len(times),
                    "mean_ms": statistics.mean(times),
                    "median_ms": statistics.median(times),
                    "p95_ms": self._percentile(times, 95),
                }

            stats["by_search_type"] = type_stats

        logger.info(f"✅ Query performance analysis complete")
        return stats

    async def analyze_throughput(self, duration_seconds: int = 60) -> Dict[str, Any]:
        """分析吞吐量"""
        logger.info(f"Analyzing throughput for {duration_seconds}s...")

        # 并发执行多个查询
        concurrent_levels = [1, 5, 10, 20, 50]
        results = {}

        async with aiohttp.ClientSession() as session:
            for concurrency in concurrent_levels:
                logger.info(f"Testing concurrency level: {concurrency}")

                tasks = []
                start_time = time.time()
                request_count = 0

                while time.time() - start_time < duration_seconds:
                    # 创建并发任务
                    batch_tasks = []
                    for _ in range(concurrency):
                        task = self._make_search_request(session)
                        batch_tasks.append(task)
                        request_count += 1

                    # 执行并发任务
                    batch_times = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    successful_times = [t for t in batch_times if isinstance(t, float) and t > 0]

                    if successful_times:
                        tasks.extend(successful_times)

                    # 控制测试时长
                    if time.time() - start_time >= duration_seconds:
                        break

                # 计算统计数据
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

        logger.info(f"✅ Throughput analysis complete")
        return results

    async def _make_search_request(self, session: aiohttp.ClientSession) -> float:
        """执行搜索请求"""
        start_time = time.time()
        try:
            async with session.get(
                f"{API_BASE_URL}/api/search",
                params={
                    "query": "测试",
                    "limit": 10,
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    end_time = time.time()
                    return (end_time - start_time) * 1000
                else:
                    return 0
        except Exception as e:
            logger.warning(f"Search request failed: {e}")
            return 0

    async def analyze_database_performance(self) -> Dict[str, Any]:
        """分析数据库性能"""
        logger.info("Analyzing database performance...")

        stats = {}

        async with self.session_factory() as session:
            # 测试表扫描性能
            for table_name in ["users", "documents", "document_chunks"]:
                start_time = time.time()
                result = await session.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                )
                count = result.scalar()
                end_time = time.time()

                stats[f"{table_name}_scan_ms"] = (end_time - start_time) * 1000
                stats[f"{table_name}_count"] = count

            # 测试索引使用
            for table_name in ["users", "documents"]:
                start_time = time.time()
                result = await session.execute(
                    text(f"SELECT COUNT(*) FROM {table_name} ORDER BY id LIMIT 1")
                )
                count = result.scalar()
                end_time = time.time()

                stats[f"{table_name}_index_scan_ms"] = (end_time - start_time) * 1000

            # 测试连接查询性能
            start_time = time.time()
            result = await session.execute(
                select(User, Document)
                .join(Document, User.id == Document.uploader_id)
                .limit(100)
            )
            results = result.fetchall()
            end_time = time.time()

            stats["join_query_ms"] = (end_time - start_time) * 1000
            stats["join_query_count"] = len(results)

        logger.info(f"✅ Database performance analysis complete")
        return stats

    async def analyze_system_health(self) -> Dict[str, Any]:
        """分析系统健康状态"""
        logger.info("Analyzing system health...")

        stats = {}

        async with self.session_factory() as session:
            # 数据统计
            for model, name in [(User, "users"), (Document, "documents"), (SearchHistory, "searches")]:
                result = await session.execute(
                    select(func.count(model.id))
                )
                stats[f"{name}_count"] = result.scalar()

            # 活跃用户
            result = await session.execute(
                select(func.count(User.id)).where(User.is_active == True)
            )
            stats["active_users"] = result.scalar()

            # 最近搜索（24小时内）
            from datetime import timedelta
            recent = datetime.now() - timedelta(days=1)
            result = await session.execute(
                select(func.count(SearchHistory.id)).where(
                    SearchHistory.created_at >= recent
                )
            )
            stats["recent_searches_24h"] = result.scalar()

        logger.info(f"✅ System health analysis complete")
        return stats

    def _percentile(self, data: List[float], p: int) -> float:
        """计算百分位数"""
        sorted_data = sorted(data)
        index = (len(data) - 1) * p / 100
        return sorted_data[int(index)]

    async def generate_report(self) -> Dict[str, Any]:
        """生成性能分析报告"""
        logger.info("=" * 50)
        logger.info("Generating Performance Analysis Report")
        logger.info("=" * 50)

        report = {
            "timestamp": datetime.now().isoformat(),
            "query_performance": await self.analyze_query_performance(),
            "system_health": await self.analyze_system_health(),
        }

        # 数据库性能（可选）
        try:
            report["database_performance"] = await self.analyze_database_performance()
        except Exception as e:
            logger.warning(f"Database performance analysis skipped: {e}")

        # 保存报告
        report_file = self.output_dir / f"performance_report_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"✅ Performance report saved to {report_file}")

        # 生成摘要
        summary_file = self.output_dir / "performance_summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=" * 50 + "\n")
            f.write("性能分析摘要\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"报告时间: {report['timestamp']}\n\n")

            # 查询性能摘要
            query_perf = report.get("query_performance", {})
            if "mean_ms" in query_perf:
                f.write("【查询性能】\n")
                f.write(f"平均响应时间: {query_perf['mean_ms']:.2f}ms\n")
                f.write(f"P95响应时间: {query_perf['p95_ms']:.2f}ms\n")
                f.write(f"最大响应时间: {query_perf['max_ms']:.2f}ms\n")
                f.write(f"最小响应时间: {query_perf['min_ms']:.2f}ms\n\n")

            # 系统健康摘要
            health = report.get("system_health", {})
            f.write("【系统健康】\n")
            f.write(f"用户总数: {health.get('users_count', 0)}\n")
            f.write(f"活跃用户: {health.get('active_users', 0)}\n")
            f.write(f"文档总数: {health.get('documents_count', 0)}\n")
            f.write(f"搜索总数: {health.get('searches_count', 0)}\n")
            f.write(f"最近24小时搜索: {health.get('recent_searches_24h', 0)}\n\n")

        logger.info(f"✅ Summary saved to {summary_file}")

        return report


# =============================================================================
# 主函数
# =============================================================================

async def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("Starting Performance Analysis")
    logger.info("=" * 50)

    try:
        # 创建数据库引擎
        engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_size=10,
            max_overflow=20
        )

        # 创建性能分析器
        analyzer = PerformanceAnalyzer(engine)

        # 生成报告
        report = await analyzer.generate_report()

        logger.info("=" * 50)
        logger.info("Performance Analysis Complete")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Error analyzing performance: {e}", exc_info=True)
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
