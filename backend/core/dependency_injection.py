"""依赖注入容器模块

提供依赖注入容器，管理应用中的依赖关系。
"""

from functools import lru_cache
from typing import TypeVar, Type, Optional, Callable, Dict, Any
import asyncpg
from fastapi import Depends
import logging

from backend.config import get_config, Config

logger = logging.getLogger(__name__)

T = TypeVar('T')


class Container:
    """依赖注入容器

    管理应用中的服务实例和依赖关系。
    """

    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable] = {}
        self._singletons: Dict[Type, Any] = {}
        self.logger = logging.getLogger("Container")

    def register_singleton(self, interface: Type[T], implementation: T) -> None:
        """注册单例服务

        Args:
            interface: 服务接口类型
            implementation: 服务实现实例
        """
        self._singletons[interface] = implementation
        self.logger.debug(f"Registered singleton: {interface.__name__}")

    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """注册工厂函数

        Args:
            interface: 服务接口类型
            factory: 服务工厂函数
        """
        self._factories[interface] = factory
        self.logger.debug(f"Registered factory: {interface.__name__}")

    def register_transient(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """注册瞬态服务（每次创建新实例）

        Args:
            interface: 服务接口类型
            factory: 服务工厂函数
        """
        self._factories[interface] = factory
        self.logger.debug(f"Registered transient: {interface.__name__}")

    def get(self, interface: Type[T]) -> T:
        """获取服务实例

        Args:
            interface: 服务接口类型

        Returns:
            服务实例

        Raises:
            ValueError: 服务未注册
        """
        # 检查单例
        if interface in self._singletons:
            return self._singletons[interface]

        # 检查工厂
        if interface in self._factories:
            return self._factories[interface]()

        raise ValueError(f"Service {interface.__name__} not registered")

    def has(self, interface: Type[T]) -> bool:
        """检查服务是否已注册

        Args:
            interface: 服务接口类型

        Returns:
            是否已注册
        """
        return interface in self._singletons or interface in self._factories

    def clear(self):
        """清空所有注册的服务"""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        self.logger.debug("Container cleared")


# 全局容器实例
_container: Optional[Container] = None


def get_container() -> Container:
    """获取容器实例（单例模式）

    Returns:
        Container: 容器实例
    """
    global _container
    if _container is None:
        _container = Container()
        _initialize_container(_container)
    return _container


def _initialize_container(container: Container):
    """初始化容器，注册核心服务

    Args:
        container: 容器实例
    """
    # 注册配置服务
    container.register_singleton(Config, get_config())

    logger.info("Dependency injection container initialized")


# ============== FastAPI 依赖函数 ==============

@lru_cache()
def get_config_dependency() -> Config:
    """获取配置实例（FastAPI依赖）

    Returns:
        Config: 配置实例
    """
    return get_config()


# 数据库连接池（全局缓存）
_db_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """获取数据库连接池（FastAPI依赖）

    Returns:
        asyncpg.Pool: 数据库连接池
    """
    global _db_pool

    if _db_pool is None:
        config = get_config()

        try:
            _db_pool = await asyncpg.create_pool(
                config.DATABASE_URL,
                min_size=2,
                max_size=config.DB_POOL_SIZE,
                command_timeout=config.DB_POOL_TIMEOUT,
                max_inactive_connection_lifetime=config.DB_POOL_RECYCLE
            )
            logger.info("Database connection pool created")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise

    return _db_pool


async def close_db_pool():
    """关闭数据库连接池"""
    global _db_pool

    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("Database connection pool closed")


def get_db():
    """获取数据库连接（FastAPI依赖）

    这是一个依赖函数，用于在API路由中获取数据库连接。

    Returns:
        数据库连接获取函数
    """
    async def _get_db():
        pool = await get_db_pool()
        async with pool.acquire() as connection:
            yield connection

    return _get_db


# ============== Redis 依赖 ==============

_redis_client = None


async def get_redis_client():
    """获取Redis客户端（FastAPI依赖）

    Returns:
        Redis客户端
    """
    global _redis_client

    if _redis_client is None:
        config = get_config()

        try:
            import redis.asyncio as redis
            _redis_client = await redis.from_url(
                config.get_redis_url(),
                encoding="utf-8",
                decode_responses=True,
                max_connections=config.REDIS_POOL_SIZE
            )
            logger.info("Redis client created")
        except Exception as e:
            logger.error(f"Failed to create Redis client: {e}")
            raise

    return _redis_client


async def close_redis_client():
    """关闭Redis客户端"""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")


# ============== 便捷依赖函数 ==============

def inject_config():
    """注入配置依赖（FastAPI使用）

    Example:
        @router.get("/test")
        async def test(config: Config = Depends(inject_config)):
            return {"environment": config.ENVIRONMENT}
    """
    return Depends(get_config_dependency)


def inject_db():
    """注入数据库连接依赖（FastAPI使用）

    Example:
        @router.get("/users")
        async def get_users(db = Depends(inject_db())):
            result = await db.fetch("SELECT * FROM users")
            return result
    """
    return Depends(get_db())


__all__ = [
    "Container",
    "get_container",
    "get_config_dependency",
    "get_db_pool",
    "close_db_pool",
    "get_db",
    "get_redis_client",
    "close_redis_client",
    "inject_config",
    "inject_db",
]
