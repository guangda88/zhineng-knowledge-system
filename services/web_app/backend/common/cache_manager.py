# -*- coding: utf-8 -*-
"""
缓存管理器
Cache Manager

提供统一的缓存层，支持多级缓存和TTL策略
支持 Redis 后端和内存后端
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Dict, Optional, Callable, TypeVar, Union, List, Set

from cachetools import TTLCache

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ==================== 缓存键命名规范 ====================


class CacheKeyPattern:
    """
    缓存键命名规范

    格式: {namespace}:{resource}:{identifier}:{version}
    示例: user:info:123:v1
    """

    # 命名空间前缀
    PREFIX = "tcm_kb"

    # 资源类型
    USER = "user"
    DOCUMENT = "doc"
    SEARCH = "search"
    HOTWORD = "hotword"
    EMBEDDING = "embedding"
    SESSION = "session"
    TOKEN_BLACKLIST = "token_bl"
    PERMISSION = "perm"
    RATE_LIMIT = "rate_limit"

    # 数据类型
    INFO = "info"  # 用户信息、文档元数据
    LIST = "list"  # 列表数据
    COUNT = "count"  # 计数数据
    RESULT = "result"  # 搜索结果
    META = "meta"  # 元数据

    # 版本标识（用于缓存失效）
    VERSION = "v1"

    @classmethod
    def build(cls, resource: str, data_type: str, identifier: str, version: str = VERSION) -> str:
        """
        构建缓存键

        Args:
            resource: 资源类型 (user, doc, search等)
            data_type: 数据类型 (info, list, count等)
            identifier: 唯一标识符
            version: 版本号

        Returns:
            完整的缓存键
        """
        return f"{cls.PREFIX}:{resource}:{data_type}:{identifier}:{version}"

    @classmethod
    def user_info(cls, user_id: int) -> str:
        """用户信息缓存键"""
        return cls.build(cls.USER, cls.INFO, str(user_id))

    @classmethod
    def user_by_username(cls, username: str) -> str:
        """通过用户名查找用户的缓存键"""
        return cls.build(cls.USER, "by_username", username.lower())

    @classmethod
    def user_by_email(cls, email: str) -> str:
        """通过邮箱查找用户的缓存键"""
        return cls.build(cls.USER, "by_email", email.lower())

    @classmethod
    def user_roles(cls, user_id: int) -> str:
        """用户角色缓存键"""
        return cls.build(cls.USER, "roles", str(user_id))

    @classmethod
    def user_permissions(cls, user_id: int) -> str:
        """用户权限缓存键"""
        return cls.build(cls.USER, "permissions", str(user_id))

    @classmethod
    def document_info(cls, doc_id: int) -> str:
        """文档信息缓存键"""
        return cls.build(cls.DOCUMENT, cls.INFO, str(doc_id))

    @classmethod
    def document_chunks(cls, doc_id: int) -> str:
        """文档分块列表缓存键"""
        return cls.build(cls.DOCUMENT, "chunks", str(doc_id))

    @classmethod
    def document_metadata(cls, doc_id: int) -> str:
        """文档元数据缓存键"""
        return cls.build(cls.DOCUMENT, cls.META, str(doc_id))

    @classmethod
    def document_list(cls, filters: str) -> str:
        """文档列表缓存键 (基于filter的hash)"""
        filter_hash = hashlib.sha256(filters.encode()).hexdigest()[:8]
        return cls.build(cls.DOCUMENT, cls.LIST, filter_hash)

    @classmethod
    def search_result(cls, query: str, search_type: str, domains: str = "") -> str:
        """搜索结果缓存键"""
        # 对查询参数进行哈希以获得固定长度的键
        query_hash = hashlib.sha256(f"{query}:{search_type}:{domains}".encode()).hexdigest()[:12]
        return cls.build(cls.SEARCH, cls.RESULT, query_hash)

    @classmethod
    def hotword_list(cls, domain: str = "all") -> str:
        """热词列表缓存键"""
        return cls.build(cls.HOTWORD, cls.LIST, domain.lower())

    @classmethod
    def hotword_by_domain(cls, domain: str) -> str:
        """指定域的热词缓存键"""
        return cls.build(cls.HOTWORD, "domain", domain.lower())

    @classmethod
    def embedding(cls, text_hash: str) -> str:
        """向量嵌入缓存键"""
        return cls.build(cls.EMBEDDING, "vec", text_hash)

    @classmethod
    def session(cls, session_id: str) -> str:
        """会话缓存键"""
        return cls.build(cls.SESSION, "data", session_id)

    @classmethod
    def token_blacklist(cls, token_jti: str) -> str:
        """令牌黑名单缓存键"""
        return cls.build(cls.TOKEN_BLACKLIST, "token", token_jti)

    @classmethod
    def rate_limit(cls, identifier: str, endpoint: str) -> str:
        """速率限制缓存键"""
        return cls.build(cls.RATE_LIMIT, endpoint, identifier)

    @classmethod
    def pattern_match(cls, pattern: str) -> str:
        """
        构建模式匹配键（用于批量删除）

        Args:
            pattern: 模式，如 "user:info:*"

        Returns:
            Redis 风格的模式匹配字符串
        """
        return f"{cls.PREFIX}:{pattern}"

    @classmethod
    def parse_key(cls, key: str) -> Dict[str, str]:
        """
        解析缓存键，返回各组成部分

        Args:
            key: 缓存键

        Returns:
            包含 prefix, resource, data_type, identifier, version 的字典
        """
        parts = key.split(":")
        if len(parts) >= 5 and parts[0] == cls.PREFIX:
            return {
                "prefix": parts[0],
                "resource": parts[1],
                "data_type": parts[2],
                "identifier": parts[3],
                "version": parts[4] if len(parts) > 4 else cls.VERSION,
            }
        return {}


# ==================== 缓存配置 ====================


@dataclass
class CacheTTL:
    """缓存TTL配置（秒）"""

    # 用户相关
    USER_INFO = 1800  # 30分钟
    USER_BY_USERNAME = 1800  # 30分钟
    USER_ROLES = 3600  # 1小时
    USER_PERMISSIONS = 1800  # 30分钟

    # 文档相关
    DOCUMENT_INFO = 3600  # 1小时
    DOCUMENT_CHUNKS = 1800  # 30分钟
    DOCUMENT_METADATA = 3600  # 1小时
    DOCUMENT_LIST = 600  # 10分钟

    # 搜索相关
    SEARCH_RESULT = 300  # 5分钟（短期缓存）
    SEARCH_HOTWORD = 86400  # 24小时（热词很少变化）

    # 会话相关
    SESSION = 86400  # 24小时
    TOKEN_BLACKLIST = 604800  # 7天

    # 向量相关
    EMBEDDING = 86400  # 24小时

    # 速率限制
    RATE_LIMIT = 60  # 1分钟


@dataclass
class CacheEntry:
    """缓存条目"""

    value: Any
    hits: int = 0
    created_at: float = 0
    last_accessed: float = 0
    ttl: Optional[int] = None
    size_bytes: int = 0


@dataclass
class CacheStats:
    """缓存统计信息"""

    type: str
    size: int = 0
    maxsize: int = 0
    hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0
    total_memory_bytes: int = 0
    evictions: int = 0
    errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "size": self.size,
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "total_memory_mb": round(self.total_memory_bytes / (1024 * 1024), 2),
            "evictions": self.evictions,
            "errors": self.errors,
        }


class CacheBackend(ABC):
    """缓存后端抽象基类"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值，返回是否成功"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """清空缓存"""
        pass

    @abstractmethod
    async def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的所有键"""
        pass

    @abstractmethod
    async def delete_pattern(self, pattern: str) -> int:
        """删除匹配模式的所有键，返回删除数量"""
        pass

    @abstractmethod
    def get_stats(self) -> CacheStats:
        """获取缓存统计信息"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""
        pass


class MemoryCacheBackend(CacheBackend):
    """
    内存缓存后端

    使用进程内内存，适用于单实例部署
    适合缓存小数据量、访问频繁的数据
    """

    def __init__(self, maxsize: int = 10000, default_ttl: int = 3600):
        """
        初始化内存缓存

        Args:
            maxsize: 最大缓存条目数
            default_ttl: 默认TTL（秒）
        """
        self._cache: TTLCache[str, CacheEntry] = TTLCache(maxsize=maxsize, ttl=default_ttl)
        self._lock = asyncio.Lock()
        self._default_ttl = default_ttl
        self._maxsize = maxsize
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._errors = 0

        # 监听缓存驱逐事件
        self._cache.callback = self._on_evict

    def _on_evict(self, key: str, entry: CacheEntry):
        """缓存驱逐回调"""
        self._evictions += 1
        logger.debug(f"Cache entry evicted: {key}")

    def _estimate_size(self, value: Any) -> int:
        """估算值的字节大小"""
        try:
            return len(json.dumps(value).encode())
        except Exception:
            return len(str(value).encode())

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            async with self._lock:
                entry = self._cache.get(key)
                if entry is None:
                    self._misses += 1
                    return None

                # 检查是否过期（支持自定义 TTL）
                current_time = time.time()
                if entry.ttl and (current_time - entry.created_at) > entry.ttl:
                    # 已过期，删除并返回 None
                    del self._cache[key]
                    self._misses += 1
                    return None

                entry.hits += 1
                entry.last_accessed = current_time
                self._hits += 1
                return entry.value
        except Exception as e:
            self._errors += 1
            logger.error(f"Memory cache get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        try:
            import time

            async with self._lock:
                entry = CacheEntry(
                    value=value,
                    created_at=time.time(),
                    last_accessed=time.time(),
                    ttl=ttl or self._default_ttl,
                    size_bytes=self._estimate_size(value),
                )
                self._cache[key] = entry
                return True
        except Exception as e:
            self._errors += 1
            logger.error(f"Memory cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        try:
            async with self._lock:
                if key in self._cache:
                    del self._cache[key]
                    return True
                return False
        except Exception as e:
            self._errors += 1
            logger.error(f"Memory cache delete error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            async with self._lock:
                return key in self._cache
        except Exception as e:
            self._errors += 1
            return False

    async def clear(self) -> None:
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    async def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的所有键"""
        import fnmatch

        async with self._lock:
            if pattern == "*":
                return list(self._cache.keys())
            return [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]

    async def delete_pattern(self, pattern: str) -> int:
        """删除匹配模式的所有键"""
        import fnmatch

        count = 0
        async with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_delete:
                del self._cache[key]
                count += 1
        return count

    def get_stats(self) -> CacheStats:
        """获取缓存统计信息"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0
        total_memory = sum(e.size_bytes for e in self._cache.values())

        return CacheStats(
            type="memory",
            size=len(self._cache),
            maxsize=self._maxsize,
            hits=self._hits,
            misses=self._misses,
            hit_rate=hit_rate,
            total_memory_bytes=total_memory,
            evictions=self._evictions,
            errors=self._errors,
        )

    async def close(self) -> None:
        """关闭连接（内存缓存无需关闭）"""
        pass


class RedisCacheBackend(CacheBackend):
    """
    Redis 缓存后端

    支持分布式缓存、持久化、发布订阅等特性
    适合多实例部署和大数据量缓存
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        default_ttl: int = 3600,
        decode_responses: bool = False,
        max_connections: int = 50,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5,
        retry_on_timeout: bool = True,
    ):
        """
        初始化 Redis 缓存后端

        Args:
            host: Redis 主机
            port: Redis 端口
            password: Redis 密码
            db: Redis 数据库编号
            default_ttl: 默认TTL（秒）
            decode_responses: 是否解码响应
            max_connections: 最大连接数
            socket_timeout: Socket 超时
            socket_connect_timeout: Socket 连接超时
            retry_on_timeout: 超时重试
        """
        self._host = host
        self._port = port
        self._password = password
        self._db = db
        self._default_ttl = default_ttl
        self._decode_responses = decode_responses

        # 连接池配置
        self._pool = None
        self._client = None
        self._max_connections = max_connections
        self._socket_timeout = socket_timeout
        self._socket_connect_timeout = socket_connect_timeout
        self._retry_on_timeout = retry_on_timeout

        # 统计信息（本地维护）
        self._hits = 0
        self._misses = 0
        self._errors = 0

        # 命中率统计键
        self._stats_key = f"{CacheKeyPattern.PREFIX}:stats:hit_count"

        # 用于跟踪键的命名空间
        self._namespace_sets = f"{CacheKeyPattern.PREFIX}:namespaces"

    async def _get_client(self):
        """获取 Redis 客户端（延迟初始化）"""
        if self._client is None:
            try:
                import redis.asyncio as aioredis
            except ImportError:
                # 回退到 redis-py 的异步支持
                import redis as aioredis

            if self._pool is None:
                self._pool = aioredis.ConnectionPool(
                    host=self._host,
                    port=self._port,
                    password=self._password,
                    db=self._db,
                    max_connections=self._max_connections,
                    socket_timeout=self._socket_timeout,
                    socket_connect_timeout=self._socket_connect_timeout,
                    retry_on_timeout=self._retry_on_timeout,
                    decode_responses=self._decode_responses,
                )

            self._client = aioredis.Redis(connection_pool=self._pool)

        return self._client

    def _serialize(self, value: Any) -> bytes:
        """序列化值"""
        if isinstance(value, bytes):
            return value
        try:
            return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            return json.dumps(value, ensure_ascii=False).encode("utf-8")

    def _deserialize(self, value: bytes) -> Any:
        """反序列化值"""
        try:
            return pickle.loads(value)
        except Exception:
            try:
                return json.loads(value.decode("utf-8"))
            except Exception:
                return value

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            client = await self._get_client()
            value = await client.get(key)

            if value is None:
                self._misses += 1
                return None

            self._hits += 1
            return self._deserialize(value)
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache get error for key '{key}': {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
    ) -> bool:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None 则使用默认值
            namespace: 命名空间（用于按模式删除）

        Returns:
            是否设置成功
        """
        try:
            client = await self._get_client()
            serialized = self._serialize(value)
            ttl = ttl or self._default_ttl

            if ttl > 0:
                await client.setex(key, ttl, serialized)
            else:
                await client.set(key, serialized)

            # 添加到命名空间集合（用于批量删除）
            if namespace:
                await client.sadd(f"{self._namespace_sets}:{namespace}", key)

            return True
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache set error for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        try:
            client = await self._get_client()
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache delete error for key '{key}': {e}")
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            client = await self._get_client()
            return await client.exists(key) > 0
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache exists error for key '{key}': {e}")
            return False

    async def clear(self) -> None:
        """清空所有缓存（慎用！）"""
        try:
            client = await self._get_client()
            # 只删除我们前缀的键，避免影响其他应用
            pattern = f"{CacheKeyPattern.PREFIX}:*"
            keys = []
            async for key in client.scan_iter(match=pattern, count=100):
                keys.append(key)
            if keys:
                await client.delete(*keys)
            self._hits = 0
            self._misses = 0
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache clear error: {e}")

    async def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的所有键"""
        try:
            client = await self._get_client()
            # 添加前缀
            full_pattern = (
                f"{CacheKeyPattern.PREFIX}:{pattern}"
                if not pattern.startswith(CacheKeyPattern.PREFIX)
                else pattern
            )
            keys = []
            async for key in client.scan_iter(match=full_pattern, count=100):
                if isinstance(key, bytes):
                    key = key.decode("utf-8")
                keys.append(key)
            return keys
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache keys error: {e}")
            return []

    async def delete_pattern(self, pattern: str) -> int:
        """删除匹配模式的所有键"""
        try:
            client = await self._get_client()
            full_pattern = (
                f"{CacheKeyPattern.PREFIX}:{pattern}"
                if not pattern.startswith(CacheKeyPattern.PREFIX)
                else pattern
            )
            keys = []
            async for key in client.scan_iter(match=full_pattern, count=100):
                keys.append(key)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache delete_pattern error: {e}")
            return 0

    async def delete_namespace(self, namespace: str) -> int:
        """
        删除指定命名空间的所有缓存

        Args:
            namespace: 命名空间名称

        Returns:
            删除的键数量
        """
        try:
            client = await self._get_client()
            set_key = f"{self._namespace_sets}:{namespace}"
            keys = await client.smembers(set_key)
            if keys:
                await client.delete(*keys)
                await client.delete(set_key)
                return len(keys)
            return 0
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache delete_namespace error: {e}")
            return 0

    async def expire(self, key: str, ttl: int) -> bool:
        """
        设置键的过期时间

        Args:
            key: 缓存键
            ttl: 过期时间（秒）

        Returns:
            是否设置成功
        """
        try:
            client = await self._get_client()
            return await client.expire(key, ttl)
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache expire error for key '{key}': {e}")
            return False

    async def ttl(self, key: str) -> int:
        """
        获取键的剩余过期时间

        Args:
            key: 缓存键

        Returns:
            剩余秒数，-1 表示永不过期，-2 表示键不存在
        """
        try:
            client = await self._get_client()
            return await client.ttl(key)
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache ttl error for key '{key}': {e}")
            return -2

    async def increment(self, key: str, amount: int = 1) -> int:
        """
        原子递增

        Args:
            key: 缓存键
            amount: 递增量

        Returns:
            递增后的值
        """
        try:
            client = await self._get_client()
            return await client.incrby(key, amount)
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache increment error for key '{key}': {e}")
            return 0

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        批量获取

        Args:
            keys: 键列表

        Returns:
            键值字典
        """
        try:
            client = await self._get_client()
            values = await client.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    self._hits += 1
                    result[key] = self._deserialize(value)
                else:
                    self._misses += 1
            return result
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache get_many error: {e}")
            return {}

    async def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        批量设置

        Args:
            mapping: 键值字典
            ttl: 过期时间

        Returns:
            是否全部设置成功
        """
        try:
            client = await self._get_client()
            ttl = ttl or self._default_ttl

            pipe = client.pipeline()
            for key, value in mapping.items():
                serialized = self._serialize(value)
                if ttl > 0:
                    pipe.setex(key, ttl, serialized)
                else:
                    pipe.set(key, serialized)
            await pipe.execute()
            return True
        except Exception as e:
            self._errors += 1
            logger.error(f"Redis cache set_many error: {e}")
            return False

    def get_stats(self) -> CacheStats:
        """获取缓存统计信息"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        return CacheStats(
            type="redis",
            size=0,  # Redis 的键数量需要通过 dbsize 获取
            maxsize=0,  # Redis 没有固定的最大值
            hits=self._hits,
            misses=self._misses,
            hit_rate=hit_rate,
            total_memory_bytes=0,
            evictions=0,
            errors=self._errors,
        )

    async def get_detailed_stats(self) -> Dict[str, Any]:
        """获取详细的 Redis 统计信息"""
        try:
            client = await self._get_client()
            info = await client.info("stats")
            memory_info = await client.info("memory")

            # 获取前缀键的数量
            pattern = f"{CacheKeyPattern.PREFIX}:*"
            key_count = 0
            async for _ in client.scan_iter(match=pattern, count=100):
                key_count += 1

            return {
                "type": "redis",
                "host": self._host,
                "port": self._port,
                "db": self._db,
                "prefix_key_count": key_count,
                "total_keys": await client.dbsize(),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": (
                    self._hits / (self._hits + self._misses)
                    if (self._hits + self._misses) > 0
                    else 0
                ),
                "errors": self._errors,
                "memory": {
                    "used_memory_mb": round(memory_info.get("used_memory", 0) / (1024 * 1024), 2),
                    "used_memory_peak_mb": round(
                        memory_info.get("used_memory_peak", 0) / (1024 * 1024), 2
                    ),
                    "maxmemory_mb": round(memory_info.get("maxmemory", 0) / (1024 * 1024), 2),
                },
                "stats": {
                    "total_commands_processed": info.get("total_commands_processed", 0),
                    "total_connections_received": info.get("total_connections_received", 0),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                },
            }
        except Exception as e:
            logger.error(f"Redis get_detailed_stats error: {e}")
            return {"error": str(e)}

    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            await self._client.close()
            self._client = None
        if self._pool:
            await self._pool.disconnect()
            self._pool = None


class RedisCacheBackendPool:
    """
    Redis 连接池管理器

    管理多个 Redis 实例的连接池
    """

    _instances: Dict[str, RedisCacheBackend] = {}

    @classmethod
    async def get_instance(
        cls,
        name: str = "default",
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        **kwargs,
    ) -> RedisCacheBackend:
        """
        获取 Redis 后端实例（单例模式）

        Args:
            name: 实例名称
            host: Redis 主机
            port: Redis 端口
            password: Redis 密码
            db: 数据库编号
            **kwargs: 其他参数

        Returns:
            RedisCacheBackend 实例
        """
        instance_key = f"{name}:{host}:{port}:{db}"

        if instance_key not in cls._instances:
            cls._instances[instance_key] = RedisCacheBackend(
                host=host, port=port, password=password, db=db, **kwargs
            )

        return cls._instances[instance_key]

    @classmethod
    async def close_all(cls) -> None:
        """关闭所有连接"""
        for instance in cls._instances.values():
            await instance.close()
        cls._instances.clear()


class CacheManager:
    """
    缓存管理器

    支持多命名空间和不同类型的缓存后端
    支持 Redis 和内存缓存
    """

    # 预定义的缓存命名空间
    NAMESPACE_USER = "user"
    NAMESPACE_DOCUMENT = "document"
    NAMESPACE_SEARCH = "search"
    NAMESPACE_HOTWORD = "hotword"
    NAMESPACE_EMBEDDING = "embedding"
    NAMESPACE_SESSION = "session"
    NAMESPACE_TOKEN = "token"

    def __init__(
        self,
        backend: str = "memory",
        redis_config: Optional[Dict[str, Any]] = None,
        default_ttl: int = 3600,
    ):
        """
        初始化缓存管理器

        Args:
            backend: 后端类型 ("memory" 或 "redis")
            redis_config: Redis 配置
            default_ttl: 默认TTL（秒）
        """
        self._backend_type = backend
        self._default_ttl = default_ttl
        self._backends: Dict[str, CacheBackend] = {}
        self._redis_config = redis_config  # 保存配置用于后续命名空间创建

        # 初始化默认后端
        if backend == "redis" and redis_config:
            self._default_backend = RedisCacheBackend(**redis_config)
        else:
            self._default_backend = MemoryCacheBackend(maxsize=10000, default_ttl=default_ttl)

        self._backends["default"] = self._default_backend

        # L1 缓存（内存缓存，作为 Redis 的前端缓存）
        self._l1_cache: Optional[MemoryCacheBackend] = None
        if backend == "redis":
            self._l1_cache = MemoryCacheBackend(maxsize=1000, default_ttl=300)  # 5分钟

    @classmethod
    def from_env(cls) -> "CacheManager":
        """
        从环境变量创建缓存管理器

        Returns:
            CacheManager 实例
        """
        import os

        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_password = os.getenv("REDIS_PASSWORD")
        redis_db = int(os.getenv("REDIS_DB", "0"))

        # 如果配置了 Redis，使用 Redis
        if redis_host and redis_host != "localhost":
            return cls(
                backend="redis",
                redis_config={
                    "host": redis_host,
                    "port": redis_port,
                    "password": redis_password,
                    "db": redis_db,
                },
            )

        # 否则使用内存缓存
        return cls(backend="memory")

    def get_backend(self, namespace: str = "default") -> CacheBackend:
        """获取指定命名空间的缓存后端（懒加载）"""
        if namespace not in self._backends:
            # 为新命名空间创建独立的后端实例
            if self._backend_type == "redis" and hasattr(self, "_redis_config"):
                self._backends[namespace] = RedisCacheBackend(**self._redis_config)
            else:
                self._backends[namespace] = MemoryCacheBackend(
                    maxsize=10000, default_ttl=self._default_ttl
                )
        return self._backends[namespace]

    async def get(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[Any]:
        """
        获取缓存值

        如果配置了 L1 缓存，会先查 L1，再查 L2
        """
        # 先查 L1 缓存
        if self._l1_cache:
            value = await self._l1_cache.get(key)
            if value is not None:
                return value

        # 查 L2 缓存
        backend = self.get_backend(namespace)
        value = await backend.get(key)

        # 回写 L1 缓存
        if value is not None and self._l1_cache:
            await self._l1_cache.set(key, value, ttl=300)

        return value

    async def set(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: Optional[int] = None,
    ) -> bool:
        """
        设置缓存值

        如果配置了 L1 缓存，会同时写入 L1 和 L2
        """
        backend = self.get_backend(namespace)
        success = await backend.set(key, value, ttl)

        # 同时写入 L1 缓存
        if success and self._l1_cache:
            await self._l1_cache.set(key, value, ttl=min(ttl or 300, 300))

        return success

    async def delete(self, key: str, namespace: str = "default") -> bool:
        """删除缓存值"""
        backend = self.get_backend(namespace)
        result = await backend.delete(key)

        # 同时删除 L1 缓存
        if self._l1_cache:
            await self._l1_cache.delete(key)

        return result

    async def exists(self, key: str, namespace: str = "default") -> bool:
        """检查键是否存在"""
        backend = self.get_backend(namespace)
        return await backend.exists(key)

    async def clear(self, namespace: Optional[str] = None) -> None:
        """清空缓存"""
        if namespace is None:
            for backend in self._backends.values():
                await backend.clear()
            if self._l1_cache:
                await self._l1_cache.clear()
        else:
            backend = self.get_backend(namespace)
            await backend.clear()

    async def delete_pattern(self, pattern: str, namespace: str = "default") -> int:
        """删除匹配模式的所有键"""
        backend = self.get_backend(namespace)
        count = await backend.delete_pattern(pattern)

        # 同时删除 L1 缓存
        if self._l1_cache:
            await self._l1_cache.delete_pattern(pattern)

        return count

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if namespace is None:
            stats = {}
            for name, backend in self._backends.items():
                backend_stats = backend.get_stats()
                stats[name] = (
                    backend_stats.to_dict()
                    if hasattr(backend_stats, "to_dict")
                    else backend_stats.__dict__
                )
            if self._l1_cache:
                l1_stats = self._l1_cache.get_stats()
                stats["L1_memory"] = (
                    l1_stats.to_dict() if hasattr(l1_stats, "to_dict") else l1_stats.__dict__
                )
            return stats
        backend = self.get_backend(namespace)
        backend_stats = backend.get_stats()
        return (
            backend_stats.to_dict() if hasattr(backend_stats, "to_dict") else backend_stats.__dict__
        )

    async def get_detailed_stats(self) -> Dict[str, Any]:
        """获取详细的缓存统计信息"""
        stats = {
            "backend_type": self._backend_type,
            "namespaces": self.get_stats(),
        }

        if isinstance(self._default_backend, RedisCacheBackend):
            stats["redis"] = await self._default_backend.get_detailed_stats()

        return stats

    async def close(self) -> None:
        """关闭所有连接"""
        for backend in self._backends.values():
            await backend.close()
        if self._l1_cache:
            await self._l1_cache.close()

    # ==================== 便捷方法 - 使用 CacheKeyPattern ====================

    async def get_user_info(self, user_id: int) -> Optional[Any]:
        """获取用户信息缓存"""
        return await self.get(CacheKeyPattern.user_info(user_id), self.NAMESPACE_USER)

    async def set_user_info(self, user_id: int, user_data: Any) -> bool:
        """设置用户信息缓存"""
        return await self.set(
            CacheKeyPattern.user_info(user_id),
            user_data,
            self.NAMESPACE_USER,
            CacheTTL.USER_INFO,
        )

    async def delete_user(self, user_id: int) -> int:
        """删除用户相关的所有缓存"""
        pattern = f"*:user:*:{user_id}:*"
        return await self.delete_pattern(pattern, self.NAMESPACE_USER)

    async def get_document_info(self, doc_id: int) -> Optional[Any]:
        """获取文档信息缓存"""
        return await self.get(CacheKeyPattern.document_info(doc_id), self.NAMESPACE_DOCUMENT)

    async def set_document_info(self, doc_id: int, doc_data: Any) -> bool:
        """设置文档信息缓存"""
        return await self.set(
            CacheKeyPattern.document_info(doc_id),
            doc_data,
            self.NAMESPACE_DOCUMENT,
            CacheTTL.DOCUMENT_INFO,
        )

    async def invalidate_document(self, doc_id: int) -> int:
        """使文档缓存失效"""
        pattern = f"*:doc:*:{doc_id}:*"
        return await self.delete_pattern(pattern, self.NAMESPACE_DOCUMENT)

    async def get_search_result(
        self, query: str, search_type: str = "hybrid", domains: str = ""
    ) -> Optional[Any]:
        """获取搜索结果缓存"""
        return await self.get(
            CacheKeyPattern.search_result(query, search_type, domains),
            self.NAMESPACE_SEARCH,
        )

    async def set_search_result(
        self, query: str, result: Any, search_type: str = "hybrid", domains: str = ""
    ) -> bool:
        """设置搜索结果缓存"""
        return await self.set(
            CacheKeyPattern.search_result(query, search_type, domains),
            result,
            self.NAMESPACE_SEARCH,
            CacheTTL.SEARCH_RESULT,
        )

    async def get_hotwords(self, domain: str = "all") -> Optional[Any]:
        """获取热词列表缓存"""
        return await self.get(CacheKeyPattern.hotword_list(domain), self.NAMESPACE_HOTWORD)

    async def set_hotwords(self, words: Any, domain: str = "all") -> bool:
        """设置热词列表缓存"""
        return await self.set(
            CacheKeyPattern.hotword_list(domain),
            words,
            self.NAMESPACE_HOTWORD,
            CacheTTL.SEARCH_HOTWORD,
        )

    async def invalidate_hotwords(self, domain: Optional[str] = None) -> int:
        """使热词缓存失效"""
        if domain:
            pattern = f"*:hotword:list:{domain}:*"
        else:
            pattern = "*:hotword:list:*"
        return await self.delete_pattern(pattern, self.NAMESPACE_HOTWORD)

    async def add_to_blacklist(self, token_jti: str, expires_in: int = 604800) -> bool:
        """添加令牌到黑名单"""
        return await self.set(
            CacheKeyPattern.token_blacklist(token_jti),
            True,
            self.NAMESPACE_TOKEN,
            expires_in,
        )

    async def is_blacklisted(self, token_jti: str) -> bool:
        """检查令牌是否在黑名单中"""
        return await self.exists(CacheKeyPattern.token_blacklist(token_jti), self.NAMESPACE_TOKEN)

    async def check_rate_limit(
        self, identifier: str, endpoint: str, limit: int = 100, window: int = 60
    ) -> tuple[bool, int]:
        """
        检查速率限制

        Args:
            identifier: 唯一标识符（如用户ID、IP地址）
            endpoint: 端点名称
            limit: 限制次数
            window: 时间窗口（秒）

        Returns:
            (是否允许, 剩余次数)
        """
        key = CacheKeyPattern.rate_limit(identifier, endpoint)

        if isinstance(self._default_backend, RedisCacheBackend):
            # 使用 Redis 的原子操作
            current = await self._default_backend.increment(key)

            if current == 1:
                # 第一次设置，添加过期时间
                await self._default_backend.expire(key, window)

            allowed = current <= limit
            remaining = max(0, limit - current)
            return allowed, remaining
        else:
            # 内存缓存的简化实现
            current_value = await self.get(key, self.NAMESPACE_TOKEN)
            if current_value is None:
                current_value = {"count": 1, "reset_at": time.time() + window}
                await self.set(key, current_value, self.NAMESPACE_TOKEN, window)
                return True, limit - 1

            if time.time() > current_value.get("reset_at", 0):
                # 时间窗口已过，重置计数
                current_value = {"count": 1, "reset_at": time.time() + window}
                await self.set(key, current_value, self.NAMESPACE_TOKEN, window)
                return True, limit - 1

            current_value["count"] += 1
            allowed = current_value["count"] <= limit
            remaining = max(0, limit - current_value["count"])
            await self.set(key, current_value, self.NAMESPACE_TOKEN, window)
            return allowed, remaining


def cached(
    ttl: int = 3600,
    namespace: str = "default",
    key_func: Optional[Callable] = None,
    cache_manager: Optional[CacheManager] = None,
):
    """
    缓存装饰器

    Args:
        ttl: 缓存TTL（秒）
        namespace: 缓存命名空间
        key_func: 自定义键生成函数
        cache_manager: 缓存管理器实例（默认使用全局实例）

    使用示例:
        @cached(ttl=1800, namespace=CacheManager.NAMESPACE_SEARCH)
        async def search_documents(query: str):
            ...

        @cached(ttl=CacheTTL.USER_INFO, key_func=lambda user_id: CacheKeyPattern.user_info(user_id))
        async def get_user(user_id: int):
            ...
    """
    if cache_manager is None:
        cache_manager = global_cache_manager

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # 生成缓存键
            if key_func is not None:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = CacheKeyPattern.build(
                    func.__name__,
                    "result",
                    hashlib.sha256(str(args + tuple(sorted(kwargs.items()))).encode()).hexdigest()[
                        :16
                    ],
                )

            # 尝试从缓存获取
            cached_value = await cache_manager.get(cache_key, namespace)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key[:20]}...")
                return cached_value

            # 执行函数并缓存结果
            try:
                result = await func(*args, **kwargs)
                await cache_manager.set(cache_key, result, namespace, ttl)
                return result
            except Exception as e:
                logger.error(f"Error in cached function {func.__name__}: {e}")
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            # 同步版本的简单实现
            if key_func is not None:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = CacheKeyPattern.build(
                    func.__name__,
                    "result",
                    hashlib.sha256(str(args + tuple(sorted(kwargs.items()))).encode()).hexdigest()[
                        :16
                    ],
                )

            # 尝试从缓存获取
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 在运行的事件循环中，创建任务
                    task = asyncio.ensure_future(cache_manager.get(cache_key, namespace))
                    cached_value = asyncio.run_coroutine_threadsafe(task, loop).result(timeout=1)
                else:
                    cached_value = loop.run_until_complete(cache_manager.get(cache_key, namespace))

                if cached_value is not None:
                    return cached_value
            except (RuntimeError, asyncio.TimeoutError):
                pass

            # 执行函数
            result = func(*args, **kwargs)

            # 异步设置缓存
            try:
                loop = asyncio.get_event_loop()
                asyncio.ensure_future(cache_manager.set(cache_key, result, namespace, ttl))
            except RuntimeError:
                pass

            return result

        # 根据函数类型选择包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def cache_invalidate(
    pattern_func: Callable,
    namespace: str = "default",
    cache_manager: Optional[CacheManager] = None,
):
    """
    缓存失效装饰器

    在函数执行后使匹配的缓存失效

    Args:
        pattern_func: 生成失效模式的函数
        namespace: 命名空间
        cache_manager: 缓存管理器

    使用示例:
        @cache_invalidate(
            pattern_func=lambda user_id: f"user:*:*:{user_id}:*",
            namespace=CacheManager.NAMESPACE_USER
        )
        async def update_user(user_id: int, ...):
            ...
    """
    if cache_manager is None:
        cache_manager = global_cache_manager

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            result = await func(*args, **kwargs)

            try:
                pattern = pattern_func(*args, **kwargs)
                await cache_manager.delete_pattern(pattern, namespace)
                logger.debug(f"Cache invalidated: {pattern}")
            except Exception as e:
                logger.error(f"Error invalidating cache: {e}")

            return result

        return async_wrapper

    return decorator


# 全局缓存管理器实例
global_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    global global_cache_manager
    if global_cache_manager is None:
        global_cache_manager = CacheManager.from_env()
    return global_cache_manager


def set_cache_manager(manager: CacheManager) -> None:
    """设置全局缓存管理器"""
    global global_cache_manager
    global_cache_manager = manager


# 兼容旧代码
cache_manager = get_cache_manager()


if __name__ == "__main__":
    # 测试代码
    async def test_cache():
        # 测试内存缓存
        print("=== Testing Memory Cache ===")
        manager = CacheManager(backend="memory")

        # 测试基本缓存操作
        await manager.set("test_key", {"data": "test_value"})
        value = await manager.get("test_key")
        print(f"Retrieved value: {value}")

        # 测试缓存键生成
        print("\n=== Testing Cache Keys ===")
        user_key = CacheKeyPattern.user_info(123)
        print(f"User info key: {user_key}")

        doc_key = CacheKeyPattern.document_info(456)
        print(f"Document info key: {doc_key}")

        search_key = CacheKeyPattern.search_result("中医治疗", "hybrid", "tcm")
        print(f"Search result key: {search_key}")

        # 测试缓存统计
        print("\n=== Testing Cache Stats ===")
        stats = await manager.get_detailed_stats()
        print(f"Cache stats: {json.dumps(stats, indent=2, default=str)}")

        # 测试缓存装饰器
        print("\n=== Testing Cache Decorator ===")

        @cached(ttl=60, namespace="test")
        async def expensive_computation(n: int) -> int:
            print(f"Computing for {n}...")
            await asyncio.sleep(0.1)
            return n * n

        # 第一次调用会执行计算
        start = time.time()
        result1 = await expensive_computation(5)
        time1 = time.time() - start

        # 第二次调用从缓存获取
        start = time.time()
        result2 = await expensive_computation(5)
        time2 = time.time() - start

        print(f"First call: {result1}, time: {time1:.4f}s")
        print(f"Second call: {result2}, time: {time2:.4f}s")

        # 测试速率限制
        print("\n=== Testing Rate Limit ===")
        for i in range(12):
            allowed, remaining = await manager.check_rate_limit(
                "user1", "search", limit=10, window=60
            )
            print(f"Request {i+1}: allowed={allowed}, remaining={remaining}")

        await manager.close()

    asyncio.run(test_cache())
