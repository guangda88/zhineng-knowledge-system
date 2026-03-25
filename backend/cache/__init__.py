"""缓存模块

提供多级缓存支持，提升系统性能

功能特性：
- L1 内存缓存（LRU策略）
- L2 Redis缓存（分布式）
- 缓存装饰器
- 缓存预热
- 统计监控
"""

from .manager import (
    CacheManager,
    get_cache_manager,
    setup_cache,
    CacheConfig,
    CacheStats,
    CacheLevel,
    CacheStrategy,
    cached,
)

from .redis_cache import RedisCache, RedisConfig, RedisStatus

from .memory_cache import MemoryCache

from .decorators import (
    cached,
    cached_query,
    cached_vector_search,
    cached_llm,
    cached_document,
    cached_stats,
    invalidate_cache,
    CacheWarmer,
    CacheAside,
    memoize_async,
    rate_limit,
    RateLimiterCache,
    CacheKeyGenerator,
)

__all__ = [
    # Manager
    'CacheManager',
    'get_cache_manager',
    'setup_cache',
    'CacheConfig',
    'CacheStats',
    'CacheLevel',
    'CacheStrategy',

    # Backends
    'RedisCache',
    'RedisConfig',
    'RedisStatus',
    'MemoryCache',

    # Decorators
    'cached_query',
    'cached_vector_search',
    'cached_llm',
    'cached_document',
    'cached_stats',
    'invalidate_cache',
    'CacheWarmer',
    'CacheAside',
    'memoize_async',
    'rate_limit',
    'RateLimiterCache',
    'CacheKeyGenerator',
]
