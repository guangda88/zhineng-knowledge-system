# -*- coding: utf-8 -*-
"""
Redis 缓存层测试脚本

测试缓存管理器和缓存服务的功能
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))


async def test_cache_manager():
    """测试缓存管理器"""
    from .cache_manager import (
        CacheManager,
        CacheKeyPattern,
        CacheTTL,
        MemoryCacheBackend,
    )

    print("=== 测试缓存管理器 ===")

    # 测试内存缓存
    print("\n1. 测试内存缓存后端")
    cache = CacheManager(backend="memory")

    # 基本操作测试
    await cache.set("test:key", {"value": "test_data"})
    value = await cache.get("test:key")
    print(f"   设置后读取: {value}")
    assert value == {"value": "test_data"}, "内存缓存读写失败"

    # 删除测试
    deleted = await cache.delete("test:key")
    print(f"   删除结果: {deleted}")
    value_after_delete = await cache.get("test:key")
    print(f"   删除后读取: {value_after_delete}")
    assert value_after_delete is None, "内存缓存删除失败"

    # 测试缓存键生成
    print("\n2. 测试缓存键生成")
    user_key = CacheKeyPattern.user_info(123)
    print(f"   用户信息键: {user_key}")

    doc_key = CacheKeyPattern.document_info(456)
    print(f"   文档信息键: {doc_key}")

    search_key = CacheKeyPattern.search_result("中医治疗", "hybrid", "tcm")
    print(f"   搜索结果键: {search_key}")

    # 测试 TTL 配置
    print("\n3. 测试 TTL 配置")
    print(f"   用户信息 TTL: {CacheTTL.USER_INFO}秒")
    print(f"   搜索结果 TTL: {CacheTTL.SEARCH_RESULT}秒")
    print(f"   热词列表 TTL: {CacheTTL.SEARCH_HOTWORD}秒")

    # 测试统计信息
    print("\n4. 测试缓存统计")
    stats = cache.get_stats()
    print(f"   缓存统计: {stats}")

    await cache.close()
    print("   内存缓存测试通过")


async def test_cache_services():
    """测试缓存服务"""
    from .cache_service import (
        UserCacheService,
        DocumentCacheService,
        SearchCacheService,
        HotwordCacheService,
    )

    print("\n=== 测试缓存服务 ===")

    cache_manager = CacheManager(backend="memory")

    # 测试用户缓存服务
    print("\n1. 测试用户缓存服务")
    user_service = UserCacheService(cache_manager=cache_manager)

    # 设置用户信息
    user_data = {
        "id": 1,
        "username": "test_user",
        "email": "test@example.com",
        "roles": ["user"],
    }
    await user_service.set_user_info(1, user_data)
    print(f"   设置用户信息: {user_data}")

    # 获取用户信息
    cached_user = await user_service.get_user_info(1)
    print(f"   获取用户信息: {cached_user}")
    assert cached_user == user_data, "用户缓存服务失败"

    # 测试文档缓存服务
    print("\n2. 测试文档缓存服务")
    doc_service = DocumentCacheService(cache_manager=cache_manager)

    doc_data = {"id": 100, "title": "测试文档", "domain": "tcm", "chunk_count": 10}
    await doc_service.set_document_info(100, doc_data)
    print(f"   设置文档信息: {doc_data}")

    cached_doc = await doc_service.get_document_info(100)
    print(f"   获取文档信息: {cached_doc}")
    assert cached_doc == doc_data, "文档缓存服务失败"

    # 测试搜索缓存服务
    print("\n3. 测试搜索缓存服务")
    search_service = SearchCacheService(cache_manager=cache_manager)

    search_result = {
        "query": "中医",
        "results": [{"id": 1, "content": "测试内容"}],
        "total": 1,
    }
    await search_service.set_search_result("中医", search_result, "hybrid", ["tcm"])
    print(f"   设置搜索结果: {search_result}")

    cached_search = await search_service.get_search_result("中医", "hybrid", ["tcm"])
    print(f"   获取搜索结果: {cached_search}")
    assert cached_search == search_result, "搜索缓存服务失败"

    # 测试热词缓存服务
    print("\n4. 测试热词缓存服务")
    hotword_service = HotwordCacheService(cache_manager=cache_manager)

    hotwords = [
        {"word": "中药", "pinyin": "zhongyao", "category": "药材"},
        {"word": "方剂", "pinyin": "fangji", "category": "处方"},
    ]
    await hotword_service.set_hotwords("tcm", hotwords)
    print(f"   设置热词: {hotwords}")

    cached_hotwords = await hotword_service.get_hotwords("tcm")
    print(f"   获取热词: {cached_hotwords}")
    assert cached_hotwords == hotwords, "热词缓存服务失败"

    await cache_manager.close()
    print("\n   缓存服务测试通过")


async def test_cache_decorator():
    """测试缓存装饰器"""
    from .cache_manager import CacheManager, cached, CacheKeyPattern

    print("\n=== 测试缓存装饰器 ===")

    cache_manager = CacheManager(backend="memory")

    # 设置全局缓存管理器
    from services.common import cache_manager as cm

    cm.set_cache_manager(cache_manager)

    call_count = {"value": 0}

    @cached(ttl=60, namespace="test")
    async def expensive_function(x: int, y: int) -> int:
        """模拟耗时函数"""
        call_count["value"] += 1
        return x + y

    # 第一次调用
    result1 = await expensive_function(1, 2)
    print(f"   第一次调用: result={result1}, call_count={call_count['value']}")

    # 第二次调用（应该从缓存获取）
    result2 = await expensive_function(1, 2)
    print(f"   第二次调用: result={result2}, call_count={call_count['value']}")

    assert call_count["value"] == 1, "装饰器缓存未生效"
    assert result1 == result2 == 3, "装饰器返回值错误"

    # 测试不同参数
    result3 = await expensive_function(2, 3)
    print(f"   不同参数调用: result={result3}, call_count={call_count['value']}")

    assert call_count["value"] == 2, "装饰器参数区分失败"
    assert result3 == 5, "装饰器返回值错误"

    await cache_manager.close()
    print("   缓存装饰器测试通过")


async def test_rate_limiting():
    """测试速率限制"""
    from .cache_manager import CacheManager

    print("\n=== 测试速率限制 ===")

    cache_manager = CacheManager(backend="memory")

    # 测试速率限制（10次/分钟）
    identifier = "test_user_123"
    endpoint = "search"

    print(f"   速率限制配置: 10次/60秒")

    for i in range(15):
        allowed, remaining = await cache_manager.check_rate_limit(
            identifier, endpoint, limit=10, window=60
        )
        status = "允许" if allowed else "拒绝"
        print(f"   请求 {i+1}: {status}, 剩余={remaining}")

    # 前10次应该允许，后5次应该拒绝
    await cache_manager.close()
    print("   速率限制测试通过")


async def main():
    """运行所有测试"""
    print("开始 Redis 缓存层测试...")

    try:
        await test_cache_manager()
        await test_cache_services()
        await test_cache_decorator()
        await test_rate_limiting()

        print("\n" + "=" * 50)
        print("所有测试通过!")
        print("=" * 50)

    except AssertionError as e:
        print(f"\n测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n测试错误: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
