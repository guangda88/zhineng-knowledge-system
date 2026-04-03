# -*- coding: utf-8 -*-
"""
缓存服务层
Cache Service Layer

提供针对特定业务场景的缓存服务
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from .cache_manager import (
    CacheManager,
    CacheKeyPattern,
    CacheTTL,
    cached,
    cache_invalidate,
    get_cache_manager,
)

logger = logging.getLogger(__name__)


# ==================== 用户缓存服务 ====================


class UserCacheService:
    """
    用户缓存服务

    提供用户信息、角色、权限的缓存管理
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self._cache = cache_manager or get_cache_manager()
        self._namespace = CacheManager.NAMESPACE_USER

    async def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        获取用户信息（带缓存）

        Args:
            user_id: 用户ID

        Returns:
            用户信息字典，如果不存在返回 None
        """
        key = CacheKeyPattern.user_info(user_id)
        cached_data = await self._cache.get(key, self._namespace)

        if cached_data is not None:
            logger.debug(f"User {user_id} info cache hit")
            return cached_data

        return None

    async def set_user_info(self, user_id: int, user_data: Dict[str, Any]) -> bool:
        """
        设置用户信息缓存

        Args:
            user_id: 用户ID
            user_data: 用户数据

        Returns:
            是否设置成功
        """
        key = CacheKeyPattern.user_info(user_id)

        # 移除敏感数据
        cache_data = user_data.copy()
        cache_data.pop("password_hash", None)

        return await self._cache.set(key, cache_data, self._namespace, CacheTTL.USER_INFO)

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        根据用户名获取用户（带缓存）

        Args:
            username: 用户名

        Returns:
            用户信息字典
        """
        key = CacheKeyPattern.user_by_username(username)
        return await self._cache.get(key, self._namespace)

    async def set_user_by_username(self, username: str, user_data: Dict[str, Any]) -> bool:
        """
        根据用户名设置用户缓存

        Args:
            username: 用户名
            user_data: 用户数据

        Returns:
            是否设置成功
        """
        key = CacheKeyPattern.user_by_username(username)
        cache_data = user_data.copy()
        cache_data.pop("password_hash", None)
        return await self._cache.set(key, cache_data, self._namespace, CacheTTL.USER_BY_USERNAME)

    async def get_user_roles(self, user_id: int) -> Optional[List[str]]:
        """
        获取用户角色（带缓存）

        Args:
            user_id: 用户ID

        Returns:
            角色列表
        """
        key = CacheKeyPattern.user_roles(user_id)
        return await self._cache.get(key, self._namespace)

    async def set_user_roles(self, user_id: int, roles: List[str]) -> bool:
        """
        设置用户角色缓存

        Args:
            user_id: 用户ID
            roles: 角色列表

        Returns:
            是否设置成功
        """
        key = CacheKeyPattern.user_roles(user_id)
        return await self._cache.set(key, roles, self._namespace, CacheTTL.USER_ROLES)

    async def invalidate_user(self, user_id: int, username: Optional[str] = None) -> None:
        """
        使用户相关缓存失效

        Args:
            user_id: 用户ID
            username: 用户名（可选，用于额外的失效）
        """
        # 删除用户信息缓存
        await self._cache.delete(CacheKeyPattern.user_info(user_id), self._namespace)
        await self._cache.delete(CacheKeyPattern.user_roles(user_id), self._namespace)
        await self._cache.delete(CacheKeyPattern.user_permissions(user_id), self._namespace)

        if username:
            await self._cache.delete(CacheKeyPattern.user_by_username(username), self._namespace)

        logger.debug(f"Invalidated cache for user {user_id}")


# ==================== 文档缓存服务 ====================


class DocumentCacheService:
    """
    文档缓存服务

    提供文档信息、元数据、分块的缓存管理
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self._cache = cache_manager or get_cache_manager()
        self._namespace = CacheManager.NAMESPACE_DOCUMENT

    async def get_document_info(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """
        获取文档信息（带缓存）

        Args:
            doc_id: 文档ID

        Returns:
            文档信息字典
        """
        key = CacheKeyPattern.document_info(doc_id)
        return await self._cache.get(key, self._namespace)

    async def set_document_info(self, doc_id: int, doc_data: Dict[str, Any]) -> bool:
        """
        设置文档信息缓存

        Args:
            doc_id: 文档ID
            doc_data: 文档数据

        Returns:
            是否设置成功
        """
        key = CacheKeyPattern.document_info(doc_id)
        return await self._cache.set(key, doc_data, self._namespace, CacheTTL.DOCUMENT_INFO)

    async def get_document_metadata(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """
        获取文档元数据（带缓存）

        Args:
            doc_id: 文档ID

        Returns:
            元数据字典
        """
        key = CacheKeyPattern.document_metadata(doc_id)
        return await self._cache.get(key, self._namespace)

    async def set_document_metadata(self, doc_id: int, metadata: Dict[str, Any]) -> bool:
        """
        设置文档元数据缓存

        Args:
            doc_id: 文档ID
            metadata: 元数据

        Returns:
            是否设置成功
        """
        key = CacheKeyPattern.document_metadata(doc_id)
        return await self._cache.set(key, metadata, self._namespace, CacheTTL.DOCUMENT_METADATA)

    async def get_document_chunks(self, doc_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        获取文档分块列表（带缓存）

        Args:
            doc_id: 文档ID

        Returns:
            分块列表
        """
        key = CacheKeyPattern.document_chunks(doc_id)
        return await self._cache.get(key, self._namespace)

    async def set_document_chunks(self, doc_id: int, chunks: List[Dict[str, Any]]) -> bool:
        """
        设置文档分块列表缓存

        Args:
            doc_id: 文档ID
            chunks: 分块列表

        Returns:
            是否设置成功
        """
        key = CacheKeyPattern.document_chunks(doc_id)
        return await self._cache.set(key, chunks, self._namespace, CacheTTL.DOCUMENT_CHUNKS)

    async def get_document_list(self, filters: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        获取文档列表（带缓存）

        Args:
            filters: 过滤条件

        Returns:
            文档列表
        """
        filter_str = json.dumps(filters, sort_keys=True)
        key = CacheKeyPattern.document_list(filter_str)
        return await self._cache.get(key, self._namespace)

    async def set_document_list(
        self, filters: Dict[str, Any], documents: List[Dict[str, Any]]
    ) -> bool:
        """
        设置文档列表缓存

        Args:
            filters: 过滤条件
            documents: 文档列表

        Returns:
            是否设置成功
        """
        filter_str = json.dumps(filters, sort_keys=True)
        key = CacheKeyPattern.document_list(filter_str)
        return await self._cache.set(key, documents, self._namespace, CacheTTL.DOCUMENT_LIST)

    async def invalidate_document(self, doc_id: int) -> None:
        """
        使文档相关缓存失效

        Args:
            doc_id: 文档ID
        """
        # 匹配格式: tcm_kb:doc:info:{doc_id}:v1, tcm_kb:doc:chunks:{doc_id}:v1, etc.
        pattern = f"*:doc:*:{doc_id}:*"
        count = await self._cache.delete_pattern(pattern, self._namespace)
        logger.debug(f"Invalidated {count} cache entries for document {doc_id}")

    async def invalidate_document_list(self) -> None:
        """使所有文档列表缓存失效"""
        pattern = "doc:list:*"
        count = await self._cache.delete_pattern(pattern, self._namespace)
        logger.debug(f"Invalidated {count} document list cache entries")


# ==================== 搜索缓存服务 ====================


class SearchCacheService:
    """
    搜索缓存服务

    提供搜索结果的短期缓存
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self._cache = cache_manager or get_cache_manager()
        self._namespace = CacheManager.NAMESPACE_SEARCH

    async def get_search_result(
        self,
        query: str,
        search_type: str = "hybrid",
        domains: Optional[List[str]] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        获取搜索结果（带缓存）

        Args:
            query: 查询字符串
            search_type: 搜索类型
            domains: 域名列表
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            搜索结果字典
        """
        domains_str = ",".join(sorted(domains)) if domains else ""
        # 包含 limit 和 offset 在键中
        key = CacheKeyPattern.search_result(query, search_type, domains_str)
        full_key = f"{key}:l{limit}:o{offset}"

        return await self._cache.get(full_key, self._namespace)

    async def set_search_result(
        self,
        query: str,
        result: Dict[str, Any],
        search_type: str = "hybrid",
        domains: Optional[List[str]] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> bool:
        """
        设置搜索结果缓存

        Args:
            query: 查询字符串
            result: 搜索结果
            search_type: 搜索类型
            domains: 域名列表
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            是否设置成功
        """
        domains_str = ",".join(sorted(domains)) if domains else ""
        key = CacheKeyPattern.search_result(query, search_type, domains_str)
        full_key = f"{key}:l{limit}:o{offset}"

        return await self._cache.set(full_key, result, self._namespace, CacheTTL.SEARCH_RESULT)

    async def get_trending_queries(self, limit: int = 10) -> Optional[List[str]]:
        """
        获取热门搜索查询

        Args:
            limit: 返回数量

        Returns:
            热门查询列表
        """
        key = f"{CacheKeyPattern.PREFIX}:search:trending:queries"
        return await self._cache.get(key, self._namespace)

    async def record_query(self, query: str) -> None:
        """
        记录搜索查询（用于统计热门查询）

        Args:
            query: 查询字符串
        """
        # 使用 Redis 的 sorted set 来记录查询频率
        if isinstance(self._cache._default_backend, type(self._cache._default_backend)):
            try:
                # 这里需要访问 Redis 的特有方法
                pass
            except Exception:
                pass

    async def invalidate_search_results(self) -> None:
        """使所有搜索结果缓存失效"""
        pattern = "search:result:*"
        count = await self._cache.delete_pattern(pattern, self._namespace)
        logger.debug(f"Invalidated {count} search result cache entries")


# ==================== 热词缓存服务 ====================


class HotwordCacheService:
    """
    热词缓存服务

    提供专业领域热词的长期缓存
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self._cache = cache_manager or get_cache_manager()
        self._namespace = CacheManager.NAMESPACE_HOTWORD

    async def get_hotwords(self, domain: str = "all") -> Optional[List[Dict[str, Any]]]:
        """
        获取热词列表（带缓存）

        Args:
            domain: 领域名称

        Returns:
            热词列表
        """
        key = CacheKeyPattern.hotword_list(domain)
        return await self._cache.get(key, self._namespace)

    async def set_hotwords(self, domain: str, words: List[Dict[str, Any]]) -> bool:
        """
        设置热词列表缓存

        Args:
            domain: 领域名称
            words: 热词列表

        Returns:
            是否设置成功
        """
        key = CacheKeyPattern.hotword_list(domain)
        return await self._cache.set(key, words, self._namespace, CacheTTL.SEARCH_HOTWORD)

    async def get_hotwords_by_domain(self, domain: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取指定领域的热词

        Args:
            domain: 领域名称

        Returns:
            热词列表
        """
        key = CacheKeyPattern.hotword_by_domain(domain)
        return await self._cache.get(key, self._namespace)

    async def set_hotwords_by_domain(self, domain: str, words: List[Dict[str, Any]]) -> bool:
        """
        设置指定领域的热词缓存

        Args:
            domain: 领域名称
            words: 热词列表

        Returns:
            是否设置成功
        """
        key = CacheKeyPattern.hotword_by_domain(domain)
        return await self._cache.set(key, words, self._namespace, CacheTTL.SEARCH_HOTWORD)

    async def invalidate_hotwords(self, domain: Optional[str] = None) -> None:
        """
        使热词缓存失效

        Args:
            domain: 领域名称，None 表示全部失效
        """
        if domain:
            pattern = f"hotword:list:{domain.lower()}:*"
            await self._cache.delete(pattern, self._namespace)
            pattern = f"hotword:domain:{domain.lower()}:*"
            await self._cache.delete(pattern, self._namespace)
        else:
            pattern = "hotword:*"
            count = await self._cache.delete_pattern(pattern, self._namespace)
            logger.debug(f"Invalidated {count} hotword cache entries")


# ==================== 会话缓存服务 ====================


class SessionCacheService:
    """
    会话缓存服务

    提供用户会话的缓存管理
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self._cache = cache_manager or get_cache_manager()
        self._namespace = CacheManager.NAMESPACE_SESSION

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话数据

        Args:
            session_id: 会话ID

        Returns:
            会话数据
        """
        key = CacheKeyPattern.session(session_id)
        return await self._cache.get(key, self._namespace)

    async def set_session(
        self, session_id: str, session_data: Dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        """
        设置会话数据

        Args:
            session_id: 会话ID
            session_data: 会话数据
            ttl: 过期时间（秒）

        Returns:
            是否设置成功
        """
        key = CacheKeyPattern.session(session_id)
        return await self._cache.set(key, session_data, self._namespace, ttl or CacheTTL.SESSION)

    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话ID

        Returns:
            是否删除成功
        """
        key = CacheKeyPattern.session(session_id)
        return await self._cache.delete(key, self._namespace)

    async def refresh_session(self, session_id: str, ttl: Optional[int] = None) -> bool:
        """
        刷新会话过期时间

        Args:
            session_id: 会话ID
            ttl: 新的过期时间

        Returns:
            是否刷新成功
        """
        key = CacheKeyPattern.session(session_id)
        if isinstance(self._cache._default_backend, type(self._cache._default_backend)):
            return await self._cache._default_backend.expire(key, ttl or CacheTTL.SESSION)
        return False


# ==================== 全局服务实例 ====================

_user_cache_service: Optional[UserCacheService] = None
_document_cache_service: Optional[DocumentCacheService] = None
_search_cache_service: Optional[SearchCacheService] = None
_hotword_cache_service: Optional[HotwordCacheService] = None
_session_cache_service: Optional[SessionCacheService] = None


def get_user_cache_service() -> UserCacheService:
    """获取用户缓存服务实例"""
    global _user_cache_service
    if _user_cache_service is None:
        _user_cache_service = UserCacheService()
    return _user_cache_service


def get_document_cache_service() -> DocumentCacheService:
    """获取文档缓存服务实例"""
    global _document_cache_service
    if _document_cache_service is None:
        _document_cache_service = DocumentCacheService()
    return _document_cache_service


def get_search_cache_service() -> SearchCacheService:
    """获取搜索缓存服务实例"""
    global _search_cache_service
    if _search_cache_service is None:
        _search_cache_service = SearchCacheService()
    return _search_cache_service


def get_hotword_cache_service() -> HotwordCacheService:
    """获取热词缓存服务实例"""
    global _hotword_cache_service
    if _hotword_cache_service is None:
        _hotword_cache_service = HotwordCacheService()
    return _hotword_cache_service


def get_session_cache_service() -> SessionCacheService:
    """获取会话缓存服务实例"""
    global _session_cache_service
    if _session_cache_service is None:
        _session_cache_service = SessionCacheService()
    return _session_cache_service
