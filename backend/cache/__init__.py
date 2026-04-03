"""缓存模块

提供多级缓存支持，提升系统性能

功能特性：
- L1 内存缓存（LRU策略）
- L2 Redis缓存（分布式）
- 缓存装饰器
- 缓存预热
- 统计监控
"""

from .decorators import (
    CacheAside,
    CacheKeyGenerator,
    CacheWarmer,
    RateLimiterCache,
    cached,
    cached_api_categories,
    cached_api_domain_stats,
    cached_api_search,
    cached_api_stats,
    cached_document,
    cached_llm,
    cached_query,
    cached_stats,
    cached_vector_search,
    invalidate_cache,
    memoize_async,
    rate_limit,
)
from .manager import (
    CacheConfig,
    CacheLevel,
    CacheManager,
    CacheStats,
    CacheStrategy,
    get_cache_manager,
    setup_cache,
)
from .memory_cache import MemoryCache
from .redis_cache import RedisCache, RedisConfig, RedisStatus

__all__ = [
    # Manager
    "CacheManager",
    "get_cache_manager",
    "setup_cache",
    "CacheConfig",
    "CacheStats",
    "CacheLevel",
    "CacheStrategy",
    # Backends
    "RedisCache",
    "RedisConfig",
    "RedisStatus",
    "MemoryCache",
    # Decorators
    "cached",
    "cached_query",
    "cached_vector_search",
    "cached_llm",
    "cached_document",
    "cached_stats",
    "cached_api_search",
    "cached_api_categories",
    "cached_api_domain_stats",
    "cached_api_stats",
    "invalidate_cache",
    "CacheWarmer",
    "CacheAside",
    "memoize_async",
    "rate_limit",
    "RateLimiterCache",
    "CacheKeyGenerator",
]
