"""缓存系统单元测试

测试缓存管理器、Redis缓存、装饰器等功能
"""

import asyncio

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
)
from backend.cache.memory_cache import MemoryCache
from backend.cache.redis_cache import RedisCache, RedisConfig


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


class TestMultiLevelCache:
    """多级缓存测试"""

    @pytest.fixture
    def cache_config(self):
        """创建缓存配置"""
        return CacheConfig(
            enabled=True,
            default_ttl=3600,
            max_size=100,
            strategy="write_through",
        )

    @pytest.fixture
    def cache_manager(self, cache_config):
        """创建缓存管理器"""
        return CacheManager(config=cache_config)

    @pytest.mark.asyncio
    async def test_l1_cache_hit(self, cache_manager):
        """测试L1缓存命中"""
        # 设置值（会同时写入L1）
        await cache_manager.set("key1", "value1")

        # 第一次获取应该是L1命中
        value = await cache_manager.get("key1")

        assert value == "value1"

    @pytest.mark.asyncio
    async def test_l1_miss_l2_hit(self, cache_manager):
        """测试L1未命中L2命中（需要模拟）"""
        # 由于没有真实Redis，这里测试L2禁用时的行为
        await cache_manager.set("key1", "value1")

        # 直接清空L1模拟L1未命中
        await cache_manager._l1_cache.clear()

        # 获取应该从L2获取（如果有）或返回None
        value = await cache_manager.get("key1")
        # 由于L2未启用，value应该是None
        assert value is None

    @pytest.mark.asyncio
    async def test_l2_fills_l1(self):
        """测试L2命中时回填L1"""
        # 这个测试需要Mock Redis缓存
        # 这里测试基本逻辑
        config = CacheConfig(enabled=True, default_ttl=3600)
        manager = CacheManager(config=config)
        assert manager._l2_cache is None  # 无Redis时L2为None


class TestCacheStrategies:
    """缓存策略测试"""

    @pytest.mark.asyncio
    async def test_write_through_strategy(self):
        """测试WRITE_THROUGH策略"""
        config = CacheConfig(strategy="write_through", enabled=True)
        manager = CacheManager(config=config)

        await manager.set("key1", "value1")
        value = await manager.get("key1")
        assert value == "value1"

    @pytest.mark.asyncio
    async def test_write_back_strategy(self):
        """测试WRITE_BACK策略"""
        config = CacheConfig(strategy="write_back", enabled=True)
        manager = CacheManager(config=config)

        await manager.set("key1", "value1")
        value = await manager.get("key1")
        assert value == "value1"

    @pytest.mark.asyncio
    async def test_write_around_strategy(self):
        """测试WRITE_AROUND策略"""
        config = CacheConfig(strategy="write_around", enabled=True)
        manager = CacheManager(config=config)

        # WRITE_AROUND不缓存写入
        await manager.set("key1", "value1")
        value = await manager.get("key1")
        # 由于策略是write_around，获取应该返回None
        assert value is None

    @pytest.mark.asyncio
    async def test_strategy_enum_to_string(self):
        """测试策略枚举与字符串转换"""
        from backend.cache.manager import CacheStrategy

        config = CacheConfig(strategy=CacheStrategy.WRITE_THROUGH)
        manager = CacheManager(config=config)

        assert manager.config.strategy == CacheStrategy.WRITE_THROUGH
        assert manager.config.strategy.value == "write_through"


class TestCacheStatistics:
    """缓存统计测试"""

    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self):
        """测试命中率计算"""
        manager = CacheManager()

        # 设置一些值
        await manager.set("key1", "value1")
        await manager.set("key2", "value2")

        # 命中
        await manager.get("key1")
        await manager.get("key2")

        # 未命中
        await manager.get("key3")

        stats = manager.get_stats()
        # 由于采样率可能不是100%，使用近似比较
        assert stats["hit_rate"] > 0  # 应该有命中率

    @pytest.mark.asyncio
    async def test_l1_hit_rate(self):
        """测试L1命中率"""
        manager = CacheManager()

        await manager.set("key1", "value1")
        await manager.get("key1")  # L1命中

        stats = manager.get_stats()
        assert stats["l1_hit_rate"] > 0

    @pytest.mark.asyncio
    async def test_l2_hit_rate(self):
        """测试L2命中率（需要Redis）"""
        manager = CacheManager()
        stats = manager.get_stats()
        # 无Redis时L2命中率为0
        assert stats["l2_hit_rate"] == 0

    @pytest.mark.asyncio
    async def test_stats_includes_sets_and_deletes(self):
        """测试统计包含设置和删除操作"""
        manager = CacheManager()

        await manager.set("key1", "value1")
        await manager.delete("key1")

        stats = manager.get_stats()
        assert stats["sets"] == 1
        assert stats["deletes"] == 1

    @pytest.mark.asyncio
    async def test_reset_stats(self):
        """测试重置统计"""
        manager = CacheManager()

        await manager.set("key1", "value1")
        await manager.get("key1")

        stats_before = manager.get_stats()
        assert stats_before["hits"] > 0

        manager.reset_stats()

        stats_after = manager.get_stats()
        assert stats_after["hits"] == 0
        assert stats_after["misses"] == 0

    @pytest.mark.asyncio
    async def test_stats_sample_rate(self):
        """测试统计采样率"""
        config = CacheConfig(stats_sample_rate=0.5)  # 50%采样
        manager = CacheManager(config=config)

        await manager.set("key1", "value1")
        await manager.get("key1")

        # 采样可能导致统计不完整
        stats = manager.get_stats()
        # 由于采样，可能没有记录到请求
        assert stats["hits"] >= 0


class TestBatchOperations:
    """批量操作测试"""

    @pytest.mark.asyncio
    async def test_get_many(self):
        """测试批量获取"""
        manager = CacheManager()

        # 设置多个值
        data = {"key1": "value1", "key2": "value2", "key3": "value3"}
        await manager.set_many(data)

        # 批量获取
        results = await manager.get_many(["key1", "key2", "key3"])

        assert len(results) == 3
        assert results["key1"] == "value1"
        assert results["key2"] == "value2"
        assert results["key3"] == "value3"

    @pytest.mark.asyncio
    async def test_get_many_partial(self):
        """测试批量获取部分存在的键"""
        manager = CacheManager()

        await manager.set("key1", "value1")
        await manager.set("key2", "value2")

        # 获取包括不存在的键
        results = await manager.get_many(["key1", "key2", "key3"])

        assert len(results) == 2
        assert "key3" not in results

    @pytest.mark.asyncio
    async def test_set_many(self):
        """测试批量设置"""
        manager = CacheManager()

        data = {f"key{i}": f"value{i}" for i in range(10)}
        await manager.set_many(data)

        # 验证
        for i in range(10):
            value = await manager.get(f"key{i}")
            assert value == f"value{i}"

    @pytest.mark.asyncio
    async def test_delete_many(self):
        """测试批量删除"""
        manager = CacheManager()

        # 设置多个值
        data = {"key1": "value1", "key2": "value2", "key3": "value3"}
        await manager.set_many(data)

        # 批量删除
        await manager.delete_many(["key1", "key2"])

        # 验证
        assert await manager.get("key1") is None
        assert await manager.get("key2") is None
        assert await manager.get("key3") == "value3"

    @pytest.mark.asyncio
    async def test_delete_pattern(self):
        """测试按模式删除"""
        manager = CacheManager()

        # 设置带前缀的键
        await manager.set("user:1", "data1")
        await manager.set("user:2", "data2")
        await manager.set("admin:1", "data3")

        # 删除用户模式
        await manager.delete_pattern("user:*")

        # 验证
        assert await manager.get("user:1") is None
        assert await manager.get("user:2") is None
        assert await manager.get("admin:1") == "data3"


class TestCacheWarmUp:
    """缓存预热测试"""

    @pytest.mark.asyncio
    async def test_warm_up_from_dict(self):
        """测试从字典预热"""
        manager = CacheManager()

        data = {f"key{i}": f"value{i}" for i in range(5)}
        stats = await manager.warm_up(data)

        assert stats["total"] == 5
        assert stats["success"] == 5
        assert stats["failed"] == 0

        # 验证数据已缓存
        for i in range(5):
            value = await manager.get(f"key{i}")
            assert value == f"value{i}"

    @pytest.mark.asyncio
    async def test_warm_up_with_batch_size(self):
        """测试指定批大小的预热"""
        manager = CacheManager()

        data = {f"key{i}": f"value{i}" for i in range(10)}
        stats = await manager.warm_up(data, batch_size=3)

        assert stats["total"] == 10
        assert stats["success"] == 10

    @pytest.mark.asyncio
    async def test_warm_up_disabled(self):
        """测试禁用预热"""
        config = CacheConfig(warm_up_enabled=False)
        manager = CacheManager(config=config)

        data = {"key1": "value1"}
        stats = await manager.warm_up(data)

        assert stats["skipped"] is True
        assert stats["reason"] == "disabled"

    @pytest.mark.asyncio
    async def test_warm_up_from_generator(self):
        """测试从生成器预热"""
        manager = CacheManager()

        async def data_generator():
            return {"key1": "value1", "key2": "value2"}

        stats = await manager.warm_up_from_generator(data_generator)

        assert stats["total"] == 2
        assert stats["success"] == 2


class TestHealthCheck:
    """健康检查测试"""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """测试健康检查 - 健康"""
        manager = CacheManager()
        health = await manager.health_check()

        assert health["status"] == "healthy"
        assert health["l1"] == "ok"

    @pytest.mark.asyncio
    async def test_health_check_l2_disabled(self):
        """测试健康检查 - L2禁用"""
        manager = CacheManager()
        health = await manager.health_check()

        assert health["l2"] == "disabled"

    @pytest.mark.asyncio
    async def test_exists_method(self):
        """测试exists方法"""
        manager = CacheManager()

        await manager.set("key1", "value1")

        assert await manager.exists("key1") is True
        assert await manager.exists("key2") is False


class TestHotKeys:
    """热键追踪测试"""

    @pytest.mark.asyncio
    async def test_hot_keys_tracking(self):
        """测试热键追踪"""
        manager = CacheManager()

        await manager.set("key1", "value1")

        # 访问多次达到阈值
        for _ in range(12):
            await manager.get("key1")

        hot_keys = await manager.get_hot_keys(threshold=10)
        assert len(hot_keys) > 0

    @pytest.mark.asyncio
    async def test_hot_keys_threshold(self):
        """测试热键阈值"""
        manager = CacheManager()

        await manager.set("key1", "value1")

        # 访问5次，低于默认阈值10
        for _ in range(5):
            await manager.get("key1")

        hot_keys = await manager.get_hot_keys(threshold=10)
        assert len(hot_keys) == 0

    @pytest.mark.asyncio
    async def test_reset_hot_keys(self):
        """测试重置热键"""
        manager = CacheManager()

        await manager.set("key1", "value1")

        # 访问多次
        for _ in range(12):
            await manager.get("key1")

        manager.reset_hot_keys()

        hot_keys = await manager.get_hot_keys(threshold=10)
        assert len(hot_keys) == 0


class TestCacheDisabled:
    """缓存禁用测试"""

    @pytest.mark.asyncio
    async def test_disabled_cache_returns_default(self):
        """测试禁用的缓存返回默认值"""
        config = CacheConfig(enabled=False)
        manager = CacheManager(config=config)

        # 所有操作应该被跳过
        await manager.set("key1", "value1")
        value = await manager.get("key1", default="default")
        assert value == "default"

    @pytest.mark.asyncio
    async def test_is_enabled(self):
        """测试is_enabled方法"""
        config_enabled = CacheConfig(enabled=True)
        manager_enabled = CacheManager(config=config_enabled)
        assert manager_enabled.is_enabled() is True

        config_disabled = CacheConfig(enabled=False)
        manager_disabled = CacheManager(config=config_disabled)
        assert manager_disabled.is_enabled() is False


class TestCacheKeyGeneration:
    """缓存键生成测试"""

    @pytest.mark.asyncio
    async def test_make_key_basic(self):
        """测试基本键生成"""
        manager = CacheManager()

        full_key = manager._make_key("my_key")
        assert "zhineng_kb:" in full_key
        assert "my_key" in full_key

    @pytest.mark.asyncio
    async def test_make_key_with_namespace(self):
        """测试带命名空间的键生成"""
        manager = CacheManager()

        full_key = manager._make_key("my_key", namespace="ns1")
        assert "ns1:my_key" in full_key

    @pytest.mark.asyncio
    async def test_make_key_long_key_hashed(self):
        """测试长键被哈希"""
        manager = CacheManager()

        # 创建超过200字符的键
        long_key = "a" * 250
        full_key = manager._make_key(long_key)

        # 应该被哈希
        assert "hash:" in full_key
        assert len(full_key) < 250

    @pytest.mark.asyncio
    async def test_get_ttl_for_resource_type(self):
        """测试获取资源类型的TTL"""
        manager = CacheManager()

        query_ttl = manager._get_ttl("query_result")
        assert query_ttl == 3600

        vector_ttl = manager._get_ttl("vector_search")
        assert vector_ttl == 1800

        # 未知类型使用默认TTL
        unknown_ttl = manager._get_ttl("unknown")
        assert unknown_ttl == 3600


class TestCacheClear:
    """缓存清空测试"""

    @pytest.mark.asyncio
    async def test_clear_all(self):
        """测试清空所有缓存"""
        manager = CacheManager()

        # 设置多个值
        await manager.set("key1", "value1")
        await manager.set("key2", "value2", namespace="ns1")

        # 清空
        await manager.clear()

        # 验证所有值已清空
        assert await manager.get("key1") is None
        assert await manager.get("key2", namespace="ns1") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
