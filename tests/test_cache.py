"""缓存模块测试

覆盖: CacheManager, MemoryCache, RedisCache, decorators
"""

import asyncio

import pytest


@pytest.fixture
async def memory_cache():
    from backend.cache.memory_cache import MemoryCache

    mc = MemoryCache()
    yield mc
    await mc.clear()


class TestMemoryCache:
    """内存缓存测试"""

    @pytest.mark.asyncio
    async def test_memory_cache_set_get(self, memory_cache):
        await memory_cache.set("test_key", "test_value", ttl=60)
        result = await memory_cache.get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_memory_cache_miss(self, memory_cache):
        result = await memory_cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_memory_cache_delete(self, memory_cache):
        await memory_cache.set("del_key", "value", ttl=60)
        await memory_cache.delete("del_key")
        assert await memory_cache.get("del_key") is None

    @pytest.mark.asyncio
    async def test_memory_cache_ttl_expiry(self, memory_cache):
        await memory_cache.set("expire_key", "value", ttl=0.01)
        await asyncio.sleep(0.02)
        assert await memory_cache.get("expire_key") is None

    @pytest.mark.asyncio
    async def test_memory_cache_clear(self, memory_cache):
        await memory_cache.set("key1", "val1", ttl=60)
        await memory_cache.set("key2", "val2", ttl=60)
        await memory_cache.clear()
        assert await memory_cache.get("key1") is None
        assert await memory_cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_memory_cache_size(self, memory_cache):
        await memory_cache.set("k1", "v1", ttl=60)
        await memory_cache.set("k2", "v2", ttl=60)
        s = memory_cache.size
        assert s >= 2


class TestCacheManager:
    """缓存管理器测试"""

    def test_import_cache_manager(self):
        from backend.cache.manager import CacheManager

        assert CacheManager is not None

    def test_cache_manager_has_methods(self):
        from backend.cache.manager import CacheManager

        cm = CacheManager()
        assert hasattr(cm, "get") or hasattr(cm, "l1")


class TestRedisCache:
    """Redis缓存测试"""

    def test_import_redis_cache(self):
        from backend.cache.redis_cache import RedisCache

        assert RedisCache is not None


class TestCacheDecorators:
    """缓存装饰器测试"""

    def test_import_decorators(self):
        from backend.cache.decorators import cached, memoize_async

        assert callable(cached)
        assert callable(memoize_async)
