"""数据库配置模块

提供数据库连接配置，包括PostgreSQL配置。
"""

import logging
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseSettings):
    """数据库配置类

    管理PostgreSQL和SQLite数据库的连接配置。
    """

    # PostgreSQL主数据库
    DATABASE_URL: Optional[str] = Field(default=None, description="PostgreSQL数据库连接URL")

    # 连接池配置
    DB_POOL_SIZE: int = Field(default=10, ge=1, le=50, description="数据库连接池大小")
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0, le=50, description="连接池最大溢出数")
    DB_POOL_TIMEOUT: int = Field(default=30, ge=1, le=120, description="连接池获取超时时间（秒）")
    DB_POOL_RECYCLE: int = Field(default=3600, ge=60, description="连接池回收时间（秒）")
    DB_MAX_CONNECTIONS: int = Field(default=10, ge=1, le=50, description="最大连接数")

    # 查询配置
    QUERY_TIMEOUT: float = Field(default=30.0, ge=1.0, le=300.0, description="查询超时时间（秒）")

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v):
        """验证数据库URL"""
        if not v:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Example: postgresql://user:password@host:port/database"
            )
        return v

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}

    def __repr__(self) -> str:
        """配置字符串表示"""
        return (
            f"DatabaseConfig("
            f"POOL_SIZE={self.DB_POOL_SIZE}, "
            f"MAX_OVERFLOW={self.DB_MAX_OVERFLOW}, "
            f"TIMEOUT={self.DB_POOL_TIMEOUT}, "
            f"QUERY_TIMEOUT={self.QUERY_TIMEOUT}"
            f")"
        )
