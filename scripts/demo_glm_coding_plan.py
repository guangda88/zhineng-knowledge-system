#!/usr/bin/env python3
"""GLM Coding Plan 使用演示

展示如何使用包月的GLM Coding Plan进行代码开发
"""
import asyncio
import sys
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.services.ai_service import (
    code_development,
    debug_code,
    code_review,
    format_pool_status
)


async def demo():
    """演示GLM Coding Plan的使用"""

    print("\n" + "=" * 80)
    print("🎬 GLM Coding Plan 使用演示")
    print("=" * 80)
    print()

    # 显示Token池状态
    print("📊 Token池状态:")
    print(format_pool_status())
    print()

    print("🔧 使用场景演示")
    print("-" * 80)

    # 场景1: 代码生成
    print("\n1️⃣ 场景: 代码生成")
    print("-" * 40)

    code_prompt = """
用Python实现一个二叉树类，支持:
1. 插入节点
2. 查找节点
3. 前序/中序/后序遍历
4. 计算树的高度
"""

    print(f"提示词: {code_prompt[:100]}...")
    print()

    result = await code_development(code_prompt)

    if result:
        print("✅ 生成的代码:")
        print(result[:500])
        print("...")
    else:
        print("❌ 生成失败")

    await asyncio.sleep(1)

    # 场景2: 代码调试
    print("\n2️⃣ 场景: 代码调试")
    print("-" * 40)

    buggy_code = """
def binary_search(arr, target):
    left, right = 0, len(arr)
    while left < right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid
    return -1
"""

    error_msg = "在查找最后一个元素时返回-1"

    print(f"问题代码:\n{buggy_code}")
    print(f"错误: {error_msg}")
    print()

    result = await debug_code(buggy_code, error_msg)

    if result:
        print("✅ 调试建议:")
        print(result[:500])
        print("...")
    else:
        print("❌ 调试失败")

    await asyncio.sleep(1)

    # 场景3: 代码审查
    print("\n3️⃣ 场景: 代码审查")
    print("-" * 40)

    code_to_review = """
def process_data(data):
    result = []
    for item in data:
        for i in range(len(item)):
            if item[i] % 2 == 0:
                result.append(item[i] * 2)
    return result
"""

    print(f"审查代码:\n{code_to_review}")
    print()

    result = await code_review(code_to_review, focus="性能")

    if result:
        print("✅ 审查意见:")
        print(result[:500])
        print("...")
    else:
        print("❌ 审查失败")

    print()
    print("=" * 80)
    print("🎉 演示完成！")
    print("=" * 80)
    print()

    print("💡 使用建议:")
    print("  • 开发场景优先使用GLM Coding Plan（包月）")
    print("  • 代码生成、调试、审查都有专用函数")
    print("  • 充分利用包月额度，不必担心费用")
    print()

    print("📖 快速开始:")
    print("""
from backend.services.ai_service import code_development, debug_code, code_review

# 代码生成
code = await code_development("实现快速排序")

# 代码调试
fix = await debug_code(buggy_code, error_msg)

# 代码审查
review = await code_review(my_code, focus="性能")
    """)


async def show_stats():
    """显示GLM Coding Plan统计"""

    from backend.services.evolution.token_monitor import get_token_monitor

    monitor = get_token_monitor()
    stats = monitor.get_provider_stats("glm_coding")

    print("\n📊 GLM Coding Plan 使用统计:")
    print("-" * 40)

    if stats.total_calls > 0:
        print(f"总调用次数: {stats.total_calls}")
        print(f"成功: {stats.successful_calls}")
        print(f"失败: {stats.failed_calls}")
        print(f"成功率: {stats.success_rate:.1%}")
        print(f"Token使用: {stats.total_tokens:,}")
        print(f"平均延迟: {stats.avg_latency_ms:.0f}ms")
    else:
        print("暂无使用数据")

    print()


async def main():
    """主函数"""

    import argparse

    parser = argparse.ArgumentParser(description="GLM Coding Plan演示")
    parser.add_argument("--stats", "-s", action="store_true", help="显示统计信息")

    args = parser.parse_args()

    if args.stats:
        await show_stats()
    else:
        await demo()

        # 显示统计
        print("\n📊 当前使用统计:")
        await show_stats()


if __name__ == "__main__":
    asyncio.run(main())
