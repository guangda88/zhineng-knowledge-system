"""Redis缓存实现

使用Redis作为L2缓存，支持连接池、健康检查、重试机制
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


def _sanitize_url(url: str) -> str:
    """Remove password from URL for safe logging."""
    return re.sub(r"(:\/\/[^:]+:)([^@]+)(@)", r"\1***\3", url)


try:
    import redis.asyncio as aioredis
    from redis.exceptions import ConnectionError, RedisError, TimeoutError

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None  # type: ignore
    RedisError = Exception  # type: ignore
    ConnectionError = Exception  # type: ignore
    TimeoutError = Exception  # type: ignore

logger = logging.getLogger(__name__)


class RedisStatus(Enum):
    """Redis连接状态"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class RedisConfig:
    """Redis配置"""

    url: str = "redis://localhost:6379/0"
    key_prefix: str = "zhineng_kb:"
    max_connections: int = 50
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    retry_on_timeout: bool = True
    retry_attempts: int = 3
    retry_delay: float = 0.1
    health_check_interval: int = 30  # 健康检查间隔（秒）
    decode_responses: bool = True
    encoding: str = "utf-8"


class RedisConnectionPool:
    """Redis连接池管理器"""

    def __init__(self, config: RedisConfig):
        """初始化连接池

        Args:
            config: Redis配置
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis-py not installed. Install with: pip install redis")

        self.config = config
        self._pool: Optional["aioredis.ConnectionPool"] = None  # type: ignore
        self._status = RedisStatus.DISCONNECTED
        self._lock = asyncio.Lock()
        self._last_health_check = 0.0

    @property
    def status(self) -> RedisStatus:
        """获取连接状态"""
        return self._status

    async def _create_pool(self) -> "aioredis.ConnectionPool":  # type: ignore
        """创建连接池

        Returns:
            Redis连接池
        """
        self._status = RedisStatus.CONNECTING

        pool = aioredis.ConnectionPool.from_url(
            self.config.url,
            max_connections=self.config.max_connections,
            socket_timeout=self.config.socket_timeout,
            socket_connect_timeout=self.config.socket_connect_timeout,
            retry_on_timeout=self.config.retry_on_timeout,
            decode_responses=self.config.decode_responses,
            encoding=self.config.encoding,
        )

        self._status = RedisStatus.CONNECTED
        sanitized = _sanitize_url(self.config.url)
        logger.info(f"Redis连接池创建成功: {sanitized}")

        return pool

    async def get_pool(self) -> "aioredis.ConnectionPool":  # type: ignore
        """获取连接池

        Returns:
            Redis连接池
        """
        async with self._lock:
            if self._pool is None:
                self._pool = await self._create_pool()
            return self._pool

    async def get_client(self) -> "aioredis.Redis":  # type: ignore
        """获取Redis客户端

        Returns:
            Redis客户端
        """
        pool = await self.get_pool()
        return aioredis.Redis(connection_pool=pool)

    async def health_check(self) -> bool:
        """健康检查

        Returns:
            是否健康
        """
        current_time = time.time()

        # 避免频繁检查
        if current_time - self._last_health_check < self.config.health_check_interval:
            return self._status == RedisStatus.CONNECTED

        self._last_health_check = current_time

        try:
            client = await self.get_client()
            await client.ping()
            self._status = RedisStatus.CONNECTED
            return True
        except Exception as e:
            logger.warning(f"Redis健康检查失败: {e}")
            self._status = RedisStatus.ERROR
            return False

    async def close(self) -> None:
        """关闭连接池"""
        async with self._lock:
            if self._pool:
                await self._pool.aclose()
                self._pool = None
                self._status = RedisStatus.DISCONNECTED
                logger.info("Redis连接池已关闭")


class RedisCache:
    """Redis缓存

    使用Redis作为分布式缓存，支持：
    - 连接池管理
    - 健康检查
    - 重试机制
    - Pipeline批量操作
    - 事务支持
    """

    def __init__(
        self,
        url: Optional[str] = None,
        config: Optional[RedisConfig] = None,
        key_prefix: str = "zhineng_kb:",
    ):
        """初始化Redis缓存

        Args:
            url: Redis连接URL
            config: Redis配置
            key_prefix: 键前缀
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis-py not installed. Install with: pip install redis")

        if config:
            self.config = config
        else:
            self.config = RedisConfig(url=url or "redis://localhost:6379/0", key_prefix=key_prefix)

        self._pool_manager = RedisConnectionPool(self.config)
        self._client: Optional["aioredis.Redis"] = None  # type: ignore
        self._circuit_breaker_open = False
        self._circuit_breaker_until = 0.0
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = 60  # 秒

    async def _get_client(self) -> "aioredis.Redis":  # type: ignore
        """获取Redis客户端

        Returns:
            Redis客户端
        """
        if self._client is None:
            self._client = await self._pool_manager.get_client()
        return self._client

    async def _execute_with_retry(
        self,
        fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """带重试的执行

        Args:
            fn: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            执行结果

        Raises:
            RedisError: 执行失败
        """
        last_error = None

        for attempt in range(self.config.retry_attempts):
            try:
                client = await self._get_client()
                result = await fn(client, *args, **kwargs)
                # 成功后重置断路器计数
                self._circuit_breaker_failures = 0
                self._circuit_breaker_open = False
                return result
            except (ConnectionError, TimeoutError) as e:
                last_error = e
                self._circuit_breaker_failures += 1

                # 检查断路器
                if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
                    self._circuit_breaker_open = True
                    self._circuit_breaker_until = time.time() + self._circuit_breaker_timeout
                    logger.error("Redis断路器已打开")

                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
            except RedisError as e:
                last_error = e
                break

        # 检查断路器
        if self._circuit_breaker_open and time.time() < self._circuit_breaker_until:
            logger.warning("Redis断路器已打开，请求被拒绝")
            return None

        raise last_error if last_error else RedisError("Unknown error")

    def _serialize(self, value: Any) -> str:
        """序列化值

        Args:
            value: 要序列化的值

        Returns:
            JSON字符串
        """
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        if isinstance(value, bytes):
            return value.decode(self.config.encoding)
        return json.dumps(value, ensure_ascii=False, default=str)

    def _deserialize(self, value: str) -> Any:
        """反序列化值

        Args:
            value: 要反反序列化的字符串

        Returns:
            反序列化后的值
        """
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value

    def _make_key(self, key: str) -> str:
        """生成完整缓存键

        Args:
            key: 原始键

        Returns:
            完整缓存键
        """
        return f"{self.config.key_prefix}{key}"

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在返回None
        """
        try:
            full_key = self._make_key(key)

            result = await self._execute_with_retry(lambda client, k: client.get(k), full_key)

            if result is None:
                return None

            return self._deserialize(result)
        except Exception as e:
            logger.error(f"Redis GET 失败: {e}")
            return None

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存值

        Args:
            keys: 缓存键列表

        Returns:
            键值对字典
        """
        try:
            full_keys = [self._make_key(k) for k in keys]

            result = await self._execute_with_retry(lambda client, ks: client.mget(ks), full_keys)

            return {k: self._deserialize(v) for k, v in zip(keys, result) if v is not None}
        except Exception as e:
            logger.error(f"Redis MGET 失败: {e}")
            return {}

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）

        Returns:
            是否成功
        """
        try:
            full_key = self._make_key(key)
            serialized = self._serialize(value)

            if ttl and ttl > 0:
                await self._execute_with_retry(
                    lambda client, k, v, t: client.setex(k, t, v), full_key, serialized, ttl
                )
            else:
                await self._execute_with_retry(
                    lambda client, k, v: client.set(k, v), full_key, serialized
                )

            return True
        except Exception as e:
            logger.error(f"Redis SET 失败: {e}")
            return False

    async def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """批量设置缓存值

        Args:
            mapping: 键值对字典
            ttl: 过期时间（秒）

        Returns:
            是否成功
        """
        try:
            async with await self._get_client().pipeline(transaction=False) as pipe:
                for key, value in mapping.items():
                    full_key = self._make_key(key)
                    serialized = self._serialize(value)

                    if ttl and ttl > 0:
                        await pipe.setex(full_key, ttl, serialized)
                    else:
                        await pipe.set(full_key, serialized)

                await pipe.execute()

            return True
        except Exception as e:
            logger.error(f"Redis MSET 失败: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否成功
        """
        try:
            full_key = self._make_key(key)
            await self._execute_with_retry(lambda client, k: client.delete(k), full_key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE 失败: {e}")
            return False

    async def delete_many(self, keys: List[str]) -> int:
        """批量删除缓存值

        Args:
            keys: 缓存键列表

        Returns:
            删除数量
        """
        try:
            full_keys = [self._make_key(k) for k in keys]
            result = await self._execute_with_retry(
                lambda client, ks: client.delete(*ks), full_keys
            )
            return result or 0
        except Exception as e:
            logger.error(f"Redis DELETE 多个键失败: {e}")
            return 0

    async def delete_pattern(self, pattern: str) -> int:
        """按模式删除缓存

        Args:
            pattern: 匹配模式

        Returns:
            删除数量
        """
        try:
            full_pattern = self._make_key(pattern)
            client = await self._get_client()

            keys = []
            async for key in client.scan_iter(match=full_pattern, count=100):
                keys.append(key)

                # 批量删除，避免一次删除太多
                if len(keys) >= 100:
                    await client.delete(*keys)
                    keys.clear()

            if keys:
                await client.delete(*keys)

            return len(keys)
        except Exception as e:
            logger.error(f"Redis DELETE_PATTERN 失败: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        """检查键是否存在

        Args:
            key: 缓存键

        Returns:
            是否存在
        """
        try:
            full_key = self._make_key(key)
            result = await self._execute_with_retry(lambda client, k: client.exists(k), full_key)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis EXISTS 失败: {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间

        Args:
            key: 缓存键
            ttl: 过期时间（秒）

        Returns:
            是否成功
        """
        try:
            full_key = self._make_key(key)
            result = await self._execute_with_retry(
                lambda client, k, t: client.expire(k, t), full_key, ttl
            )
            return bool(result)
        except Exception as e:
            logger.error(f"Redis EXPIRE 失败: {e}")
            return False

    async def ttl(self, key: str) -> int:
        """获取剩余过期时间

        Args:
            key: 缓存键

        Returns:
            剩余秒数，-1表示永不过期，-2表示不存在
        """
        try:
            full_key = self._make_key(key)
            result = await self._execute_with_retry(lambda client, k: client.ttl(k), full_key)
            return result or -2
        except Exception as e:
            logger.error(f"Redis TTL 失败: {e}")
            return -2

    async def increment(self, key: str, delta: int = 1) -> Optional[int]:
        """原子递增

        Args:
            key: 缓存键
            delta: 增量

        Returns:
            新值
        """
        try:
            full_key = self._make_key(key)
            result = await self._execute_with_retry(
                lambda client, k, d: client.incrby(k, d), full_key, delta
            )
            return result
        except Exception as e:
            logger.error(f"Redis INCR 失败: {e}")
            return None

    async def clear(self) -> bool:
        """清空所有带前缀的缓存

        Returns:
            是否成功
        """
        return await self.delete_pattern("*") > 0

    async def get_info(self) -> Dict[str, Any]:
        """获取缓存信息

        Returns:
            缓存信息
        """
        info = {
            "type": "redis",
            "url": self.config.url,
            "prefix": self.config.key_prefix,
            "status": self._pool_manager.status.value,
            "circuit_breaker_open": self._circuit_breaker_open,
            "circuit_breaker_failures": self._circuit_breaker_failures,
        }

        try:
            client = await self._get_client()
            # 获取数据库信息
            db_size = await client.dbsize()
            info["db_size"] = db_size

            # 获取内存使用
            memory_info = await client.info("memory")
            info["used_memory"] = memory_info.get("used_memory_human", "unknown")
        except Exception as e:
            logger.warning(f"获取Redis信息失败: {e}")

        return info

    async def health_check(self) -> bool:
        """健康检查

        Returns:
            是否健康
        """
        return await self._pool_manager.health_check()

    async def close(self) -> None:
        """关闭Redis连接"""
        await self._pool_manager.close()
        self._client = None
