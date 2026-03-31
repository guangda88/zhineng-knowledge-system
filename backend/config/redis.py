"""Redis配置模块

提供Redis缓存配置。
"""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RedisConfig(BaseSettings):
    """Redis配置类

    管理Redis缓存连接配置。
    """

    # Redis连接
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis连接URL"
    )
    REDIS_HOST: str = Field(
        default="localhost",
        description="Redis主机地址"
    )
    REDIS_PORT: int = Field(
        default=6379,
        ge=1,
        le=65535,
        description="Redis端口"
    )
    REDIS_DB: int = Field(
        default=0,
        ge=0,
        le=15,
        description="Redis数据库编号"
    )
    REDIS_PASSWORD: Optional[str] = Field(
        default=None,
        description="Redis密码"
    )

    # 缓存配置
    CACHE_ENABLED: bool = Field(
        default=True,
        description="是否启用缓存"
    )
    CACHE_TTL: int = Field(
        default=3600,
        ge=60,
        description="缓存过期时间（秒）"
    )
    CACHE_MAX_SIZE: int = Field(
        default=10000,
        ge=100,
        description="缓存最大条目数"
    )

    # 连接池配置
    REDIS_POOL_SIZE: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Redis连接池大小"
    )
    REDIS_SOCKET_TIMEOUT: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Redis连接超时（秒）"
    )
    REDIS_SOCKET_CONNECT_TIMEOUT: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Redis连接超时（秒）"
    )

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}

    def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    def __repr__(self) -> str:
        """配置字符串表示"""
        return (
            f"RedisConfig("
            f"HOST={self.REDIS_HOST}, "
            f"PORT={self.REDIS_PORT}, "
            f"DB={self.REDIS_DB}, "
            f"CACHE_ENABLED={self.CACHE_ENABLED}, "
            f"CACHE_TTL={self.CACHE_TTL}"
            f")"
        )
