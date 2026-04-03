#!/usr/bin/env python3
"""多AI API连接测试脚本

测试混元、DeepSeek等API的连接和调用
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx


async def test_hunyuan():
    """测试混元API"""
    api_key = os.getenv("HUNYUAN_API_KEY")

    if not api_key:
        print("⚠️  HUNYUAN_API_KEY 未设置，跳过测试")
        return False

    print("🧪 测试混元API...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "hunyuan-lite",
                    "messages": [
                        {"role": "user", "content": "你好，请用一句话介绍你自己。"}
                    ],
                    "max_tokens": 100
                }
            )
            response.raise_for_status()
            result = response.json()

        print("✅ 混元API连接成功！")
        print(f"   回复: {result['choices'][0]['message']['content']}")

        return True

    except Exception as e:
        print(f"❌ 混元API连接失败: {e}")
        return False


async def test_deepseek():
    """测试DeepSeek API"""
    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        print("⚠️  DEEPSEEK_API_KEY 未设置，跳过测试")
        return False

    print("🧪 测试DeepSeek API...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "user", "content": "你好，请用一句话介绍你自己。"}
                    ],
                    "max_tokens": 100
                }
            )
            response.raise_for_status()
            result = response.json()

        print("✅ DeepSeek API连接成功！")
        print(f"   回复: {result['choices'][0]['message']['content']}")

        return True

    except Exception as e:
        print(f"❌ DeepSeek API连接失败: {e}")
        return False


async def test_mock_response():
    """测试mock响应（无需API密钥）"""
    print("🧪 测试Mock响应...")

    # 导入多AI适配器
    from backend.services.evolution.multi_ai_adapter import get_multi_ai_adapter

    adapter = get_multi_ai_adapter()

    # 测试mock响应
    result = await adapter._adapters["lingzhi"].generate(
        prompt="测试",
        request_type="qa"
    )

    print("✅ Mock响应测试成功！")
    print(f"   Lingzhi响应: {result['content'][:50]}...")

    return True


async def main():
    """主测试函数"""
    print("=" * 60)
    print("🚀 多AI API连接测试")
    print("=" * 60)
    print()

    # 测试真实API
    hunyuan_ok = await test_hunyuan()
    print()

    deepseek_ok = await test_deepseek()
    print()

    # 测试mock响应
    mock_ok = await test_mock_response()
    print()

    # 总结
    print("=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    print(f"混元API: {'✅ 连接成功' if hunyuan_ok else '⚠️  未配置或连接失败'}")
    print(f"DeepSeek API: {'✅ 连接成功' if deepseek_ok else '⚠️  未配置或连接失败'}")
    print(f"Mock响应: {'✅ 正常' if mock_ok else '❌ 异常'}")
    print()

    if hunyuan_ok or deepseek_ok:
        print("🎉 可以开始使用多AI对比功能！")
    else:
        print("💡 提示：API密钥未配置，将使用Mock响应进行开发测试")
        print("   配置方法：参考 docs/AI_API_SETUP_GUIDE.md")

    print()
    print("**众智混元，万法灵通** ⚡🚀")


if __name__ == "__main__":
    asyncio.run(main())
