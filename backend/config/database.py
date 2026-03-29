"""数据库配置模块

提供数据库连接配置，包括PostgreSQL和SQLite配置。
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseSettings):
    """数据库配置类

    管理PostgreSQL和SQLite数据库的连接配置。
    """

    # PostgreSQL主数据库
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="PostgreSQL数据库连接URL"
    )

    # SQLite数据库（灵知系统）
    GUOXUE_DB_PATH: str = Field(
        default="/opt/lingzhi/database/guoxue.db",
        description="国学数据库路径"
    )
    KXZD_DB_PATH: str = Field(
        default="/opt/lingzhi/database/kxzd.db",
        description="科学指导数据库路径"
    )

    # 连接池配置
    DB_POOL_SIZE: int = Field(
        default=10,
        ge=1,
        le=50,
        description="数据库连接池大小"
    )
    DB_MAX_OVERFLOW: int = Field(
        default=20,
        ge=0,
        le=50,
        description="连接池最大溢出数"
    )
    DB_POOL_TIMEOUT: int = Field(
        default=30,
        ge=1,
        le=120,
        description="连接池获取超时时间（秒）"
    )
    DB_POOL_RECYCLE: int = Field(
        default=3600,
        ge=60,
        description="连接池回收时间（秒）"
    )
    DB_MAX_CONNECTIONS: int = Field(
        default=10,
        ge=1,
        le=50,
        description="最大连接数"
    )

    # 查询配置
    QUERY_TIMEOUT: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="查询超时时间（秒）"
    )

    @field_validator('DATABASE_URL', mode='before')
    @classmethod
    def validate_database_url(cls, v):
        """验证数据库URL"""
        if not v:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Example: postgresql://user:password@host:port/database"
            )
        return v

    @field_validator('GUOXUE_DB_PATH')
    @classmethod
    def validate_guoxue_path(cls, v):
        """验证国学数据库路径"""
        path = Path(v)
        if not path.exists():
            logger.warning(f"Guoxue database not found at {v}")
        return v

    @field_validator('KXZD_DB_PATH')
    @classmethod
    def validate_kxzd_path(cls, v):
        """验证科学指导数据库路径"""
        path = Path(v)
        if not path.exists():
            logger.warning(f"KXZD database not found at {v}")
        return v

    def get_sqlite_url(self, db_type: str = "guoxue") -> str:
        """获取SQLite数据库URL

        Args:
            db_type: 数据库类型，guoxue或kxzd

        Returns:
            SQLite数据库URL
        """
        if db_type == "guoxue":
            return f"sqlite:///{self.GUOXUE_DB_PATH}"
        elif db_type == "kxzd":
            return f"sqlite:///{self.KXZD_DB_PATH}"
        else:
            raise ValueError(f"Unknown database type: {db_type}")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

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
