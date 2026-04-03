"""
具体服务实现

提供常用的服务实现，如数据库服务、缓存服务等
"""

import asyncio
import logging
import re
from typing import Any, Dict, Optional

import asyncpg

from backend.core.database import close_db_pool, init_db_pool
from backend.core.service_manager import Service, ServiceHealth, ServiceStatus

logger = logging.getLogger(__name__)


def _sanitize_url(url: str) -> str:
    """Remove password from URL for safe logging."""
    return re.sub(r"(:\/\/[^:]+:)([^@]+)(@)", r"\1***\3", url)


class DatabaseService(Service):
    """
    数据库服务

    管理数据库连接池的生命周期
    """

    def __init__(self, name: str = "database", dependencies: Optional[list] = None):
        super().__init__(name, dependencies)
        self._pool: Optional[asyncpg.Pool] = None
        self._config: Optional[Dict[str, Any]] = None

    async def start(self) -> None:
        """启动数据库服务"""
        try:
            logger.info("Initializing database connection pool...")
            self._pool = await init_db_pool()

            # 测试连接
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            logger.info("Database connection pool initialized successfully")
            self._health = ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.RUNNING,
                healthy=True,
                message="Database service running",
                metadata={
                    "pool_size": self._pool.get_size(),
                    "max_connections": self._pool.get_max_size(),
                },
            )

        except Exception as e:
            logger.error(f"Failed to initialize database service: {e}")
            self._health = ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.ERROR,
                healthy=False,
                message=f"Database initialization failed: {e}",
            )
            raise

    async def stop(self) -> None:
        """停止数据库服务"""
        if self._pool:
            logger.info("Closing database connection pool...")
            await close_db_pool()
            self._pool = None
            logger.info("Database connection pool closed")

    async def health_check(self) -> ServiceHealth:
        """数据库健康检查"""
        try:
            if not self._pool:
                return ServiceHealth(
                    service_name=self.name,
                    status=self.status,
                    healthy=False,
                    message="Database pool not initialized",
                )

            # 测试连接
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            metadata = {
                "pool_size": self._pool.get_size(),
                "max_connections": self._pool.get_max_size(),
                "available_connections": self._pool.get_max_size() - self._pool.get_size(),
            }

            return ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.RUNNING,
                healthy=True,
                message="Database connection healthy",
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.ERROR,
                healthy=False,
                message=f"Health check failed: {e}",
            )

    @property
    def pool(self) -> Optional[asyncpg.Pool]:
        """获取数据库连接池"""
        return self._pool


class CacheService(Service):
    """
    缓存服务

    管理Redis连接的生命周期
    """

    def __init__(self, name: str = "cache", dependencies: Optional[list] = None):
        super().__init__(name, dependencies)
        self._redis_client: Optional[Any] = None
        self._connected = False

    async def start(self) -> None:
        """启动缓存服务"""
        try:
            from redis.asyncio import Redis

            from backend.config import get_config

            config = get_config()
            redis_url = config.get_redis_url()

            sanitized = _sanitize_url(redis_url)
            logger.info(f"Connecting to Redis: {sanitized}")
            self._redis_client = Redis.from_url(redis_url, decode_responses=True)

            # 测试连接
            await self._redis_client.ping()
            self._connected = True

            logger.info("Cache service initialized successfully")
            self._health = ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.RUNNING,
                healthy=True,
                message="Cache service running",
                metadata={"redis_url": sanitized},
            )

        except Exception as e:
            logger.error(f"Failed to initialize cache service: {e}")
            self._health = ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.ERROR,
                healthy=False,
                message=f"Cache initialization failed: {e}",
            )
            # Cache is not critical, so we don't raise the exception
            logger.warning("Cache service is not available, continuing without cache")

    async def stop(self) -> None:
        """停止缓存服务"""
        if self._redis_client and self._connected:
            logger.info("Closing Redis connection...")
            await self._redis_client.close()
            self._connected = False
            logger.info("Redis connection closed")

    async def health_check(self) -> ServiceHealth:
        """缓存健康检查"""
        try:
            if not self._redis_client or not self._connected:
                return ServiceHealth(
                    service_name=self.name,
                    status=self.status,
                    healthy=False,
                    message="Cache not initialized",
                )

            # 测试连接
            await self._redis_client.ping()

            return ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.RUNNING,
                healthy=True,
                message="Cache connection healthy",
                metadata={"connected": True},
            )

        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.ERROR,
                healthy=False,
                message=f"Health check failed: {e}",
            )

    @property
    def client(self) -> Optional[Any]:
        """获取Redis客户端"""
        return self._redis_client


class VectorService(Service):
    """
    向量搜索服务

    管理向量检索器的生命周期
    """

    def __init__(self, name: str = "vector", dependencies: Optional[list] = None):
        dependencies = dependencies or ["database"]
        super().__init__(name, dependencies)
        self._retriever: Optional[Any] = None

    async def start(self) -> None:
        """启动向量服务"""
        try:
            from backend.core.database import init_db_pool
            from backend.services.retrieval import HybridRetriever

            logger.info("Initializing vector retriever...")
            pool = await init_db_pool()
            self._retriever = HybridRetriever(pool)
            await self._retriever.initialize()

            logger.info("Vector service initialized successfully")
            self._health = ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.RUNNING,
                healthy=True,
                message="Vector service running",
                metadata={"retriever_type": "HybridRetriever"},
            )

        except Exception as e:
            logger.error(f"Failed to initialize vector service: {e}")
            self._health = ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.ERROR,
                healthy=False,
                message=f"Vector initialization failed: {e}",
            )
            # Vector service is not critical for basic functionality
            logger.warning("Vector service is not available, some features may be limited")

    async def stop(self) -> None:
        """停止向量服务"""
        if self._retriever:
            logger.info("Stopping vector retriever...")
            self._retriever = None
            logger.info("Vector retriever stopped")

    async def health_check(self) -> ServiceHealth:
        """向量服务健康检查"""
        try:
            if not self._retriever:
                return ServiceHealth(
                    service_name=self.name,
                    status=self.status,
                    healthy=False,
                    message="Vector retriever not initialized",
                )

            # 基本检查 - 确保检索器存在
            return ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.RUNNING,
                healthy=True,
                message="Vector service healthy",
                metadata={"retriever_type": "HybridRetriever"},
            )

        except Exception as e:
            logger.error(f"Vector service health check failed: {e}")
            return ServiceHealth(
                service_name=self.name,
                status=ServiceStatus.ERROR,
                healthy=False,
                message=f"Health check failed: {e}",
            )

    @property
    def retriever(self) -> Optional[Any]:
        """获取向量检索器"""
        return self._retriever


class MonitoringService(Service):
    """
    监控服务

    提供系统监控和指标收集
    """

    def __init__(self, name: str = "monitoring", dependencies: Optional[list] = None):
        super().__init__(name, dependencies)
        self._metrics: Dict[str, Any] = {}
        self._start_time: Optional[float] = None

    async def start(self) -> None:
        """启动监控服务"""
        import time

        self._start_time = time.time()
        logger.info("Monitoring service started")
        self._health = ServiceHealth(
            service_name=self.name,
            status=ServiceStatus.RUNNING,
            healthy=True,
            message="Monitoring service running",
        )

    async def stop(self) -> None:
        """停止监控服务"""
        logger.info("Monitoring service stopped")
        self._start_time = None

    async def record_metric(self, name: str, value: Any) -> None:
        """记录指标"""
        self._metrics[name] = {"value": value, "timestamp": asyncio.get_running_loop().time()}

    async def get_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        return self._metrics.copy()

    async def get_uptime(self) -> float:
        """获取运行时间（秒）"""
        if self._start_time is None:
            return 0.0
        import time

        return time.time() - self._start_time
