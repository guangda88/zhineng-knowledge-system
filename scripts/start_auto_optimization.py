#!/usr/bin/env python3
"""LingMinOpt自动优化循环启动器"""
import asyncio
import sys
import signal
from pathlib import Path
from datetime import datetime

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.evolution.lingminopt import get_lingminopt_framework


class AutoOptimizationController:
    """自动优化控制器"""

    def __init__(self):
        self.framework = get_lingminopt_framework()
        self.is_running = False
        self.optimization_count = 0

    async def start(self, check_interval: int = 3600):
        """启动自动优化循环

        Args:
            check_interval: 检查间隔（秒），默认1小时
        """
        self.is_running = True
        self.framework.optimization_interval = check_interval

        # 设置优雅退出
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self._shutdown()))

        print("=" * 70)
        print("🚀 LingMinOpt自动优化模式启动")
        print("=" * 70)
        print()
        print(f"📊 优化间隔: {check_interval}秒 ({check_interval/60:.1f}分钟)")
        print(f"🔄 循环模式: 持续运行直到手动停止")
        print()
        print("💡 提示: 按 Ctrl+C 停止优化")
        print()
        print("=" * 70)
        print()

        # 启动优化循环
        await self.framework.start_auto_optimization()

    async def _shutdown(self):
        """优雅退出"""
        print()
        print("=" * 70)
        print("⏸️  接收到停止信号，正在优雅退出...")
        print("=" * 70)

        self.is_running = False
        await self.framework.stop_auto_optimization()

        print()
        print("📊 本次优化会话总结:")
        print(f"  优化轮次: {self.optimization_count}")
        print(f"  结束时间: {datetime.now().isoformat()}")
        print()
        print("✅ 优化已安全停止")
        print("=" * 70)


async def run_with_status_updates():
    """运行带状态更新的自动优化"""

    controller = AutoOptimizationController()

    # 启动自动优化（30秒检查一次，用于演示）
    print("⚡ 启动快速演示模式（30秒检查一次）")
    print("   生产环境建议使用3600秒（1小时）")
    print()

    try:
        await controller.start(check_interval=30)
    except KeyboardInterrupt:
        print("\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
    finally:
        print("\n👋 自动优化会话结束")


async def run_single_round():
    """运行单轮优化（手动触发）"""

    print("=" * 70)
    print("🎯 手动触发单轮优化")
    print("=" * 70)
    print()

    framework = get_lingminopt_framework()

    try:
        await framework.run_manual_optimization()
    except Exception as e:
        print(f"\n❌ 优化失败: {e}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="LingMinOpt自动优化系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 启动自动优化循环（默认1小时检查一次）
  python scripts/start_auto_optimization.py start

  # 启动快速演示模式（30秒检查一次）
  python scripts/start_auto_optimization.py start --fast

  # 执行单轮优化
  python scripts/start_auto_optimization.py once

  # 仅分析当前状态
  python scripts/start_auto_optimization.py analyze
        """
    )

    parser.add_argument(
        "action",
        choices=["start", "once", "analyze"],
        help="操作: start(启动循环), once(单次优化), analyze(仅分析)"
    )

    parser.add_argument(
        "--fast",
        action="store_true",
        help="快速演示模式（30秒检查一次）"
    )

    args = parser.parse_args()

    if args.action == "start":
        # 启动自动优化循环
        interval = 30 if args.fast else 3600
        asyncio.run(run_with_status_updates())

    elif args.action == "once":
        # 执行单轮优化
        asyncio.run(run_single_round())

    elif args.action == "analyze":
        # 仅分析
        print("🔍 分析当前系统状态...")
        import subprocess
        subprocess.run([
            "python", "scripts/run_lingminopt.py"
        ])


if __name__ == "__main__":
    main()
