#!/usr/bin/env python3
"""LingMinOpt自动优化监控面板"""
import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.evolution.lingminopt import get_lingminopt_framework


class OptimizationMonitor:
    """优化监控面板"""

    def __init__(self):
        self.framework = get_lingminopt_framework()
        self.check_interval = 30  # 30秒检查一次
        self.max_iterations = 10  # 最多运行10轮（演示用）

    async def start_monitoring(self):
        """启动监控"""

        print("=" * 70)
        print("📊 LingMinOpt自动优化监控面板")
        print("=" * 70)
        print()
        print(f"⏱️  检查间隔: {self.check_interval}秒")
        print(f"🔄 最大轮次: {self.max_iterations}")
        print()
        print("💡 提示: 按 Ctrl+C 停止监控")
        print()
        print("=" * 70)
        print()

        iteration = 0

        try:
            while iteration < self.max_iterations:
                iteration += 1

                # 显示轮次标题
                print(f"\n{'='*70}")
                print(f"🔄 优化轮次 #{iteration}")
                print(f"⏰ 时间: {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 70)
                print()

                # 执行一轮优化
                await self.framework.optimization_loop()

                # 显示进度条
                progress = iteration / self.max_iterations
                bar_length = 40
                filled = int(bar_length * progress)
                bar = "█" * filled + "░" * (bar_length - filled)

                print(f"\n📊 总体进度: [{bar}] {progress*100:.0f}%")

                # 如果不是最后一轮，显示等待倒计时
                if iteration < self.max_iterations:
                    print(f"\n⏳ 等待 {self.check_interval}秒 后进行下一轮优化...")
                    print()

                    # 倒计时显示
                    for i in range(self.check_interval, 0, -5):
                        remaining = i
                        mins, secs = divmod(remaining, 60)
                        print(f"   ⏰ 剩余时间: {mins:02d}:{secs:02d}", end="\r")
                        await asyncio.sleep(5)

                    print()  # 换行

        except KeyboardInterrupt:
            print("\n\n⏸️  用户中断监控")

        # 显示最终总结
        print("\n" + "=" * 70)
        print("📊 监控会话总结")
        print("=" * 70)
        print()
        print(f"总优化轮次: {iteration}")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # 显示最终统计
        stats = self.framework.metrics_collector.get_final_stats()
        print("最终指标:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        print()
        print("=" * 70)
        print("✅ 监控已停止")
        print("=" * 70)

    async def show_realtime_dashboard(self):
        """显示实时仪表板"""

        try:
            while True:
                # 清屏（可选）
                # print("\033[2J\033[H", end="")

                print("\n" + "=" * 70)
                print("📊 LingMinOpt实时监控仪表板")
                print("=" * 70)
                print()

                # 显示当前时间
                now = datetime.now()
                print(f"⏰ 时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                print()

                # 收集当前指标
                snapshot = await self.framework.metrics_collector.collect_snapshot()

                # 显示指标卡片
                self._display_metric_card(
                    "API延迟", snapshot.metrics["avg_api_latency_ms"], "ms", "200", 300
                )
                self._display_metric_card(
                    "API成功率", snapshot.metrics["api_success_rate"] * 100, "%", 98, 95
                )
                self._display_metric_card(
                    "用户满意度", snapshot.metrics["avg_user_satisfaction"], "/5", 4.0, 3.8
                )
                self._display_metric_card(
                    "竞品胜率", snapshot.metrics["competitor_win_rate"] * 100, "%", 50, 45
                )
                self._display_metric_card(
                    "每日成本", f"¥{snapshot.metrics['daily_cost']:.2f}", "", 10, 15
                )

                print()
                print("-" * 70)
                print()

                # 显示最近优化记录
                print("📋 最近优化记录:")
                print()

                results = self.framework.orchestrator.optimization_results
                if results:
                    for result in results[-3:]:  # 显示最近3个
                        status_icon = "✅" if result.success else "❌"
                        print(f"  {status_icon} {result.opportunity_id}")
                        print(f"     时间: {result.executed_at.strftime('%H:%M:%S')}")
                        if result.improvement:
                            improvements = ", ".join(
                                [f"{k}:{v:+.0%}" for k, v in result.improvement.items()]
                            )
                            print(f"     改进: {improvements}")
                        print()
                else:
                    print("  (暂无优化记录)")
                    print()

                # 显示下一轮倒计时
                print("-" * 70)
                next_time = now + timedelta(seconds=self.check_interval)
                print(f"⏳ 下次检查: {next_time.strftime('%H:%M:%S')}")
                print()

                # 等待一段时间再更新
                await asyncio.sleep(10)  # 每10秒更新一次仪表板

        except KeyboardInterrupt:
            print("\n\n⏸️  仪表板已停止")

    def _display_metric_card(self, title: str, value, unit: str, target, current):
        """显示指标卡片"""

        # 简单的可视化
        if isinstance(value, (int, float)):
            if target and current:
                # 计算状态
                if title == "API延迟":
                    status = "🟢" if value <= target else "🟡" if value <= current else "🔴"
                elif title == "API成功率":
                    status = "🟢" if value >= target else "🟡" if value >= current else "🔴"
                else:
                    status = "🟢" if value >= target else "🟡"
            else:
                status = "⚪"
        else:
            status = "⚪"

        print(f"{status} {title}: {value}{unit}")

        if target and current:
            # 显示目标
            if isinstance(current, (int, float)):
                if title == "每日成本":
                    # 成本越低越好
                    arrow = "↓" if value < current else "↑"
                else:
                    # 其他指标越高越好
                    arrow = "↑" if value > current else "↓"
                print(f"   目标: {target}{unit} {arrow}")


async def run_interactive_mode():
    """运行交互式监控模式"""

    monitor = OptimizationMonitor()

    print(
        """
╔═══════════════════════════════════════════════════════════════════════════╗
║                   选择模式                                                ║
╚═══════════════════════════════════════════════════════════════════════════╝

1. 自动优化循环 - 持续运行，自动优化
2. 实时仪表板 - 显示实时指标和优化状态
3. 单轮优化 - 执行一次优化后退出
0. 退出
"""
    )

    while True:
        try:
            choice = input("请选择模式 [0-3]: ").strip()

            if choice == "0":
                print("\n👋 再见！")
                break

            elif choice == "1":
                print("\n🔄 启动自动优化循环...")
                await monitor.start_monitoring()
                break

            elif choice == "2":
                print("\n📊 启动实时仪表板...")
                await monitor.show_realtime_dashboard()
                break

            elif choice == "3":
                print("\n🎯 执行单轮优化...")
                await monitor.framework.run_manual_optimization()
                break

            else:
                print("\n❌ 无效选择，请输入 0-3")

        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break


def main():
    """主函数"""

    # 直接启动监控仪表板（更直观）
    print("🚀 启动LingMinOpt自动优化监控")
    print()
    print("模式: 实时仪表板")
    print("更新频率: 每10秒")
    print("停止方式: 按 Ctrl+C")
    print()
    print("=" * 70)
    print()

    try:
        asyncio.run(run_interactive_mode())
    except KeyboardInterrupt:
        print("\n\n👋 监控已停止")


if __name__ == "__main__":
    main()
