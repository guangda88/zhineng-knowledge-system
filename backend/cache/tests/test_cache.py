"""缓存系统单元测试

测试缓存管理器、Redis缓存、装饰器等功能
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.cache.decorators import (
    CacheKeyGenerator,
    CacheWarmer,
    _generate_cache_key,
    cached,
    cached_api_categories,
    cached_api_domain_stats,
    cached_api_search,
    cached_api_stats,
    memoize_async,
)
from backend.cache.manager import (
    CacheConfig,
    CacheManager,
    CacheStats,
    get_cache_manager,
    setup_cache,
)
from backend.cache.memory_cache import MemoryCache
from backend.cache.redis_cache import RedisCache, RedisConfig, RedisStatus


class TestMemoryCache:
    """内存缓存测试"""

    @pytest.fixture
    def cache(self):
        """创建缓存实例"""
        return MemoryCache(max_size=100, default_ttl=60)

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """测试设置和获取"""
        await cache.set("key1", "value1")
        value = await cache.get("key1")
        assert value == "value1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, cache):
        """测试获取不存在的键"""
        value = await cache.get("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """测试删除"""
        await cache.set("key1", "value1")
        await cache.delete("key1")
        value = await cache.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """测试清空"""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, cache):
        """测试TTL过期"""
        await cache.set("key1", "value1", ttl=1)
        value = await cache.get("key1")
        assert value == "value1"
        # 等待过期
        await asyncio.sleep(1.1)
        value = await cache.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_max_size_eviction(self):
        """测试最大容量驱逐"""
        cache = MemoryCache(max_size=3, default_ttl=60)
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        await cache.set("key4", "value4")
        # key1应该被驱逐
        assert await cache.get("key1") is None
        assert await cache.get("key4") == "value4"


class TestRedisCache:
    """Redis缓存测试"""

    @pytest.fixture
    def redis_config(self):
        """创建Redis配置"""
        return RedisConfig(
            url="redis://localhost:6379/1",  # 使用测试数据库
            key_prefix="test:",
            max_connections=10,
        )

    def test_config_creation(self, redis_config):
        """测试配置创建"""
        assert redis_config.url == "redis://localhost:6379/1"
        assert redis_config.key_prefix == "test:"
        assert redis_config.max_connections == 10

    def test_serialize_deserialize(self, redis_config):
        """测试序列化和反序列化"""
        cache = RedisCache(config=redis_config)

        # 基本类型
        assert cache._serialize("test") == "test"
        assert cache._serialize(123) == "123"
        assert cache._serialize(3.14) == "3.14"
        assert cache._serialize(True) == "True"

        # 复杂类型
        data = {"key": "value", "number": 42}
        serialized = cache._serialize(data)
        assert isinstance(serialized, str)

        deserialized = cache._deserialize(serialized)
        assert deserialized == data

    def test_make_key(self, redis_config):
        """测试键生成"""
        cache = RedisCache(config=redis_config)
        full_key = cache._make_key("my_key")
        assert full_key == "test:my_key"


class TestCacheManager:
    """缓存管理器测试"""

    @pytest.fixture
    def cache_config(self):
        """创建缓存配置"""
        return CacheConfig(
            enabled=True,
            default_ttl=3600,
            max_size=100,
        )

    @pytest.fixture
    def cache_manager(self, cache_config):
        """创建缓存管理器"""
        return CacheManager(config=cache_config)

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache_manager):
        """测试设置和获取"""
        await cache_manager.set("key1", "value1")
        value = await cache_manager.get("key1")
        assert value == "value1"

    @pytest.mark.asyncio
    async def test_get_with_default(self, cache_manager):
        """测试获取不存在的键返回默认值"""
        value = await cache_manager.get("nonexistent", default="default")
        assert value == "default"

    @pytest.mark.asyncio
    async def test_delete(self, cache_manager):
        """测试删除"""
        await cache_manager.set("key1", "value1")
        await cache_manager.delete("key1")
        value = await cache_manager.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_namespace(self, cache_manager):
        """测试命名空间"""
        await cache_manager.set("key1", "value1", namespace="ns1")
        await cache_manager.set("key1", "value2", namespace="ns2")

        value1 = await cache_manager.get("key1", namespace="ns1")
        value2 = await cache_manager.get("key1", namespace="ns2")

        assert value1 == "value1"
        assert value2 == "value2"

    @pytest.mark.asyncio
    async def test_get_or_set(self, cache_manager):
        """测试get_or_set"""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            return "computed_value"

        # 第一次调用工厂函数
        value1 = await cache_manager.get_or_set("key1", factory)
        assert value1 == "computed_value"
        assert call_count == 1

        # 第二次从缓存获取
        value2 = await cache_manager.get_or_set("key1", factory)
        assert value2 == "computed_value"
        assert call_count == 1  # 工厂函数未被再次调用

    @pytest.mark.asyncio
    async def test_stats(self, cache_manager):
        """测试统计信息"""
        await cache_manager.set("key1", "value1")
        await cache_manager.get("key1")  # hit
        await cache_manager.get("key2")  # miss

        stats = cache_manager.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_health_check(self, cache_manager):
        """测试健康检查"""
        health = await cache_manager.health_check()
        assert "status" in health
        assert "l1" in health


class TestCacheDecorators:
    """缓存装饰器测试"""

    def test_generate_cache_key_hash(self):
        """测试哈希键生成"""

        def sample_func(arg1, arg2="default"):
            return arg1 + arg2

        key = _generate_cache_key(
            sample_func,
            ("hello",),
            {"arg2": "world"},
            CacheKeyGenerator.HASH,
        )
        assert "sample_func" in key
        assert len(key.split(":")[-1]) == 16  # MD5哈希截断

    def test_generate_cache_key_json(self):
        """测试JSON键生成"""

        def sample_func(arg1):
            return arg1

        key = _generate_cache_key(
            sample_func,
            ({"data": "value"},),
            {},
            CacheKeyGenerator.JSON,
        )
        assert "sample_func" in key
        assert len(key.split(":")[-1]) == 32  # 完整MD5哈希

    @pytest.mark.asyncio
    async def test_cached_decorator(self):
        """测试缓存装饰器"""
        call_count = 0

        @cached(ttl=60)
        async def test_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # 第一次调用
        result1 = await test_function(5)
        assert result1 == 10
        assert call_count == 1

        # 第二次调用（从缓存）
        result2 = await test_function(5)
        assert result2 == 10
        assert call_count == 1  # 没有增加

    @pytest.mark.asyncio
    async def test_cached_with_different_args(self):
        """测试不同参数的缓存"""
        call_count = 0

        @cached(ttl=60)
        async def test_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        await test_function(5)
        await test_function(10)
        assert call_count == 2  # 不同参数，调用两次

    @pytest.mark.asyncio
    async def test_memoize_async(self):
        """测试memoize_async装饰器"""
        call_count = 0

        @memoize_async(ttl=60)
        async def expensive_computation(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x**2

        result1 = await expensive_computation(5)
        result2 = await expensive_computation(5)
        assert result1 == 25
        assert result2 == 25
        assert call_count == 1


class TestCacheWarmer:
    """缓存预热器测试"""

    @pytest.mark.asyncio
    async def test_cache_warm_up(self):
        """测试缓存预热"""
        warmer = CacheWarmer()

        async def mock_func(x):
            return x * 2

        warmer.add_task(mock_func, 5, ttl=60)
        warmer.add_task(mock_func, 10, ttl=60)

        results = await warmer.warm_up(batch_size=2)

        assert results["total"] == 2
        assert results["success"] == 2
        assert results["failed"] == 0


class TestApiSpecificDecorators:
    """API专用装饰器测试"""

    @pytest.mark.asyncio
    async def test_cached_api_search(self):
        """测试搜索API缓存装饰器"""
        call_count = 0

        @cached_api_search(ttl=300)
        async def search_api(q: str, category: str = None):
            nonlocal call_count
            call_count += 1
            return {"query": q, "results": []}

        # 第一次调用
        await search_api("test", "气功")
        assert call_count == 1

        # 第二次调用（从缓存）
        await search_api("test", "气功")
        assert call_count == 1

        # 不同参数
        await search_api("test2", "气功")
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cached_api_categories(self):
        """测试分类API缓存装饰器"""
        call_count = 0

        @cached_api_categories(ttl=1800)
        async def categories_api():
            nonlocal call_count
            call_count += 1
            return {"categories": []}

        await categories_api()
        await categories_api()
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_cached_api_domain_stats(self):
        """测试领域统计API缓存装饰器"""
        call_count = 0

        @cached_api_domain_stats(ttl=600)
        async def domain_stats_api(domain: str):
            nonlocal call_count
            call_count += 1
            return {"domain": domain, "stats": {}}

        await domain_stats_api("qigong")
        await domain_stats_api("qigong")
        assert call_count == 1

        await domain_stats_api("tcm")
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cached_api_stats(self):
        """测试系统统计API缓存装饰器"""
        call_count = 0

        @cached_api_stats(ttl=300)
        async def stats_api():
            nonlocal call_count
            call_count += 1
            return {"document_count": 100, "category_stats": []}

        await stats_api()
        await stats_api()
        assert call_count == 1


class TestCacheIntegration:
    """缓存集成测试"""

    @pytest.mark.asyncio
    async def test_multi_level_cache(self):
        """测试多级缓存"""
        config = CacheConfig(
            enabled=True,
            strategy="write_through",
            default_ttl=60,
        )

        manager = CacheManager(config=config)

        # 设置缓存
        await manager.set("key1", "value1")

        # 通过管理器获取验证缓存工作
        cached_value = await manager.get("key1")
        assert cached_value == "value1"

    @pytest.mark.asyncio
    async def test_warm_up(self):
        """测试缓存预热"""
        manager = CacheManager()

        data = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }

        stats = await manager.warm_up(data, batch_size=2)

        assert stats["total"] == 3
        assert stats["success"] == 3
        assert stats["failed"] == 0


# 性能测试
class TestCachePerformance:
    """缓存性能测试"""

    @pytest.mark.asyncio
    async def test_bulk_operations(self):
        """测试批量操作性能"""
        manager = CacheManager()

        # 批量设置
        import time

        start = time.time()

        data = {f"key{i}": f"value{i}" for i in range(100)}
        await manager.set_many(data, ttl=60)

        set_time = time.time() - start

        # 批量获取
        start = time.time()
        results = await manager.get_many(list(data.keys()))
        get_time = time.time() - start

        assert len(results) == 100
        assert set_time < 1.0  # 应该很快
        assert get_time < 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
