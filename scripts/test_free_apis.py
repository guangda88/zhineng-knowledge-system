#!/usr/bin/env python3
"""免费API测试脚本

测试混元、豆包、GLM、DeepSeek等免费API是否配置正确
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.evolution.multi_ai_adapter import (
    MultiAIAdapter,
    LingzhiAdapter,
    HunyuanAdapter,
    DoubaoAdapter,
    DeepSeekAdapter,
    GLMAdapter
)


async def test_single_adapter(adapter_name: str, adapter, test_prompt: str):
    """测试单个适配器"""
    print(f"\n{'='*60}")
    print(f"🧪 测试 {adapter_name.upper()}")
    print('='*60)

    try:
        result = await adapter.generate(
            prompt=test_prompt,
            request_type="qa"
        )

        success = result.get("success", False)
        content = result.get("content", "")
        latency = result.get("latency_ms", 0)
        error = result.get("error", "")

        if success:
            print(f"✅ {adapter_name} 测试成功")
            print(f"⏱️  延迟: {latency}ms")
            print(f"📝 响应内容（前200字）:")
            print(f"   {content[:200]}...")
            return True
        else:
            print(f"❌ {adapter_name} 测试失败")
            print(f"🔴 错误: {error}")
            if "mock" in content.lower() or "模拟" in content:
                print(f"⚠️  当前使用模拟响应（未配置API密钥）")
            return False

    except Exception as e:
        print(f"❌ {adapter_name} 测试出错: {e}")
        return False


async def main():
    """主测试函数"""

    print("\n" + "="*60)
    print("🚀 免费API测试脚本")
    print("="*60)
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 测试问题
    test_prompt = "什么是气功？请用简短的语言回答。"

    # 要测试的适配器
    adapters_to_test = [
        ("hunyuan", HunyuanAdapter, "HUNYUAN_API_KEY"),
        ("doubao", DoubaoAdapter, "DOUBAO_API_KEY"),
        ("deepseek", DeepSeekAdapter, "DEEPSEEK_API_KEY"),
        ("glm", GLMAdapter, "GLM_API_KEY"),
        ("lingzhi", LingzhiAdapter, None),  # 内部系统，不需要API Key
    ]

    results = {}

    for adapter_name, adapter_class, env_key in adapters_to_test:
        # 检查环境变量（除了lingzhi）
        if env_key:
            api_key = os.getenv(env_key)
            if not api_key:
                print(f"\n⚠️  {adapter_name.upper()}: 未配置 {env_key}")
                print(f"   获取方式请参考: docs/FREE_API_ACQUISITION_GUIDE.md")
                results[adapter_name] = False
                continue
            else:
                print(f"\n✅ {adapter_name.upper()}: 已配置 {env_key}")

        # 测试适配器
        adapter = adapter_class()
        success = await test_single_adapter(adapter_name, adapter, test_prompt)
        results[adapter_name] = success

    # 总结
    print(f"\n{'='*60}")
    print("📊 测试总结")
    print('='*60)

    total = len(results)
    success_count = sum(1 for v in results.values() if v)
    fail_count = total - success_count

    print(f"总计: {total} 个API")
    print(f"✅ 成功: {success_count} 个")
    print(f"❌ 失败: {fail_count} 个")
    print(f"成功率: {success_count/total*100:.1f}%")

    # 详细结果
    print(f"\n详细结果:")
    for name, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {name.upper()}")

    # 建议
    if fail_count > 0:
        print(f"\n💡 建议:")
        print(f"   1. 参考 docs/FREE_API_ACQUISITION_GUIDE.md 获取免费API")
        print(f"   2. GLM Coding Plan: 100万tokens/月 永久免费")
        print(f"   3. 混元新用户: 100万tokens 30天")
        print(f"   4. 豆包火山引擎: 200万tokens 30天")
        print(f"   5. DeepSeek: 500万tokens 30天（最便宜）")

    print(f"\n{'='*60}\n")

    return 0 if success_count == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
