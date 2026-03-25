"""配置管理模块

安全配置管理：
- 所有敏感配置必须通过环境变量设置
- 不提供硬编码的默认值防止错误配置
"""

from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """配置错误"""
    pass


# 环境配置
class Config:
    """应用配置

    所有敏感配置都需要通过环境变量设置，不提供默认值。
    """

    # 数据库 - 必须设置
    @staticmethod
    def _get_database_url() -> str:
        """获取数据库URL，必须设置"""
        url = os.getenv("DATABASE_URL")
        if not url:
            raise ConfigError(
                "DATABASE_URL environment variable is required. "
                "Example: postgresql://user:password@host:port/database"
            )
        return url

    DATABASE_URL: str = _get_database_url.__func__()

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # 日志
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # 检索
    MAX_RESULTS: int = 10
    SIMILARITY_THRESHOLD: float = 0.7

    # BGE 嵌入
    BGE_API_URL: Optional[str] = os.getenv("BGE_API_URL")
    EMBEDDING_DIM: int = 1024

    # DeepSeek - 可选配置
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_API_URL: Optional[str] = os.getenv("DEEPSEEK_API_URL")

    # CORS安全配置
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000")

    # 分类
    VALID_CATEGORIES = ["气功", "中医", "儒家"]

    @classmethod
    def validate(cls) -> None:
        """验证必需的配置项"""
        if not cls.DATABASE_URL:
            raise ConfigError("DATABASE_URL is required")

    class Config:
        validate_assignment = True


# 全局配置实例
try:
    config = Config()
    Config.validate()
except ConfigError as e:
    logger.error(f"Configuration error: {e}")
    raise
