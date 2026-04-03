"""统一配置管理模块

提供统一的配置管理入口，整合所有配置模块。

Import direction: config is a LEAF module. It must NOT import from:
  - backend.core.* (especially core.database, core.service_manager, core.dependency_injection)
  - backend.services.*
  - backend.api.*
Other modules may freely import from config.
"""

import logging
import threading
import warnings
from typing import Optional

from .base import BaseConfig
from .database import DatabaseConfig
from .lingzhi import LingZhiConfig
from .redis import RedisConfig
from .security import SecurityConfig

logger = logging.getLogger(__name__)


class Config(BaseConfig, DatabaseConfig, RedisConfig, SecurityConfig, LingZhiConfig):
    """统一配置类

    整合所有配置模块，提供统一的配置访问接口。
    """

    def __init__(self, **kwargs):
        """初始化配置"""
        super().__init__(**kwargs)
        self._validate_config()

    def _validate_config(self):
        """验证配置"""
        # 验证必需的环境变量
        if self.ENVIRONMENT == "production":
            if not self.DATABASE_URL:
                raise ValueError("DATABASE_URL is required in production")
            if not self.SECRET_KEY:
                logger.warning("SECRET_KEY not set in production")

        logger.info(f"Configuration loaded for environment: {self.ENVIRONMENT}")

    def get_database_url(self) -> str:
        """获取主数据库URL"""
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL is not configured")
        return self.DATABASE_URL

    def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        return self.REDIS_URL

    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.ENVIRONMENT == "development"

    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.ENVIRONMENT == "production"

    def is_testing(self) -> bool:
        """是否为测试环境"""
        return self.ENVIRONMENT == "testing"

    def __repr__(self) -> str:
        """配置字符串表示"""
        return (
            f"Config("
            f"ENV={self.ENVIRONMENT}, "
            f"API={self.API_HOST}:{self.API_PORT}, "
            f"DB_POOL={self.DB_POOL_SIZE}, "
            f"CACHE={self.CACHE_ENABLED}"
            f")"
        )


# 全局配置实例
_config: Optional[Config] = None
_config_lock = threading.Lock()


def get_config() -> Config:
    """获取配置实例（单例模式，线程安全）

    Returns:
        Config: 配置实例
    """
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                _config = Config()
    return _config


async def reload_config() -> Config:
    """重新加载配置

    清除当前配置实例并重新创建新的配置实例。
    这会重新读取环境变量和配置文件。

    Returns:
        Config: 新的配置实例
    """
    global _config
    with _config_lock:
        logger.info("Reloading configuration...")

        # 清除旧配置
        old_config = _config
        _config = None

        try:
            # 创建新配置
            new_config = Config()
            _config = new_config

            logger.info("Configuration reloaded successfully")
            return new_config

        except Exception as e:
            # 如果重新加载失败，恢复旧配置
            _config = old_config
            logger.error(f"Failed to reload configuration: {e}")
            raise


# 向后兼容：保留旧的config变量
config = get_config()


# 废弃警告
def __getattr__(name: str):
    """处理废弃的配置访问"""
    if name in ("Config",):
        warnings.warn(
            "Direct import of Config from backend.config is deprecated. "
            "Use get_config() or config instance instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return Config
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "Config",
    "get_config",
    "config",
    "BaseConfig",
    "DatabaseConfig",
    "RedisConfig",
    "SecurityConfig",
    "LingZhiConfig",
]
