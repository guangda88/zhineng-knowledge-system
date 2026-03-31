"""速率限制测试脚本"""

import asyncio
import aiohttp
import time

BASE_URL = "http://localhost:8000"

async def test_rate_limit():
    """测试速率限制"""
    print("🧪 测试速率限制功能...\n")

    # 测试1: 正常请求（应该成功）
    print("📝 测试1: 发送5个正常请求...")
    async with aiohttp.ClientSession() as session:
        for i in range(5):
            try:
                async with session.get(f"{BASE_URL}/health") as response:
                    print(f"  请求 {i+1}: {response.status} - ✅")
            except Exception as e:
                print(f"  请求 {i+1}: ❌ 错误 - {e}")

    # 测试2: 快速发送大量请求（应该触发速率限制）
    print("\n📝 测试2: 快速发送100个请求（应该触发429）...")
    success_count = 0
    rate_limited_count = 0
    error_count = 0

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(100):
            async def fetch():
                nonlocal success_count, rate_limited_count, error_count
                try:
                    async with session.get(f"{BASE_URL}/health") as response:
                        if response.status == 200:
                            success_count += 1
                        elif response.status == 429:
                            rate_limited_count += 1
                        else:
                            error_count += 1
                except Exception:
                    error_count += 1

            tasks.append(fetch())

        start_time = time.time()
        await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

    print(f"  总时间: {elapsed:.2f}秒")
    print(f"  成功: {success_count}")
    print(f"  速率限制: {rate_limited_count}")
    print(f"  错误: {error_count}")

    if rate_limited_count > 0:
        print("\n✅ 速率限制已启用并正常工作！")
    else:
        print("\n⚠️  未检测到速率限制，请检查配置。")

if __name__ == "__main__":
    asyncio.run(test_rate_limit())
