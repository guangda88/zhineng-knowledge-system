#!/usr/bin/env python3
"""
Test CLIProxyAPI Integration

This script tests the CLIProxyAPI integration with the ZhiNeng system.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import AsyncOpenAI

from backend.services.ai_service_adapter import AIServiceAdapter, TaskType, UnifiedAIService

# Test configuration
CLIPROXYAPI_BASE_URL = os.getenv("CLIPROXYAPI_BASE_URL", "http://localhost:8317/v1")
CLIPROXYAPI_API_KEY = os.getenv("CLIPROXYAPI_API_KEY", "lingzhi-api-key-001")


async def test_health_check():
    """Test CLIProxyAPI health check endpoint"""
    print("\n" + "=" * 60)
    print("Test 1: Health Check")
    print("=" * 60)

    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8317/health") as resp:
                if resp.status == 200:
                    print("✅ Health check passed")
                    data = await resp.json()
                    print(f"   Response: {data}")
                    return True
                else:
                    print(f"❌ Health check failed: status {resp.status}")
                    return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


async def test_basic_chat():
    """Test basic chat completion"""
    print("\n" + "=" * 60)
    print("Test 2: Basic Chat Completion")
    print("=" * 60)

    adapter = AIServiceAdapter(base_url=CLIPROXYAPI_BASE_URL, api_key=CLIPROXYAPI_API_KEY)

    messages = [
        {"role": "system", "content": "你是一个友好的助手。"},
        {"role": "user", "content": "你好！请用一句话介绍你自己。"},
    ]

    try:
        response = await adapter.chat(messages=messages, task_type=TaskType.CHAT, max_tokens=100)

        print("✅ Chat completion successful")
        print(f"   Model: {response['model']}")
        print(f"   Content: {response['content']}")
        print(f"   Tokens: {response['usage']['total_tokens']}")
        return True

    except Exception as e:
        print(f"❌ Chat completion failed: {e}")
        return False


async def test_task_based_model_selection():
    """Test task-based model selection"""
    print("\n" + "=" * 60)
    print("Test 3: Task-Based Model Selection")
    print("=" * 60)

    adapter = AIServiceAdapter()

    test_cases = [
        (TaskType.REASONING, "什么是智能气功的混元灵通原理？"),
        (TaskType.CODING, "写一个Python函数计算斐波那契数列"),
        (TaskType.CHINESE, "解释组场发气的概念"),
        (TaskType.SUMMARIZATION, "请总结以下内容：智能气功是一种通过意念来调节身心的方法。"),
    ]

    all_passed = True

    for task_type, prompt in test_cases:
        print(f"\n   Testing task: {task_type.value}")

        messages = [{"role": "user", "content": prompt}]

        try:
            response = await adapter.chat(messages=messages, task_type=task_type, max_tokens=50)

            print(f"   ✅ {task_type.value}: {response['model']}")

        except Exception as e:
            print(f"   ❌ {task_type.value} failed: {e}")
            all_passed = False

    return all_passed


async def test_rag_query():
    """Test RAG query with context"""
    print("\n" + "=" * 60)
    print("Test 4: RAG Query")
    print("=" * 60)

    service = UnifiedAIService()

    query = "什么是混元灵通？"
    context = [
        {
            "title": "智能气功基础理论",
            "content": "混元灵通是智能气功的核心理论，强调通过意念来统一身心，达到与自然界的混元状态。",
        },
        {
            "title": "组场方法",
            "content": "组场是智能气功的重要练习方法，通过集体意念形成气场，增强练习效果。",
        },
    ]

    try:
        answer = await service.rag_query(query=query, context=context, max_tokens=500)

        print("✅ RAG query successful")
        print(f"   Query: {query}")
        print(f"   Answer: {answer}")
        return True

    except Exception as e:
        print(f"❌ RAG query failed: {e}")
        return False


async def test_audio_analysis():
    """Test audio transcript analysis"""
    print("\n" + "=" * 60)
    print("Test 5: Audio Transcript Analysis")
    print("=" * 60)

    service = UnifiedAIService()

    transcript = """
    智能气功的混元灵通理论认为，通过意念的集中和引导，
    可以调节人体的气血运行，达到强身健体的效果。
    组场练习时，大家要集中注意力，意念统一。
    """

    try:
        # Test summarization
        print("\n   Testing summarization...")
        summary = await service.summarize_audio_transcript(transcript=transcript, max_length=100)
        print(f"   ✅ Summary: {summary}")

        # Test ASR correction
        print("\n   Testing ASR error correction...")
        corrected = await service.correct_asr_errors(transcript=transcript, domain="qigong")
        print(f"   ✅ Corrected: {corrected[:100]}...")

        return True

    except Exception as e:
        print(f"❌ Audio analysis failed: {e}")
        return False


async def test_streaming():
    """Test streaming chat"""
    print("\n" + "=" * 60)
    print("Test 6: Streaming Chat")
    print("=" * 60)

    adapter = AIServiceAdapter()

    messages = [{"role": "user", "content": "请数到5，每个数字单独输出"}]

    try:
        print("   Streaming response:")
        async for chunk in adapter.stream_chat(messages=messages, task_type=TaskType.CHAT):
            print(f"   {chunk}", end="", flush=True)

        print("\n   ✅ Streaming successful")
        return True

    except Exception as e:
        print(f"❌ Streaming failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("CLIProxyAPI Integration Test Suite")
    print("=" * 60)
    print(f"\nTesting endpoint: {CLIPROXYAPI_BASE_URL}")

    tests = [
        ("Health Check", test_health_check),
        ("Basic Chat", test_basic_chat),
        ("Task-Based Selection", test_task_based_model_selection),
        ("RAG Query", test_rag_query),
        ("Audio Analysis", test_audio_analysis),
        ("Streaming", test_streaming),
    ]

    results = {}

    for name, test_func in tests:
        try:
            results[name] = await test_func()
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results[name] = False

    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(results.values())

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
