"""灵知系统配置模块

提供灵知古籍知识系统的特定配置。
"""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class LingZhiConfig(BaseSettings):
    """灵知系统配置类

    管理灵知古籍知识系统的特定配置。
    """

    # 数据库配置
    GUOXUE_DB_PATH: str = Field(
        default="/opt/lingzhi/database/guoxue.db",
        description="国学数据库路径"
    )
    KXZD_DB_PATH: str = Field(
        default="/opt/lingzhi/database/kxzd.db",
        description="科学指导数据库路径"
    )

    # 缓存配置
    ENABLE_CACHE: bool = Field(
        default=True,
        description="是否启用缓存"
    )
    CACHE_TTL: int = Field(
        default=3600,
        ge=60,
        description="缓存过期时间（秒）"
    )

    # 日志配置
    LOG_LEVEL: str = Field(
        default="INFO",
        description="日志级别"
    )

    # 查询配置
    QUERY_TIMEOUT: float = Field(
        default=30.0,
        ge=1.0,
        description="查询超时时间（秒）"
    )

    # 连接池配置
    MAX_CONNECTIONS: int = Field(
        default=10,
        ge=1,
        le=50,
        description="最大连接数"
    )
    CONNECTION_TIMEOUT: int = Field(
        default=10,
        ge=1,
        le=60,
        description="连接超时时间（秒）"
    )

    # PDF文件配置
    PDF_BASE_PATH: str = Field(
        default="/mnt/openlist/115/国学大师/guji",
        description="PDF文件基础路径"
    )

    # 数据统计
    TOTAL_BOOKS: int = Field(
        default=130000,
        description="总书籍数"
    )
    VERIFIED_BOOKS: int = Field(
        default=55,
        description="已验证书籍数"
    )

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

    def get_database_url(self, db_type: str = "guoxue") -> str:
        """获取数据库URL

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

    def __repr__(self) -> str:
        """配置字符串表示"""
        return (
            f"LingZhiConfig("
            f"GUOXUE_DB={self.GUOXUE_DB_PATH}, "
            f"KXZD_DB={self.KXZD_DB_PATH}, "
            f"CACHE={self.ENABLE_CACHE}, "
            f"TIMEOUT={self.QUERY_TIMEOUT}"
            f")"
        )
