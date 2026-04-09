#!/usr/bin/env python3
"""LingMinOpt自动优化 - 非交互式持续运行版本"""
import asyncio
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.evolution.lingminopt import get_lingminopt_framework


class AutoOptimizationService:
    """自动优化服务"""

    def __init__(self, check_interval: int = 300):  # 5分钟检查一次
        self.framework = get_lingminopt_framework()
        self.check_interval = check_interval
        self.optimization_count = 0
        self.is_running = False

    async def start(self):
        """启动自动优化服务"""
        self.is_running = True

        # 设置日志
        import logging

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("/tmp/lingminopt_auto.log"), logging.StreamHandler()],
        )

        logger = logging.getLogger(__name__)
        logger.info("=" * 70)
        logger.info("🚀 LingMinOpt自动优化服务启动")
        logger.info("=" * 70)
        logger.info(f"⏱️  检查间隔: {self.check_interval}秒 ({self.check_interval/60:.1f}分钟)")
        logger.info("🔄 模式: 持续自动优化")
        logger.info("=" * 70)
        logger.info("")

        # 设置优雅退出
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self._shutdown()))

        # 主循环
        while self.is_running:
            try:
                self.optimization_count += 1

                logger.info(f"{'='*70}")
                logger.info(f"🔄 优化轮次 #{self.optimization_count}")
                logger.info(f"⏰ 时间: {datetime.now().isoformat()}")
                logger.info("=" * 70)

                # 执行优化
                await self._run_optimization_round()

                # 显示当前状态
                self._log_current_status()

                # 等待下一轮
                if self.is_running:
                    logger.info(f"⏳ 等待 {self.check_interval}秒 后进行下一轮优化...")
                    logger.info("")

                    await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"优化循环出错: {e}")
                logger.info("等待60秒后继续...")
                await asyncio.sleep(60)

    async def _run_optimization_round(self):
        """执行一轮优化"""
        logger = logging.getLogger(__name__)

        # 1. 收集指标
        logger.info("📊 第1步: 收集系统指标...")
        snapshot = await self.framework.metrics_collector.collect_snapshot()
        logger.info(f"当前指标: {snapshot.metrics}")

        # 2. 分析优化机会
        logger.info("🔍 第2步: 分析优化机会...")
        opportunities = await self.framework.optimizer.identify_bottlenecks(snapshot.metrics)
        logger.info(f"发现 {len(opportunities)} 个优化机会")

        for opp in opportunities:
            logger.info(f"  - [{opp.priority.value}] {opp.title}: {opp.expected_improvement}")

        # 3. 执行优化（仅Phase 1: 立即优化）
        if opportunities:
            critical_ops = [opp for opp in opportunities if opp.priority.value == "critical"]

            if critical_ops:
                logger.info("⚡ 第3步: 执行关键优化...")
                for opp in critical_ops:
                    try:
                        result = await self.framework.orchestrator.execute_optimization(
                            opp, {"metrics_collector": self.framework.metrics_collector}
                        )

                        if result.success:
                            logger.info(f"✅ {opp.title} - 成功")
                        else:
                            logger.warning(f"❌ {opp.title} - 失败")

                    except Exception as e:
                        logger.error(f"❌ {opp.title} - 错误: {e}")

    def _log_current_status(self):
        """记录当前状态"""
        logger = logging.getLogger(__name__)

        stats = self.framework.orchestrator.optimization_results
        logger.info("📊 当前统计:")
        logger.info(f"  优化轮次: {self.optimization_count}")
        logger.info(f"  成功优化: {len([r for r in stats if r.success])}")
        logger.info(f"  失败优化: {len([r for r in stats if not r.success])}")

    async def _shutdown(self):
        """优雅退出"""
        logger = logging.getLogger(__name__)
        logger.info("")
        logger.info("=" * 70)
        logger.info("⏸️  接收到停止信号，正在优雅退出...")
        logger.info("=" * 70)

        self.is_running = False

        logger.info("📊 本次会话总结:")
        logger.info(f"  优化轮次: {self.optimization_count}")
        logger.info(f"  结束时间: {datetime.now().isoformat()}")

        logger.info("")
        logger.info("✅ 自动优化服务已停止")
        logger.info("=" * 70)


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="LingMinOpt自动优化服务")
    parser.add_argument(
        "--interval", type=int, default=300, help="检查间隔（秒），默认300秒（5分钟）"
    )

    args = parser.parse_args()

    service = AutoOptimizationService(check_interval=args.interval)

    print()
    print("🚀 LingMinOpt自动优化服务")
    print()
    print(f"⏱️  检查间隔: {args.interval}秒 ({args.interval/60:.1f}分钟)")
    print("📝 日志文件: /tmp/lingminopt_auto.log")
    print()
    print("💡 提示: 使用 'tail -f /tmp/lingminopt_auto.log' 查看实时日志")
    print("💡 停止: kill $(pgrep -f 'auto_optimization_service' | awk '{print $1}')")
    print()
    print("=" * 70)
    print("🔄 启动自动优化...")
    print("=" * 70)
    print()

    await service.start()


if __name__ == "__main__":
    asyncio.run(main())
