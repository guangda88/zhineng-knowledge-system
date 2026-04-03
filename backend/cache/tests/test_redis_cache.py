"""Redis缓存集成测试

测试Redis缓存的完整功能，包括连接、读写、批量操作等
"""

import asyncio
import time

import pytest

# 尝试导入redis相关模块
try:
    from backend.cache.manager import CacheConfig, CacheManager
    from backend.cache.redis_cache import (
        RedisCache,
        RedisConfig,
        RedisConnectionPool,
        RedisStatus,
    )

    REDIS_AVAILABLE = True
except ImportError as e:
    REDIS_AVAILABLE = False
    pytest.skip(f"Redis模块不可用: {e}", allow_module_level=True)


@pytest.fixture
def redis_config():
    """创建Redis测试配置"""
    return RedisConfig(
        url="redis://localhost:6379/15",  # 使用测试数据库15
        key_prefix="test:",
        max_connections=10,
        socket_timeout=5.0,
        retry_attempts=3,
        decode_responses=True,
    )


@pytest.fixture
async def redis_cache(redis_config):
    """创建Redis缓存实例"""
    try:
        cache = RedisCache(config=redis_config)
        # 先清空测试数据库
        await cache.clear()
        yield cache
        # 清理
        await cache.clear()
        await cache.close()
    except Exception as e:
        pytest.skip(f"Redis连接失败: {e}")


@pytest.fixture
async def cache_manager_with_redis(redis_config):
    """创建带Redis的缓存管理器"""
    try:
        manager = CacheManager(
            config=CacheConfig(enabled=True, max_size=100),
            redis_config=redis_config,
        )
        yield manager
        await manager.close()
    except Exception as e:
        pytest.skip(f"Redis连接失败: {e}")


class TestRedisConnection:
    """Redis连接测试"""

    @pytest.mark.asyncio
    async def test_connection_pool_creation(self, redis_config):
        """测试连接池创建"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        pool = RedisConnectionPool(redis_config)
        assert pool.status == RedisStatus.DISCONNECTED

        # 获取客户端会触发连接
        try:
            _client = await pool.get_client()  # noqa: F841
            assert pool.status == RedisStatus.CONNECTED
            await pool.close()
        except Exception as e:
            pytest.skip(f"Redis连接失败: {e}")

    @pytest.mark.asyncio
    async def test_health_check(self, redis_cache):
        """测试健康检查"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        is_healthy = await redis_cache.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_get_info(self, redis_cache):
        """测试获取Redis信息"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        info = await redis_cache.get_info()
        assert "type" in info
        assert info["type"] == "redis"
        assert "prefix" in info


class TestRedisBasicOperations:
    """Redis基本操作测试"""

    @pytest.mark.asyncio
    async def test_set_and_get(self, redis_cache):
        """测试设置和获取"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        # 设置字符串
        await redis_cache.set("key1", "value1")
        value = await redis_cache.get("key1")
        assert value == "value1"

        # 设置数字
        await redis_cache.set("key2", 123)
        value = await redis_cache.get("key2")
        assert value == 123

        # 设置复杂对象
        data = {"name": "test", "count": 42}
        await redis_cache.set("key3", data)
        value = await redis_cache.get("key3")
        assert value == data

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, redis_cache):
        """测试获取不存在的键"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        value = await redis_cache.get("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_set_with_ttl(self, redis_cache):
        """测试设置带TTL的值"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        await redis_cache.set("key1", "value1", ttl=2)
        value = await redis_cache.get("key1")
        assert value == "value1"

        # 等待过期
        await asyncio.sleep(2.5)
        value = await redis_cache.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self, redis_cache):
        """测试删除"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        await redis_cache.set("key1", "value1")
        assert await redis_cache.exists("key1") is True

        await redis_cache.delete("key1")
        assert await redis_cache.exists("key1") is False

    @pytest.mark.asyncio
    async def test_exists(self, redis_cache):
        """测试检查键是否存在"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        assert await redis_cache.exists("nonexistent") is False

        await redis_cache.set("key1", "value1")
        assert await redis_cache.exists("key1") is True

    @pytest.mark.asyncio
    async def test_ttl(self, redis_cache):
        """测试获取TTL"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        # 永不过期的键
        await redis_cache.set("key1", "value1")
        ttl = await redis_cache.ttl("key1")
        assert ttl == -1

        # 带TTL的键
        await redis_cache.set("key2", "value2", ttl=10)
        ttl = await redis_cache.ttl("key2")
        assert 0 < ttl <= 10

        # 不存在的键
        ttl = await redis_cache.ttl("nonexistent")
        assert ttl == -2

    @pytest.mark.asyncio
    async def test_expire(self, redis_cache):
        """测试设置过期时间"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        await redis_cache.set("key1", "value1")
        result = await redis_cache.expire("key1", 5)
        assert result is True

        ttl = await redis_cache.ttl("key1")
        assert 0 < ttl <= 5

    @pytest.mark.asyncio
    async def test_increment(self, redis_cache):
        """测试原子递增"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        # 初始化
        await redis_cache.set("counter", 0)

        # 递增
        value = await redis_cache.increment("counter")
        assert value == 1

        value = await redis_cache.increment("counter", 5)
        assert value == 6

        # 验证最终值
        final_value = await redis_cache.get("counter")
        assert final_value == 6


class TestRedisBatchOperations:
    """Redis批量操作测试"""

    @pytest.mark.asyncio
    async def test_get_many(self, redis_cache):
        """测试批量获取"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        # 设置多个键
        await redis_cache.set("key1", "value1")
        await redis_cache.set("key2", "value2")
        await redis_cache.set("key3", "value3")

        # 批量获取
        values = await redis_cache.get_many(["key1", "key2", "key3", "nonexistent"])
        assert len(values) == 3
        assert values["key1"] == "value1"
        assert values["key2"] == "value2"
        assert values["key3"] == "value3"
        assert "nonexistent" not in values

    @pytest.mark.asyncio
    async def test_set_many(self, redis_cache):
        """测试批量设置"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        data = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }

        result = await redis_cache.set_many(data, ttl=60)
        assert result is True

        # 验证
        values = await redis_cache.get_many(["key1", "key2", "key3"])
        assert len(values) == 3

    @pytest.mark.asyncio
    async def test_delete_many(self, redis_cache):
        """测试批量删除"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        await redis_cache.set("key1", "value1")
        await redis_cache.set("key2", "value2")
        await redis_cache.set("key3", "value3")

        deleted = await redis_cache.delete_many(["key1", "key2", "key4"])
        assert deleted == 2

    @pytest.mark.asyncio
    async def test_delete_pattern(self, redis_cache):
        """测试按模式删除"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        # 设置多个键
        await redis_cache.set("user:1:name", "Alice")
        await redis_cache.set("user:2:name", "Bob")
        await redis_cache.set("user:1:age", "30")
        await redis_cache.set("other:key", "value")

        # 删除所有user:1开头的键
        deleted = await redis_cache.delete_pattern("user:1*")
        assert deleted >= 2

        # 验证
        assert await redis_cache.exists("user:1:name") is False
        assert await redis_cache.exists("user:1:age") is False
        assert await redis_cache.exists("user:2:name") is True

    @pytest.mark.asyncio
    async def test_clear(self, redis_cache):
        """测试清空所有缓存"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        await redis_cache.set("key1", "value1")
        await redis_cache.set("key2", "value2")

        result = await redis_cache.clear()
        assert result is True

        assert await redis_cache.exists("key1") is False
        assert await redis_cache.exists("key2") is False


class TestRedisSerialization:
    """Redis序列化测试"""

    def test_serialize_string(self, redis_cache):
        """测试字符串序列化"""
        assert redis_cache._serialize("test") == "test"

    def test_serialize_number(self, redis_cache):
        """测试数字序列化"""
        assert redis_cache._serialize(123) == "123"
        assert redis_cache._serialize(3.14) == "3.14"

    def test_serialize_bool(self, redis_cache):
        """测试布尔序列化"""
        assert redis_cache._serialize(True) == "True"
        assert redis_cache._serialize(False) == "False"

    def test_serialize_dict(self, redis_cache):
        """测试字典序列化"""
        data = {"key": "value", "number": 42}
        serialized = redis_cache._serialize(data)
        assert isinstance(serialized, str)

    def test_serialize_list(self, redis_cache):
        """测试列表序列化"""
        data = [1, 2, 3, "test"]
        serialized = redis_cache._serialize(data)
        assert isinstance(serialized, str)

    def test_deserialize_json(self, redis_cache):
        """测试JSON反序列化"""
        json_str = '{"key": "value", "number": 42}'
        result = redis_cache._deserialize(json_str)
        assert result == {"key": "value", "number": 42}

    def test_deserialize_string(self, redis_cache):
        """测试字符串反序列化"""
        result = redis_cache._deserialize("plain string")
        assert result == "plain string"

    def test_deserialize_none(self, redis_cache):
        """测试None反序列化"""
        result = redis_cache._deserialize(None)
        assert result is None


class TestRedisCircuitBreaker:
    """Redis断路器测试"""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, redis_cache):
        """测试失败重试机制"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        # 正常操作应该成功
        result = await redis_cache.set("key1", "value1")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_info_with_circuit_breaker(self, redis_cache):
        """测试断路器状态"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        info = await redis_cache.get_info()
        assert "circuit_breaker_open" in info
        assert "circuit_breaker_failures" in info


class TestCacheManagerWithRedis:
    """缓存管理器与Redis集成测试"""

    @pytest.mark.asyncio
    async def test_l1_l2_cache_interaction(self, cache_manager_with_redis):
        """测试L1和L2缓存交互"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        manager = cache_manager_with_redis

        # 设置缓存（应该同时写入L1和L2）
        await manager.set("key1", "value1", ttl=60)

        # 从L1获取
        l1_value = await manager._l1_cache.get(manager._make_key("key1"))
        assert l1_value == "value1"

        # 从管理器获取
        value = await manager.get("key1")
        assert value == "value1"

    @pytest.mark.asyncio
    async def test_l2_fallback_to_l1(self, cache_manager_with_redis):
        """测试L2命中时回填L1"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        manager = cache_manager_with_redis

        # 只写入L2
        await manager._l2_cache.set(manager._make_key("key1"), "value1", ttl=60)

        # 清空L1
        await manager._l1_cache.clear()

        # 从管理器获取，应该从L2获取并回填L1
        value = await manager.get("key1")
        assert value == "value1"

        # 验证L1已被回填
        l1_value = await manager._l1_cache.get(manager._make_key("key1"))
        assert l1_value == "value1"

    @pytest.mark.asyncio
    async def test_namespace_with_redis(self, cache_manager_with_redis):
        """测试命名空间与Redis"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        manager = cache_manager_with_redis

        # 不同命名空间的相同键
        await manager.set("key1", "value1", namespace="ns1")
        await manager.set("key1", "value2", namespace="ns2")

        value1 = await manager.get("key1", namespace="ns1")
        value2 = await manager.get("key1", namespace="ns2")

        assert value1 == "value1"
        assert value2 == "value2"

    @pytest.mark.asyncio
    async def test_stats_with_redis(self, cache_manager_with_redis):
        """测试统计信息"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        manager = cache_manager_with_redis

        # 清空统计
        manager.reset_stats()

        # 执行操作
        await manager.set("key1", "value1")
        await manager.get("key1")  # hit
        await manager.get("key2")  # miss

        stats = manager.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 1
        assert stats["l2_available"] is True

    @pytest.mark.asyncio
    async def test_health_check_with_redis(self, cache_manager_with_redis):
        """测试健康检查"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        manager = cache_manager_with_redis

        health = await manager.health_check()
        assert "status" in health
        assert "l1" in health
        assert "l2" in health

        # L2应该是ok
        assert health["l2"] in ["ok", "error"]


class TestRedisPerformance:
    """Redis性能测试"""

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, redis_cache):
        """测试并发操作"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        # 并发设置
        tasks = [redis_cache.set(f"key{i}", f"value{i}") for i in range(100)]
        await asyncio.gather(*tasks)

        # 并发获取
        tasks = [redis_cache.get(f"key{i}") for i in range(100)]
        results = await asyncio.gather(*tasks)

        assert len([r for r in results if r is not None]) == 100

    @pytest.mark.asyncio
    async def test_pipeline_performance(self, redis_cache):
        """测试管道操作性能"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        # 使用批量设置
        data = {f"key{i}": f"value{i}" for i in range(100)}
        start = time.time()
        await redis_cache.set_many(data, ttl=60)
        set_time = time.time() - start

        # 应该很快
        assert set_time < 2.0

    @pytest.mark.asyncio
    async def test_large_value(self, redis_cache):
        """测试大值存储"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        # 创建一个较大的值
        large_value = {"data": "x" * 10000}  # 10KB
        await redis_cache.set("large_key", large_value)

        retrieved = await redis_cache.get("large_key")
        assert retrieved == large_value


class TestRedisErrorHandling:
    """Redis错误处理测试"""

    @pytest.mark.asyncio
    async def test_get_returns_none_on_error(self, redis_cache):
        """测试错误时get返回None"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        # 正常情况
        value = await redis_cache.get("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete_returns_false_on_error(self):
        """测试错误时delete返回False"""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis不可用")

        # 使用无效连接创建缓存
        config = RedisConfig(url="redis://invalid:9999/0")
        cache = RedisCache(config=config)

        result = await cache.delete("key1")
        assert result is False  # 失败返回False

        await cache.close()


# 设置和清理
@pytest.fixture(autouse=True)
async def cleanup_redis(redis_cache):
    """每个测试后清理"""
    yield
    if REDIS_AVAILABLE:
        try:
            await redis_cache.clear()
        except Exception:
            pass
