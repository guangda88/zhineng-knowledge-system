#!/usr/bin/env python3
"""Token池监控完整演示

展示监控系统的所有功能
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from backend.services.ai_service import chat, format_pool_status, generate_code, reason
from backend.services.evolution.token_monitor import get_token_monitor


async def demo():
    """完整演示"""

    print("\n" + "=" * 80)
    print("🎬 Token池监控演示")
    print("=" * 80)
    print()

    # 获取监控器
    monitor = get_token_monitor()

    print("📊 初始状态:")
    print(format_pool_status())
    print()

    print("🧪 开始测试调用...")
    print("-" * 80)

    # 测试1: 简单对话
    print("\n1️⃣ 调用1: 简单对话")
    result1 = await chat("你好，请介绍一下你自己")
    if result1:
        print(f"✅ 成功: {result1[:50]}...")

    await asyncio.sleep(1)

    # 测试2: 推理任务
    print("\n2️⃣ 调用2: 推理任务")
    result2 = await reason("解释什么是递归")
    if result2:
        print(f"✅ 成功: {result2[:50]}...")

    await asyncio.sleep(1)

    # 测试3: 代码生成
    print("\n3️⃣ 调用3: 代码生成")
    result3 = await generate_code("用Python写一个Hello World")
    if result3:
        print(f"✅ 成功: {result3[:50]}...")

    await asyncio.sleep(1)

    # 测试4: 再次对话
    print("\n4️⃣ 调用4: 再次对话")
    result4 = await chat("今天天气怎么样")
    if result4:
        print(f"✅ 成功: {result4[:50]}...")

    await asyncio.sleep(1)

    # 测试5: 复杂推理
    print("\n5️⃣ 调用5: 复杂推理")
    result5 = await reason("如何证明sqrt(2)是无理数")
    if result5:
        print(f"✅ 成功: {result5[:50]}...")

    print()
    print("-" * 80)
    print("✅ 测试调用完成")
    print()

    # 查看监控数据
    print("📊 监控报告:")
    print(monitor.format_summary(hours=1))
    print()

    # Provider对比
    print("🏆 Provider性能对比:")
    stats = monitor.get_all_stats()

    if stats:
        print(
            f"\n{'Provider':<15} {'调用':<8} {'成功':<8} {'失败':<8} {'成功率':<10} {'平均延迟':<10}"
        )
        print("-" * 80)

        for name, stat in sorted(stats.items(), key=lambda x: x[1].total_calls, reverse=True):
            if stat.total_calls > 0:
                print(
                    f"{name:<15} "
                    f"{stat.total_calls:<8} "
                    f"{stat.successful_calls:<8} "
                    f"{stat.failed_calls:<8} "
                    f"{stat.success_rate:<10.1%} "
                    f"{stat.avg_latency_ms:<10.0f}"
                )

    print()
    print("=" * 80)
    print("🎉 演示完成！")
    print("=" * 80)
    print()
    print("💡 后续操作:")
    print("  • 运行实时监控: python scripts/token_monitor_dashboard.py --realtime")
    print("  • 查看对比: python scripts/token_monitor_dashboard.py --compare")
    print("  • 导出报告: python scripts/token_monitor_dashboard.py --export")
    print()


if __name__ == "__main__":
    asyncio.run(demo())
