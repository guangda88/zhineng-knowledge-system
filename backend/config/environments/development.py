"""开发环境配置"""

from ..base import BaseConfig
from ..database import DatabaseConfig
from ..redis import RedisConfig
from ..security import SecurityConfig


class DevelopmentConfig(BaseConfig, DatabaseConfig, RedisConfig, SecurityConfig):
    """开发环境配置"""

    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # 开发环境使用更详细的日志
    LOG_LEVEL: str = "DEBUG"

    # 开发环境允许所有来源
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8001"
    ]

    # 开发环境禁用速率限制
    RATE_LIMIT_ENABLED: bool = False

    # 开发环境使用较小的连接池
    DB_POOL_SIZE: int = 5
    REDIS_POOL_SIZE: int = 5
