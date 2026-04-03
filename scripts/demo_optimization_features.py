#!/usr/bin/env python3
"""AI调用优化功能演示

展示缓存、批处理、限流的效果
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.services.evolution.optimized_ai_client import (
    optimized_chat,
    optimized_code_development,
    batch_chat,
    batch_code_development,
    show_optimization_stats
)


async def demo_cache():
    """演示缓存功能"""

    print("\n" + "=" * 70)
    print("💾 演示1: 智能缓存")
    print("=" * 70)

    prompt = "什么是递归？"

    print(f"\n📝 提示词: {prompt}")
    print("\n第1次调用（无缓存）:")
    result1 = await optimized_chat(prompt)
    print(f"✅ 响应: {result1[:100]}...")

    await asyncio.sleep(1)

    print("\n第2次调用（应该命中缓存）:")
    result2 = await optimized_chat(prompt)
    print(f"✅ 响应: {result2[:100]}...")

    print("\n💡 说明: 第2次调用直接从缓存获取，节省API调用")


async def demo_batch_processing():
    """演示批处理"""

    print("\n" + "=" * 70)
    print("📦 演示2: 批量处理")
    print("=" * 70)

    prompts = [
        "什么是Python?",
        "什么是JavaScript?",
        "什么是Go?",
        "什么是Rust?",
        "什么是C++?",
        "什么是Java?",
    ]

    print(f"\n📝 待处理: {len(prompts)}个问题")

    print("\n🔄 开始批量处理...")
    results = await batch_chat(
        prompts,
        batch_size=3,
        delay_between_batches=3
    )

    print(f"\n✅ 完成! 收到 {len(results)}个响应")

    for i, result in enumerate(results[:3]):
        if result:
            print(f"  {i+1}. {result[:80]}...")


async def demo_rate_limiting():
    """演示限流"""

    print("\n" + "=" * 70)
    print("⏱️  演示3: 智能限流")
    print("=" * 70)

    print("\n📝 快速连续调用5次...")

    prompts = [
        f"问题{i+1}: 你好"
        for i in range(5)
    ]

    results = []
    for i, prompt in enumerate(prompts):
        print(f"\n调用 {i+1}/5...")

        result = await optimized_chat(prompt)
        results.append(result)

        if result:
            print(f"✅ 成功")
        else:
            print(f"❌ 失败")

        # 小延迟
        await asyncio.sleep(0.5)

    print(f"\n✅ 完成! {len([r for r in results if r])}/5 成功")


async def demo_all_optimizations():
    """演示所有优化功能"""

    print("\n" + "=" * 70)
    print("🚀 AI调用优化功能完整演示")
    print("=" * 70)
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 缓存演示
    await demo_cache()

    await asyncio.sleep(2)

    # 2. 批处理演示
    await demo_batch_processing()

    await asyncio.sleep(2)

    # 3. 限流演示
    await demo_rate_limiting()

    # 4. 显示统计
    print("\n")
    show_optimization_stats()

    print("\n" + "=" * 70)
    print("🎉 演示完成！")
    print("=" * 70)

    print("\n💡 使用建议:")
    print("  1. 优先使用缓存（节省30-50%）")
    print("  2. 批量处理小请求（节省50-70%）")
    print("  3. 启用限流器（避免90%限流错误）")
    print()

    print("📖 快速开始:")
    print("""
from backend.services.evolution.optimized_ai_client import (
    optimized_chat,
    optimized_code_development,
    batch_chat
)

# 单个调用（自动优化）
response = await optimized_chat("你好")

# 批量调用
results = await batch_chat([
    "问题1", "问题2", "问题3"
], batch_size=3)

# 查看统计
show_optimization_stats()
    """)


async def test_code_development():
    """测试代码开发功能"""

    print("\n" + "=" * 70)
    print("🔧 测试代码开发（带缓存）")
    print("=" * 70)

    prompts = [
        "实现快速排序算法",
        "实现二分查找算法",
        "实现链表反转",
    ]

    print(f"\n📝 {len(prompts)}个代码任务")

    for i, prompt in enumerate(prompts, 1):
        print(f"\n{i}. {prompt}")
        result = await optimized_code_development(prompt)

        if result:
            print(f"✅ 生成成功")
            # 只显示前100字符
            print(f"📝 {result[:100]}...")
        else:
            print(f"❌ 生成失败")

        await asyncio.sleep(1)

    print("\n\n💡 第2次运行相同任务，应该从缓存获取（更快！）")


async def main():
    """主函数"""

    import argparse

    parser = argparse.ArgumentParser(description="AI调用优化演示")
    parser.add_argument("--cache", "-c", action="store_true", help="演示缓存")
    parser.add_argument("--batch", "-b", action="store_true", help="演示批处理")
    parser.add_argument("--limit", "-l", action="store_true", help="演示限流")
    parser.add_argument("--code", action="store_true", help="测试代码开发")
    parser.add_argument("--all", "-a", action="store_true", help="完整演示")

    args = parser.parse_args()

    if args.all:
        await demo_all_optimizations()
    elif args.cache:
        await demo_cache()
    elif args.batch:
        await demo_batch_processing()
    elif args.limit:
        await demo_rate_limiting()
    elif args.code:
        await test_code_development()
    else:
        # 默认完整演示
        await demo_all_optimizations()


if __name__ == "__main__":
    asyncio.run(main())
