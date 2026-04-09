#!/usr/bin/env python3
"""Token池监控仪表板

实时查看Token池使用情况和各Provider性能
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from backend.services.ai_service import format_pool_status
from backend.services.evolution.token_monitor import get_token_monitor


async def show_dashboard():
    """显示监控仪表板"""

    print("\n" + "=" * 80)
    print("📊 Token池监控仪表板")
    print("=" * 80)
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 1. Token池状态
    print(format_pool_status())
    print()

    # 2. 监控报告
    monitor = get_token_monitor()
    print(monitor.format_summary(hours=24))
    print()

    # 3. 性能排行
    print("🏆 性能排行榜 (24小时)")
    print("-" * 80)

    summary = monitor.get_summary(hours=24)

    if summary["providers"]:
        print(f"\n{'Provider':<15} {'调用次数':<10} {'成功率':<10} {'平均延迟':<10} {'Token使用'}")
        print("-" * 80)

        # 按成功率排序
        providers_sorted = sorted(
            summary["providers"].items(), key=lambda x: x[1]["success_rate"], reverse=True
        )

        for provider, stats in providers_sorted:
            print(
                f"{provider:<15} "
                f"{stats['calls']:<10} "
                f"{stats['success_rate']:<10.1%} "
                f"{stats['avg_latency']:<10.0f} "
                f"{stats['tokens']:,}"
            )
    else:
        print("暂无数据")

    print()
    print("=" * 80)


async def show_realtime_monitoring(interval: int = 60):
    """实时监控（自动刷新）"""

    print("\n🔄 实时监控模式启动 (每{}秒刷新)".format(interval))
    print("按 Ctrl+C 停止\n")

    try:
        while True:
            show_dashboard()
            print(f"\n⏳ 下次更新: {interval}秒后...")
            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n👋 监控已停止")


async def export_report():
    """导出监控报告"""

    monitor = get_token_monitor()

    print("\n📄 导出监控报告")
    print("-" * 80)

    # 导出24小时记录
    records = monitor.export_records(hours=24)

    print(f"✅ 导出记录数: {len(records)}")

    # 保存到文件
    report_file = (
        Path("data/monitoring") / f"token_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    report_file.parent.mkdir(parents=True, exist_ok=True)

    import json

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "export_time": datetime.now().isoformat(),
                "summary": monitor.get_summary(hours=24),
                "records": records,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"✅ 报告已保存: {report_file}")


async def show_provider_comparison():
    """Provider对比分析"""

    monitor = get_token_monitor()
    stats = monitor.get_all_stats()

    print("\n📊 Provider详细对比")
    print("=" * 80)

    if not stats:
        print("暂无统计数据")
        return

    print(
        f"\n{'Provider':<15} {'总调用':<10} {'成功':<10} {'失败':<10} {'成功率':<10} {'平均延迟':<10} {'总Token'}"
    )
    print("-" * 100)

    for name, stat in sorted(stats.items(), key=lambda x: x[1].total_calls, reverse=True):
        print(
            f"{name:<15} "
            f"{stat.total_calls:<10} "
            f"{stat.successful_calls:<10} "
            f"{stat.failed_calls:<10} "
            f"{stat.success_rate:<10.1%} "
            f"{stat.avg_latency_ms:<10.0f} "
            f"{stat.total_tokens:,}"
        )

    print("\n错误统计:")
    for name, stat in stats.items():
        if stat.errors:
            print(f"\n{name}:")
            for error, count in sorted(stat.errors.items(), key=lambda x: x[1], reverse=True):
                print(f"  - {error}: {count}次")


async def main():
    """主函数"""

    import argparse

    parser = argparse.ArgumentParser(description="Token池监控仪表板")
    parser.add_argument("--realtime", "-r", action="store_true", help="实时监控模式")
    parser.add_argument("--interval", "-i", type=int, default=60, help="刷新间隔（秒）")
    parser.add_argument("--export", "-e", action="store_true", help="导出报告")
    parser.add_argument("--compare", "-c", action="store_true", help="Provider对比")

    args = parser.parse_args()

    if args.realtime:
        await show_realtime_monitoring(args.interval)
    elif args.export:
        await export_report()
    elif args.compare:
        await show_provider_comparison()
    else:
        await show_dashboard()


if __name__ == "__main__":
    asyncio.run(main())
