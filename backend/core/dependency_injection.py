"""依赖注入容器模块

提供依赖注入容器，管理应用中的依赖关系。
"""

import hmac
from functools import lru_cache
from typing import TypeVar, Type, Optional, Callable, Dict, Any
from fastapi import Depends, Request, HTTPException
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

async def require_admin_api_key(request: Request) -> bool:
    """验证管理端点API密钥

    从 X-Admin-API-Key 头或 admin_api_key 查询参数读取密钥。
    生产环境：未配置 ADMIN_API_KEYS 时默认拒绝访问。
    开发环境：未配置时记录警告并允许访问（向后兼容）。

    Raises:
        HTTPException 401: 密钥缺失或未配置
        HTTPException 403: 密钥无效
    """
    from backend.config import get_config

    config = get_config()
    raw_keys = config.ADMIN_API_KEYS
    valid_keys = [k.strip() for k in raw_keys.split(",") if k.strip()] if raw_keys else []

    if not valid_keys:
        if config.is_production():
            raise HTTPException(
                status_code=401,
                detail="Admin API not configured. Set ADMIN_API_KEYS environment variable."
            )
        logger.warning("ADMIN_API_KEYS not configured - admin endpoints are unprotected")
        return True

    provided = request.headers.get("X-Admin-API-Key") or request.query_params.get("admin_api_key")

    if not provided:
        raise HTTPException(
            status_code=401,
            detail="Admin API key required. Provide X-Admin-API-Key header."
        )

    if not any(hmac.compare_digest(provided, k) for k in valid_keys):
        raise HTTPException(
            status_code=403,
            detail="Invalid admin API key"
        )

    return True


@lru_cache()
def get_config_dependency() -> Config:
    """获取配置实例（FastAPI依赖）

    Returns:
        Config: 配置实例
    """
    return get_config()


def get_db_pool():
    """获取数据库连接池（委托给 backend.core.database）

    Returns:
        asyncpg.Pool 或 None: 数据库连接池
    """
    from backend.core.database import get_db_pool as _get_db_pool
    return _get_db_pool()


async def get_db():
    """获取数据库连接（FastAPI依赖）

    Yields:
        asyncpg.Connection: 数据库连接
    """
    pool = get_db_pool()
    if pool is None:
        from backend.core.database import init_db_pool
        pool = await init_db_pool()
    async with pool.acquire() as connection:
        yield connection


def get_redis_client():
    """获取Redis客户端（委托给 CacheService）

    Returns:
        Redis客户端或None
    """
    try:
        from backend.core.service_manager import get_service_manager
        sm = get_service_manager()
        cache_service = sm.get_service("cache")
        if cache_service and hasattr(cache_service, 'client'):
            return cache_service.client
    except (ImportError, AttributeError, RuntimeError):
        pass
    return None


# ============== 便捷依赖函数 ==============

__all__ = [
    "Container",
    "get_container",
    "get_config_dependency",
    "get_db_pool",
    "get_db",
    "get_redis_client",
    "require_admin_api_key",
]
