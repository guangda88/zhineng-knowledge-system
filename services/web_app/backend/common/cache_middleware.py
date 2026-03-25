import hashlib
# -*- coding: utf-8 -*-
"""
缓存中间件
Cache Middleware for FastAPI

提供 FastAPI 集成的缓存中间件和依赖注入
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers

from .cache_manager import (
    CacheManager,
    CacheKeyPattern,
    CacheTTL,
    get_cache_manager,
)

logger = logging.getLogger(__name__)


class CacheMiddleware(BaseHTTPMiddleware):
    """
    缓存中间件

    对 GET 请求进行响应缓存
    支持基于请求头和查询参数的缓存键生成
    """

    def __init__(
        self,
        app,
        cache_manager: Optional[CacheManager] = None,
        default_ttl: int = 300,  # 5分钟
        cacheable_paths: Optional[List[str]] = None,
        cacheable_prefixes: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
        exclude_prefixes: Optional[List[str]] = None,
        cache_header: str = "X-Cache",
    ):
        """
        初始化缓存中间件

        Args:
            app: FastAPI 应用
            cache_manager: 缓存管理器
            default_ttl: 默认缓存时间（秒）
            cacheable_paths: 可缓存的路径列表（精确匹配）
            cacheable_prefixes: 可缓存的路径前缀列表
            exclude_paths: 排除的路径列表（精确匹配）
            exclude_prefixes: 排除的路径前缀列表
            cache_header: 缓存状态响应头名称
        """
        super().__init__(app)
        self._cache = cache_manager or get_cache_manager()
        self._default_ttl = default_ttl
        self._cacheable_paths = set(cacheable_paths or [])
        self._cacheable_prefixes = set(cacheable_prefixes or [])
        self._exclude_paths = set(exclude_paths or [])
        self._exclude_prefixes = set(exclude_prefixes or [])
        self._cache_header = cache_header

        # 默认可缓存的前缀
        if not self._cacheable_prefixes:
            self._cacheable_prefixes = {
                "/api/v1/hotwords",
                "/api/v1/documents",
            }

        # 默认排除的前缀
        if not self._exclude_prefixes:
            self._exclude_prefixes = {
                "/api/v1/auth",
                "/api/v1/admin",
                "/health",
                "/docs",
                "/openapi.json",
            }

    def _is_cacheable(self, path: str, method: str) -> bool:
        """
        判断请求是否可缓存

        Args:
            path: 请求路径
            method: 请求方法

        Returns:
            是否可缓存
        """
        # 只缓存 GET 请求
        if method != "GET":
            return False

        # 检查精确排除
        if path in self._exclude_paths:
            return False

        # 检查前缀排除
        if any(path.startswith(prefix) for prefix in self._exclude_prefixes):
            return False

        # 如果没有指定可缓存路径，则默认可缓存（排除的除外）
        if not self._cacheable_paths and not self._cacheable_prefixes:
            return True

        # 检查精确匹配
        if path in self._cacheable_paths:
            return True

        # 检查前缀匹配
        if any(path.startswith(prefix) for prefix in self._cacheable_prefixes):
            return True

        return False

    def _make_cache_key(self, request: Request) -> str:
        """
        生成缓存键

        Args:
            request: 请求对象

        Returns:
            缓存键
        """
        path = request.url.path
        query_string = str(request.url.query) if request.url.query else ""

        # 获取影响缓存的关键请求头
        vary_headers = []
        if "Accept-Language" in request.headers:
            vary_headers.append(f"lang={request.headers['Accept-Language'][:2]}")
        if "Authorization" in request.headers:
            # 对于需要认证的请求，包含用户标识
            # 注意：这里不应该存储完整的 token，只存储用户标识
            token = request.headers["Authorization"]
            if token.startswith("Bearer "):
                # 简单的哈希用于区分不同用户
                import hashlib

                token_hash = hashlib.sha256(token[7:].encode()).hexdigest()[:8]
                vary_headers.append(f"user={token_hash}")

        headers_str = ":".join(vary_headers) if vary_headers else ""

        # 组合生成键
        key_parts = [path, query_string, headers_str]
        key_string = "|".join(key_parts)

        # 生成最终键
        import hashlib

        cache_hash = hashlib.sha256(key_string.encode()).hexdigest()

        return CacheKeyPattern.build("http", "response", cache_hash)

    async def dispatch(self, request: Request, call_next):
        """
        处理请求

        Args:
            request: 请求对象
            call_next: 下一个中间件/路由处理器

        Returns:
            响应对象
        """
        # 检查是否可缓存
        if not self._is_cacheable(request.url.path, request.method):
            return await call_next(request)

        cache_key = self._make_cache_key(request)

        # 尝试从缓存获取
        cached_response = await self._cache.get(cache_key, "http")
        if cached_response is not None:
            logger.debug(f"Cache hit for {request.url.path}")
            response = JSONResponse(
                content=cached_response["body"],
                status_code=cached_response["status_code"],
            )
            response.headers[self._cache_header] = "HIT"
            # 复制原始响应头
            for key, value in cached_response.get("headers", {}).items():
                response.headers[key] = value
            return response

        # 缓存未命中，执行请求
        logger.debug(f"Cache miss for {request.url.path}")
        response = await call_next(request)

        # 只缓存成功的响应
        if response.status_code == 200:
            # 对于 JSONResponse，可以缓存其内容
            if hasattr(response, "body"):
                try:
                    import json

                    body = json.loads(response.body.decode())

                    cached_data = {
                        "body": body,
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                    }

                    await self._cache.set(
                        cache_key, cached_data, "http", self._default_ttl
                    )

                    # 添加缓存状态头
                    response.headers[self._cache_header] = "MISS"
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass

        return response


def setup_cache_middleware(
    app,
    cache_manager: Optional[CacheManager] = None,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    设置缓存中间件

    Args:
        app: FastAPI 应用
        cache_manager: 缓存管理器
        config: 配置字典

    配置示例:
        {
            "default_ttl": 300,
            "cacheable_paths": ["/api/v1/hotwords"],
            "exclude_prefixes": ["/api/v1/auth", "/api/v1/admin"],
        }
    """
    if config is None:
        config = {}

    middleware = CacheMiddleware(app, cache_manager=cache_manager, **config)

    # 添加中间件到应用
    app.add_middleware(CacheMiddleware, **config)


# ==================== 缓存控制装饰器 ====================


def cache_response(
    ttl: int = 300,
    key_func: Optional[Callable] = None,
    namespace: str = "api",
):
    """
    响应缓存装饰器

    Args:
        ttl: 缓存时间（秒）
        key_func: 自定义键生成函数
        namespace: 命名空间

    使用示例:
        @cache_response(ttl=600)
        async def get_hotwords():
            return {"words": [...]}

        @cache_response(
            ttl=300,
            key_func=lambda domain: f"hotwords:{domain}"
        )
        async def get_hotwords_by_domain(domain: str):
            return {"words": [...]}
    """
    from .cache_manager import cached

    return cached(ttl=ttl, namespace=namespace, key_func=key_func)


def invalidate_cache_pattern(
    pattern_func: Callable,
    namespace: str = "default",
):
    """
    缓存失效装饰器

    Args:
        pattern_func: 模式生成函数
        namespace: 命名空间

    使用示例:
        @invalidate_cache_pattern(
            pattern_func=lambda doc_id: f"doc:*:*:{doc_id}:*"
        )
        async def update_document(doc_id: int, ...):
            ...
    """
    from cache_manager import cache_invalidate

    return cache_invalidate(pattern_func=pattern_func, namespace=namespace)


# ==================== FastAPI 依赖注入 ====================


async def get_cache() -> CacheManager:
    """
    获取缓存管理器（依赖注入）

    Returns:
        CacheManager 实例
    """
    return get_cache_manager()


def cached_endpoint(
    ttl: int = 300,
    key_prefix: str = "",
    include_query_params: bool = True,
    include_user: bool = False,
):
    """
    端点缓存装饰器

    专门用于 FastAPI 路由的缓存装饰器

    Args:
        ttl: 缓存时间（秒）
        key_prefix: 键前缀
        include_query_params: 是否包含查询参数
        include_user: 是否包含用户标识

    使用示例:
        @app.get("/api/v1/hotwords")
        @cached_endpoint(ttl=86400)
        async def get_hotwords(cache: CacheManager = Depends(get_cache)):
            ...
    """

    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            cache = kwargs.get("cache") or get_cache_manager()

            # 从参数中提取 Request 对象
            request: Optional[Request] = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request:
                # 生成缓存键
                path = request.url.path
                query = (
                    str(request.url.query)
                    if include_query_params and request.url.query
                    else ""
                )

                key_parts = [key_prefix, path, query]
                if include_user and "Authorization" in request.headers:
                    import hashlib

                    token = request.headers["Authorization"]
                    if token.startswith("Bearer "):
                        token_hash = hashlib.sha256(token[7:].encode()).hexdigest()[:8]
                        key_parts.append(f"user:{token_hash}")

                cache_key = ":".join(filter(None, key_parts))

                # 尝试获取缓存
                cached_result = await cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

            # 执行函数
            result = await func(*args, **kwargs)

            # 缓存结果
            if request:
                await cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


# ==================== 缓存预热 ====================


class CacheWarmer:
    """
    缓存预热器

    在应用启动时预加载常用数据到缓存
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self._cache = cache_manager or get_cache_manager()
        self._tasks: List[Callable] = []

    def add_task(self, task: Callable) -> None:
        """
        添加预热任务

        Args:
            task: 异步函数，不接受参数
        """
        self._tasks.append(task)

    async def warm_up(self) -> Dict[str, Any]:
        """
        执行所有预热任务

        Returns:
            预热结果统计
        """
        results = {
            "success": 0,
            "failed": 0,
            "errors": [],
        }

        for task in self._tasks:
            try:
                await task()
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(str(e))
                logger.error(f"Cache warm-up task failed: {e}")

        return results

    async def warm_up_hotwords(self, domain: str = "all") -> None:
        """
        预热热词缓存

        Args:
            domain: 领域名称
        """
        from cache_service import get_hotword_cache_service

        service = get_hotword_cache_service()
        # 这里应该从实际数据源加载
        # words = await load_hotwords_from_db(domain)
        # await service.set_hotwords(domain, words)
        logger.info(f"Hotwords cache warmed for domain: {domain}")

    async def warm_up_trending_documents(self, limit: int = 100) -> None:
        """
        预热门文档缓存

        Args:
            limit: 文档数量
        """
        from cache_service import get_document_cache_service

        service = get_document_cache_service()
        # 这里应该从实际数据源加载
        # docs = await get_trending_documents_from_db(limit)
        # for doc in docs:
        #     await service.set_document_info(doc["id"], doc)
        logger.info(f"Trending documents cache warmed: {limit} documents")


# ==================== 缓存统计端点 ====================


async def get_cache_stats_endpoint(
    detailed: bool = False,
    cache: CacheManager = Depends(get_cache),
):
    """
    获取缓存统计信息（API 端点）

    Args:
        detailed: 是否返回详细信息
        cache: 缓存管理器

    Returns:
        统计信息字典
    """
    if detailed:
        return await cache.get_detailed_stats()
    return cache.get_stats()


class CacheControlHeaders:
    """
    HTTP Cache-Control 头管理

    为响应添加适当的缓存控制头
    """

    @staticmethod
    def public(max_age: int = 300) -> Dict[str, str]:
        """
        公共缓存头

        Args:
            max_age: 最大缓存时间（秒）

        Returns:
            响应头字典
        """
        return {
            "Cache-Control": f"public, max-age={max_age}",
        }

    @staticmethod
    def private(max_age: int = 300) -> Dict[str, str]:
        """
        私有缓存头（只能被浏览器缓存）

        Args:
            max_age: 最大缓存时间（秒）

        Returns:
            响应头字典
        """
        return {
            "Cache-Control": f"private, max-age={max_age}",
        }

    @staticmethod
    def no_cache() -> Dict[str, str]:
        """
        不缓存头

        Returns:
            响应头字典
        """
        return {
            "Cache-Control": "no-cache, no-store, must-revalidate",
        }

    @staticmethod
    def no_store() -> Dict[str, str]:
        """
        不存储头

        Returns:
            响应头字典
        """
        return {
            "Cache-Control": "no-store",
        }
