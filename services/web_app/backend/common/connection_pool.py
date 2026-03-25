# -*- coding: utf-8 -*-
"""
HTTP连接池管理器
HTTP Connection Pool Manager

提供全局HTTP连接池，支持连接复用和高效并发

优化功能:
- 连接健康检查
- 详细监控指标
- 请求重试机制
- 自适应超时配置
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from collections import deque

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PoolMetrics:
    """连接池指标"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_timeout_errors: int = 0
    total_connection_errors: int = 0
    active_connections: int = 0
    request_times: deque = field(default_factory=lambda: deque(maxlen=100))

    @property
    def success_rate(self) -> float:
        """成功率百分比"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def avg_request_time(self) -> float:
        """平均请求时间(毫秒)"""
        if not self.request_times:
            return 0.0
        return sum(self.request_times) / len(self.request_times)

    @property
    def p95_request_time(self) -> float:
        """P95请求时间(毫秒)"""
        if not self.request_times:
            return 0.0
        sorted_times = sorted(self.request_times)
        return sorted_times[int(len(sorted_times) * 0.95)]

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "timeout_errors": self.total_timeout_errors,
            "connection_errors": self.total_connection_errors,
            "success_rate": round(self.success_rate, 2),
            "avg_request_time_ms": round(self.avg_request_time, 2),
            "p95_request_time_ms": round(self.p95_request_time, 2),
        }


class HTTPConnectionPool:
    """
    全局HTTP连接池

    使用单例模式管理httpx.AsyncClient，实现连接复用

    优化功能:
    - 连接健康检查
    - 请求重试机制
    - 详细监控指标
    - 自适应超时
    """

    _instance: Optional["HTTPConnectionPool"] = None
    _lock = asyncio.Lock()

    # 默认配置
    DEFAULT_MAX_CONNECTIONS = 100
    DEFAULT_MAX_KEEPALIVE = 50
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_CONNECT_TIMEOUT = 10.0
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 0.5
    DEFAULT_HEALTH_CHECK_INTERVAL = 300  # 5分钟

    def __init__(self):
        """初始化连接池（私有构造函数）"""
        self._client: Optional[httpx.AsyncClient] = None
        self._client_sync: Optional[httpx.Client] = None
        self._metrics_async = PoolMetrics()
        self._metrics_sync = PoolMetrics()
        self._last_health_check = 0
        self._health_check_interval = self.DEFAULT_HEALTH_CHECK_INTERVAL
        self._is_healthy = True

    @classmethod
    async def get_instance(cls) -> "HTTPConnectionPool":
        """获取连接池单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def get_instance_sync(cls) -> "HTTPConnectionPool":
        """获取连接池单例实例（同步版本）"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_async_client(
        self,
        max_connections: int = None,
        max_keepalive_connections: int = None,
        timeout: float = None,
        connect_timeout: float = None,
        read_timeout: float = None,
        write_timeout: float = None,
        pool_idle_timeout: float = None,
        http2: bool = True,
    ) -> httpx.AsyncClient:
        """
        获取异步HTTP客户端

        Args:
            max_connections: 最大连接数 (默认: 100)
            max_keepalive_connections: 最大保持活动连接数 (默认: 50)
            timeout: 请求总超时时间（秒）
            connect_timeout: 连接超时时间（秒）
            read_timeout: 读取超时时间（秒）
            write_timeout: 写入超时时间（秒）
            pool_idle_timeout: 连接池空闲超时（秒）
            http2: 是否启用HTTP/2

        Returns:
            httpx.AsyncClient实例
        """
        # 使用默认值
        max_connections = max_connections or self.DEFAULT_MAX_CONNECTIONS
        max_keepalive_connections = (
            max_keepalive_connections or self.DEFAULT_MAX_KEEPALIVE
        )
        timeout = timeout or self.DEFAULT_TIMEOUT
        connect_timeout = connect_timeout or self.DEFAULT_CONNECT_TIMEOUT
        pool_idle_timeout = pool_idle_timeout or 30.0

        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_keepalive_connections=max_keepalive_connections,
                max_connections=max_connections,
                keepalive_expiry=pool_idle_timeout,
            )
            timeout_config = httpx.Timeout(
                timeout=timeout,
                connect=connect_timeout,
                read=read_timeout,
                write=write_timeout,
            )

            # 配置事件钩子用于监控
            event_hooks = {
                "request": [self._log_request],
                "response": [self._log_response],
                "error": [self._log_error],
            }

            self._client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout_config,
                http2=http2,
                verify=True,
                event_hooks=event_hooks,
            )
            logger.info(
                f"Created new HTTP connection pool: "
                f"max_connections={max_connections}, "
                f"max_keepalive={max_keepalive_connections}, "
                f"http2={http2}"
            )

        return self._client

    def get_sync_client(
        self,
        max_connections: int = None,
        max_keepalive_connections: int = None,
        timeout: float = None,
        connect_timeout: float = None,
        http2: bool = True,
    ) -> httpx.Client:
        """
        获取同步HTTP客户端

        Args:
            max_connections: 最大连接数 (默认: 100)
            max_keepalive_connections: 最大保持活动连接数 (默认: 50)
            timeout: 请求超时时间（秒）
            connect_timeout: 连接超时时间（秒）
            http2: 是否启用HTTP/2

        Returns:
            httpx.Client实例
        """
        max_connections = max_connections or self.DEFAULT_MAX_CONNECTIONS
        max_keepalive_connections = (
            max_keepalive_connections or self.DEFAULT_MAX_KEEPALIVE
        )
        timeout = timeout or self.DEFAULT_TIMEOUT
        connect_timeout = connect_timeout or self.DEFAULT_CONNECT_TIMEOUT

        if self._client_sync is None or self._client_sync.is_closed:
            limits = httpx.Limits(
                max_keepalive_connections=max_keepalive_connections,
                max_connections=max_connections,
                keepalive_expiry=30.0,
            )
            timeout_config = httpx.Timeout(
                timeout=timeout,
                connect=connect_timeout,
            )

            self._client_sync = httpx.Client(
                limits=limits,
                timeout=timeout_config,
                http2=http2,
                verify=True,
            )
            logger.info(
                f"Created new HTTP sync connection pool: "
                f"max_connections={max_connections}, "
                f"max_keepalive={max_keepalive_connections}"
            )

        return self._client_sync

    def _log_request(self, request: httpx.Request) -> None:
        """请求日志钩子"""
        self._metrics_async.total_requests += 1

    def _log_response(self, response: httpx.Response) -> None:
        """响应日志钩子"""
        self._metrics_async.successful_requests += 1

    def _log_error(self, exc: Exception) -> None:
        """错误日志钩子"""
        self._metrics_async.failed_requests += 1
        if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
            self._metrics_async.total_timeout_errors += 1
        elif isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
            self._metrics_async.total_connection_errors += 1

    @asynccontextmanager
    async def request_context(self, **kwargs):
        """
        请求上下文管理器（带监控）

        使用示例:
            async with pool.request_context() as client:
                response = await client.get(...)
        """
        client = await self.get_async_client()
        start_time = time.time()
        try:
            yield client
        except Exception as e:
            logger.error(f"HTTP request error: {e}")
            raise
        finally:
            # 记录请求时间
            elapsed_ms = (time.time() - start_time) * 1000
            self._metrics_async.request_times.append(elapsed_ms)

    async def close(self) -> None:
        """关闭连接池"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            logger.info("HTTP connection pool closed")

    def close_sync(self) -> None:
        """关闭同步连接池"""
        if self._client_sync is not None and not self._client_sync.is_closed:
            self._client_sync.close()
            self._client_sync = None
            logger.info("HTTP sync connection pool closed")

    @property
    def stats(self) -> dict:
        """获取连接池统计信息"""
        stats = {
            "async_client": None,
            "sync_client": None,
            "health": {
                "is_healthy": self._is_healthy,
                "last_health_check": self._last_health_check,
            },
            "metrics_async": self._metrics_async.to_dict(),
            "metrics_sync": self._metrics_sync.to_dict(),
        }

        if self._client is not None:
            stats["async_client"] = {
                "is_closed": self._client.is_closed,
                "is_http2": self._client.is_http2,
            }

        if self._client_sync is not None:
            stats["sync_client"] = {
                "is_closed": self._client_sync.is_closed,
                "is_http2": self._client_sync.is_http2,
            }

        return stats

    async def health_check(self, test_url: str = None) -> bool:
        """
        连接健康检查

        Args:
            test_url: 测试URL (默认: http://httpbin.org/status/200)

        Returns:
            bool: 连接是否健康
        """
        test_url = test_url or "http://httpbin.org/status/200"

        try:
            client = await self.get_async_client()
            response = await client.get(test_url, timeout=5.0)
            self._is_healthy = response.status_code == 200
            self._last_health_check = time.time()

            if not self._is_healthy:
                logger.warning(f"Health check failed: status={response.status_code}")

            return self._is_healthy
        except Exception as e:
            self._is_healthy = False
            self._last_health_check = time.time()
            logger.error(f"Health check error: {e}")
            return False

    async def request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = None,
        retry_delay: float = None,
        retry_on_timeout: bool = True,
        retry_on_5xx: bool = True,
        **kwargs,
    ) -> httpx.Response:
        """
        带重试机制的HTTP请求

        Args:
            method: HTTP方法 (GET, POST, etc.)
            url: 请求URL
            max_retries: 最大重试次数 (默认: 3)
            retry_delay: 重试延迟秒数 (默认: 0.5)
            retry_on_timeout: 是否在超时时重试
            retry_on_5xx: 是否在5xx错误时重试
            **kwargs: 传递给httpx请求的其他参数

        Returns:
            httpx.Response

        Raises:
            httpx.HTTPError: 所有重试失败后抛出最后一个异常
        """
        max_retries = max_retries or self.DEFAULT_MAX_RETRIES
        retry_delay = retry_delay or self.DEFAULT_RETRY_DELAY
        last_error = None

        client = await self.get_async_client()

        for attempt in range(max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)

                # 检查是否需要重试
                if attempt < max_retries:
                    if retry_on_5xx and 500 <= response.status_code < 600:
                        logger.warning(
                            f"Request failed with {response.status_code}, "
                            f"retrying ({attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(retry_delay * (2**attempt))  # 指数退避
                        continue

                return response

            except (httpx.TimeoutException, asyncio.TimeoutError) as e:
                last_error = e
                self._metrics_async.total_timeout_errors += 1

                if attempt < max_retries and retry_on_timeout:
                    logger.warning(
                        f"Request timed out, retrying ({attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_delay * (2**attempt))
                    continue
                raise

            except httpx.HTTPError as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        f"Request failed: {e}, retrying ({attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_delay * (2**attempt))
                    continue
                raise

        # 不应该到达这里
        raise last_error

    async def get_with_retry(self, url: str, **kwargs) -> httpx.Response:
        """带重试的GET请求"""
        return await self.request_with_retry("GET", url, **kwargs)

    async def post_with_retry(self, url: str, **kwargs) -> httpx.Response:
        """带重试的POST请求"""
        return await self.request_with_retry("POST", url, **kwargs)

    def reset_metrics(self) -> None:
        """重置监控指标"""
        self._metrics_async = PoolMetrics()
        self._metrics_sync = PoolMetrics()
        logger.info("Connection pool metrics reset")


# 便捷函数
async def get_async_client(**kwargs) -> httpx.AsyncClient:
    """获取全局异步HTTP客户端"""
    pool = await HTTPConnectionPool.get_instance()
    return await pool.get_async_client(**kwargs)


def get_sync_client(**kwargs) -> httpx.Client:
    """获取全局同步HTTP客户端"""
    pool = HTTPConnectionPool.get_instance_sync()
    return pool.get_sync_client(**kwargs)


async def close_connection_pool() -> None:
    """关闭全局连接池"""
    if HTTPConnectionPool._instance is not None:
        await HTTPConnectionPool._instance.close()


def close_connection_pool_sync() -> None:
    """关闭全局同步连接池"""
    if HTTPConnectionPool._instance is not None:
        HTTPConnectionPool._instance.close_sync()


async def get_pool_stats() -> dict:
    """获取连接池统计信息"""
    if HTTPConnectionPool._instance is not None:
        return HTTPConnectionPool._instance.stats
    return {}


async def health_check(test_url: str = None) -> bool:
    """执行连接池健康检查"""
    if HTTPConnectionPool._instance is not None:
        return await HTTPConnectionPool._instance.health_check(test_url)
    return False


async def http_get_with_retry(url: str, **kwargs) -> httpx.Response:
    """带重试的GET请求"""
    pool = await HTTPConnectionPool.get_instance()
    return await pool.get_with_retry(url, **kwargs)


async def http_post_with_retry(url: str, **kwargs) -> httpx.Response:
    """带重试的POST请求"""
    pool = await HTTPConnectionPool.get_instance()
    return await pool.post_with_retry(url, **kwargs)


if __name__ == "__main__":
    # 测试代码
    import time

    async def test_connection_pool():
        pool = await HTTPConnectionPool.get_instance()

        # 测试异步客户端
        client = await pool.get_async_client()

        # 发送多个请求测试连接复用
        urls = [
            "https://httpbin.org/get",
            "https://httpbin.org/delay/1",
            "https://httpbin.org/headers",
        ]

        start = time.time()
        for url in urls:
            try:
                response = await client.get(url)
                print(f"Status: {response.status_code}, URL: {url}")
            except Exception as e:
                print(f"Error: {e}, URL: {url}")

        elapsed = time.time() - start
        print(f"Total time: {elapsed:.2f}s")
        print(f"Pool stats: {pool.stats}")

        await pool.close()

    asyncio.run(test_connection_pool())
