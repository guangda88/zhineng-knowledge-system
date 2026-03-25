"""缓存装饰器

提供便捷的缓存装饰器，支持多种缓存策略
"""

import asyncio
import functools
import hashlib
import inspect
import json
import logging
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    ParamSpec,
    TypeVar,
    Union,
)

from .manager import CacheManager

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


class CacheKeyGenerator(Enum):
    """缓存键生成策略"""

    SIMPLE = "simple"  # 简单拼接
    HASH = "hash"  # MD5哈希
    JSON = "json"  # JSON序列化后哈希


def _generate_cache_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    strategy: CacheKeyGenerator = CacheKeyGenerator.HASH,
    prefix: str = "",
) -> str:
    """生成缓存键

    Args:
        func: 被装饰的函数
        args: 位置参数
        kwargs: 关键字参数
        strategy: 键生成策略
        prefix: 键前缀

    Returns:
        缓存键
    """
    # 获取函数名
    func_name = func.__qualname__
    module_name = func.__module__

    # 构建基础键
    base_key = f"{module_name}.{func_name}"

    # 序列化参数
    try:
        # 过滤掉不可序列化的参数
        serializable_kwargs = {}
        for k, v in kwargs.items():
            try:
                json.dumps(v)
                serializable_kwargs[k] = v
            except (TypeError, ValueError):
                # 使用字符串表示
                serializable_kwargs[k] = str(v)

        # 处理位置参数
        serializable_args = []
        for arg in args:
            try:
                json.dumps(arg)
                serializable_args.append(arg)
            except (TypeError, ValueError):
                serializable_args.append(str(arg))

        params_str = json.dumps(
            {"args": serializable_args, "kwargs": serializable_kwargs},
            sort_keys=True,
            default=str,
        )
    except Exception as e:
        logger.warning(f"参数序列化失败: {e}")
        params_str = str(args) + str(kwargs)

    # 根据策略生成键
    if strategy == CacheKeyGenerator.HASH:
        params_hash = hashlib.md5(params_str.encode(), usedforsecurity=False).hexdigest()[:16]
        cache_key = f"{base_key}:{params_hash}"
    elif strategy == CacheKeyGenerator.JSON:
        params_hash = hashlib.md5(params_str.encode(), usedforsecurity=False).hexdigest()
        cache_key = f"{base_key}:{params_hash}"
    else:  # SIMPLE
        params_short = params_str[:50]
        cache_key = f"{base_key}:{params_short}"

    # 添加前缀
    if prefix:
        cache_key = f"{prefix}:{cache_key}"

    return cache_key


def cached(
    cache_manager: Optional[CacheManager] = None,
    namespace: str = "",
    ttl: Optional[int] = None,
    key_prefix: str = "",
    key_strategy: CacheKeyGenerator = CacheKeyGenerator.HASH,
    skip_cache_param: str = "skip_cache",
):
    """通用缓存装饰器

    Args:
        cache_manager: 缓存管理器，None则使用全局实例
        namespace: 命名空间
        ttl: 过期时间（秒）
        key_prefix: 缓存键前缀
        key_strategy: 键生成策略
        skip_cache_param: 跳过缓存的参数名

    Returns:
        装饰器函数

    Example:
        @cached(namespace="query_result", ttl=3600)
        async def search_documents(query: str):
            return await db.query(query)
    """

    def decorator(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, Coroutine[Any, Any, R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # 检查是否跳过缓存
            if kwargs.pop(skip_cache_param, False):
                return await func(*args, **kwargs)

            # 获取缓存管理器
            from .manager import get_cache_manager

            cm = cache_manager or get_cache_manager()

            if not cm.is_enabled():
                return await func(*args, **kwargs)

            # 生成缓存键
            cache_key = _generate_cache_key(func, args, kwargs, key_strategy, key_prefix)

            # 尝试获取缓存
            cached_value = await cm.get(cache_key, namespace=namespace)
            if cached_value is not None:
                logger.debug(f"缓存命中: {cache_key}")
                return cached_value

            # 执行函数
            result = await func(*args, **kwargs)

            # 设置缓存
            await cm.set(cache_key, result, namespace=namespace, ttl=ttl)

            return result

        return wrapper

    return decorator


def cached_query(ttl: int = 3600):
    """查询结果缓存装饰器 (TTL: 1小时)

    Args:
        ttl: 过期时间（秒）

    Example:
        @cached_query()
        async def get_user(user_id: str):
            return await db.fetch_user(user_id)
    """
    return cached(namespace="query_result", ttl=ttl)


def cached_vector_search(ttl: int = 1800):
    """向量搜索缓存装饰器 (TTL: 30分钟)

    Args:
        ttl: 过期时间（秒）

    Example:
        @cached_vector_search()
        async def search_similar(query_vector: List[float]):
            return await vector_store.search(query_vector)
    """
    return cached(namespace="vector_search", ttl=ttl, key_prefix="vector")


def cached_llm(ttl: int = 7200):
    """LLM响应缓存装饰器 (TTL: 2小时)

    Args:
        ttl: 过期时间（秒）

    Example:
        @cached_llm()
        async def generate_response(prompt: str):
            return await llm_client.generate(prompt)
    """
    return cached(namespace="llm_response", ttl=ttl, key_prefix="llm")


def cached_document(ttl: int = 86400):
    """文档内容缓存装饰器 (TTL: 1天)

    Args:
        ttl: 过期时间（秒）

    Example:
        @cached_document()
        async def get_document(doc_id: str):
            return await db.fetch_document(doc_id)
    """
    return cached(namespace="document", ttl=ttl, key_prefix="doc")


def cached_stats(ttl: int = 300):
    """统计信息缓存装饰器 (TTL: 5分钟)

    Args:
        ttl: 过期时间（秒）

    Example:
        @cached_stats()
        async def get_domain_stats(domain: str):
            return await calculate_stats(domain)
    """
    return cached(namespace="domain_stats", ttl=ttl, key_prefix="stats")


class CacheWarmer:
    """缓存预热器

    用于批量预加载缓存数据
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        """初始化缓存预热器

        Args:
            cache_manager: 缓存管理器
        """
        from .manager import get_cache_manager

        self._cache_manager = cache_manager or get_cache_manager()
        self._warmup_tasks: List[Callable] = []

    def add_task(
        self,
        func: Callable,
        *args: Any,
        namespace: str = "",
        ttl: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """添加预热任务

        Args:
            func: 要执行的函数
            *args: 位置参数
            namespace: 命名空间
            ttl: 过期时间
            **kwargs: 关键字参数
        """
        self._warmup_tasks.append((func, args, kwargs, namespace, ttl))

    async def warm_up(self, batch_size: int = 10) -> Dict[str, Any]:
        """执行缓存预热

        Args:
            batch_size: 并发批大小

        Returns:
            预热统计信息
        """
        results = {
            "total": len(self._warmup_tasks),
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }

        logger.info(f"开始缓存预热，共 {results['total']} 个任务")

        # 分批执行
        for i in range(0, len(self._warmup_tasks), batch_size):
            batch = self._warmup_tasks[i : i + batch_size]
            tasks = []

            for func, args, kwargs, namespace, ttl in batch:

                async def warm_task(f=func, a=args, kw=kwargs, ns=namespace, t=ttl):
                    try:
                        result = await f(*a, **kw)
                        # 生成缓存键
                        cache_key = _generate_cache_key(f, a, kw)
                        await self._cache_manager.set(cache_key, result, namespace=ns, ttl=t)
                        return "success"
                    except Exception as e:
                        logger.warning(f"预热任务失败: {e}")
                        return "failed"

                tasks.append(warm_task())

            # 等待批次完成
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if result == "success":
                    results["success"] += 1
                elif result == "failed":
                    results["failed"] += 1
                else:
                    results["skipped"] += 1

            logger.info(f"预热进度: {min(i + batch_size, results['total'])}/{results['total']}")

        # 清空任务列表
        self._warmup_tasks.clear()

        logger.info(
            f"缓存预热完成: 成功={results['success']}, 失败={results['failed']}, "
            f"跳过={results['skipped']}"
        )

        return results

    def clear_tasks(self) -> None:
        """清空预热任务"""
        self._warmup_tasks.clear()


def invalidate_cache(pattern: str = "*", namespace: str = ""):
    """缓存失效装饰器

    用于在数据更新时使相关缓存失效

    Args:
        pattern: 匹配模式
        namespace: 命名空间

    Example:
        @invalidate_cache(pattern="user_*", namespace="query_result")
        async def update_user(user_id: str, data: dict):
            return await db.update_user(user_id, data)
    """

    def decorator(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, Coroutine[Any, Any, R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # 执行函数
            result = await func(*args, **kwargs)

            # 使缓存失效
            from .manager import get_cache_manager

            cache_manager = get_cache_manager()
            await cache_manager.delete_pattern(pattern, namespace=namespace)

            logger.debug(f"缓存已失效: pattern={pattern}, namespace={namespace}")

            return result

        return wrapper

    return decorator


class CacheAside:
    """Cache-Aside 模式装饰器

    先查缓存，未命中则查数据库并回填缓存
    """

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        namespace: str = "",
        ttl: Optional[int] = None,
    ):
        """初始化

        Args:
            cache_manager: 缓存管理器
            namespace: 命名空间
            ttl: 过期时间
        """
        from .manager import get_cache_manager

        self._cache_manager = cache_manager or get_cache_manager()
        self._namespace = namespace
        self._ttl = ttl

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Coroutine[Any, Any, T]],
    ) -> T:
        """获取缓存或计算值

        Args:
            key: 缓存键
            compute_fn: 计算函数

        Returns:
            缓存值或计算结果
        """
        # 尝试获取缓存
        value = await self._cache_manager.get(key, namespace=self._namespace)
        if value is not None:
            return value

        # 计算值
        value = await compute_fn()

        # 回填缓存
        await self._cache_manager.set(key, value, namespace=self._namespace, ttl=self._ttl)

        return value


def memoize_async(ttl: Optional[int] = None, max_size: int = 128):
    """异步函数结果缓存（内存级）

    Args:
        ttl: 过期时间（秒）
        max_size: 最大缓存条目数

    Example:
        @memoize_async(ttl=60)
        async def expensive_computation(x: int):
            return x ** 2
    """

    def decorator(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, Coroutine[Any, Any, R]]:
        cache: Dict[str, tuple[Any, float]] = {}

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # 生成键
            key = _generate_cache_key(func, args, kwargs, CacheKeyGenerator.HASH)

            # 检查缓存
            if key in cache:
                value, expiry = cache[key]
                if ttl is None or expiry > asyncio.get_event_loop().time():
                    return value
                else:
                    del cache[key]

            # 执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            if max_size and len(cache) >= max_size:
                # 删除最旧的条目
                oldest_key = min(cache.keys(), key=lambda k: cache[k][1])
                del cache[oldest_key]

            expiry = asyncio.get_event_loop().time() + ttl if ttl else float("inf")
            cache[key] = (result, expiry)

            return result

        # 添加清除方法
        wrapper.cache_clear = lambda: cache.clear()  # type: ignore
        wrapper.cache_info = lambda: {"size": len(cache), "max_size": max_size}  # type: ignore

        return wrapper

    return decorator


def cached_api_search(ttl: int = 300):
    """API搜索结果缓存装饰器 (TTL: 5分钟)

    专为/api/v1/search端点设计，支持查询参数和分类筛选

    Args:
        ttl: 过期时间（秒）

    Example:
        @cached_api_search()
        async def search_documents(q: str, category: str = None):
            return await search_service.query(q, category)
    """
    return cached(
        namespace="api_search", ttl=ttl, key_prefix="search", key_strategy=CacheKeyGenerator.HASH
    )


def cached_api_categories(ttl: int = 1800):
    """API分类列表缓存装饰器 (TTL: 30分钟)

    专为/api/v1/categories端点设计

    Args:
        ttl: 过期时间（秒）

    Example:
        @cached_api_categories()
        async def get_categories():
            return await db.fetch_categories()
    """
    return cached(
        namespace="api_categories",
        ttl=ttl,
        key_prefix="categories",
        key_strategy=CacheKeyGenerator.SIMPLE,
    )


def cached_api_domain_stats(ttl: int = 600):
    """API领域统计缓存装饰器 (TTL: 10分钟)

    专为/api/v1/domains/{domain}/stats端点设计

    Args:
        ttl: 过期时间（秒）

    Example:
        @cached_api_domain_stats()
        async def get_domain_stats(domain: str):
            return await domain_service.get_stats(domain)
    """
    return cached(
        namespace="api_domain_stats",
        ttl=ttl,
        key_prefix="domain_stats",
        key_strategy=CacheKeyGenerator.HASH,
    )


def cached_api_stats(ttl: int = 300):
    """API系统统计缓存装饰器 (TTL: 5分钟)

    专为/api/v1/stats端点设计，缓存文档数量和分类统计信息

    Args:
        ttl: 过期时间（秒）

    Example:
        @cached_api_stats()
        async def get_stats():
            return await db.fetch_stats()
    """
    return cached(
        namespace="api_stats", ttl=ttl, key_prefix="stats", key_strategy=CacheKeyGenerator.SIMPLE
    )


class RateLimiterCache:
    """基于缓存的速率限制器"""

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        requests: int = 100,
        window: int = 60,
    ):
        """初始化速率限制器

        Args:
            cache_manager: 缓存管理器
            requests: 请求上限
            window: 时间窗口（秒）
        """
        from .manager import get_cache_manager

        self._cache_manager = cache_manager or get_cache_manager()
        self._requests = requests
        self._window = window

    async def is_allowed(
        self,
        identifier: str,
        namespace: str = "rate_limit",
    ) -> tuple[bool, int]:
        """检查是否允许请求

        Args:
            identifier: 标识符（如用户ID、IP地址）
            namespace: 命名空间

        Returns:
            (是否允许, 剩余请求数)
        """
        import time

        key = f"{namespace}:{identifier}"
        current_time = int(time.time())

        # 获取当前计数
        data = await self._cache_manager.get(key)

        if data is None:
            # 首次请求
            await self._cache_manager.set(
                key,
                {"count": 1, "window_start": current_time},
                namespace=namespace,
                ttl=self._window,
            )
            return True, self._requests - 1

        # 检查窗口
        if current_time - data["window_start"] >= self._window:
            # 新窗口
            await self._cache_manager.set(
                key,
                {"count": 1, "window_start": current_time},
                namespace=namespace,
                ttl=self._window,
            )
            return True, self._requests - 1

        # 同一窗口内
        if data["count"] >= self._requests:
            return False, 0

        # 增加计数
        data["count"] += 1
        remaining = self._requests - data["count"]
        await self._cache_manager.set(
            key,
            data,
            namespace=namespace,
            ttl=self._window - (current_time - data["window_start"]),
        )

        return True, remaining


def rate_limit(
    requests: int = 100,
    window: int = 60,
    identifier_fn: Optional[Callable] = None,
):
    """速率限制装饰器

    Args:
        requests: 请求上限
        window: 时间窗口（秒）
        identifier_fn: 标识符生成函数

    Example:
        @rate_limit(requests=10, window=60)
        async def api_endpoint(user_id: str):
            return await process_request(user_id)
    """

    def decorator(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, Coroutine[Any, Any, R]]:
        limiter = RateLimiterCache(requests=requests, window=window)

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # 生成标识符
            if identifier_fn:
                identifier = str(identifier_fn(*args, **kwargs))
            else:
                identifier = _generate_cache_key(func, args, kwargs, CacheKeyGenerator.HASH)

            # 检查速率限制
            allowed, remaining = await limiter.is_allowed(identifier)

            if not allowed:
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Try again later.",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
