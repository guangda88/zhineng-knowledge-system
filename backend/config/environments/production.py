"""生产环境配置"""

from ..base import BaseConfig
from ..database import DatabaseConfig
from ..redis import RedisConfig
from ..security import SecurityConfig


class ProductionConfig(BaseConfig, DatabaseConfig, RedisConfig, SecurityConfig):
    """生产环境配置"""

    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    # 生产环境使用INFO级别日志
    LOG_LEVEL: str = "INFO"

    # 生产环境严格的CORS配置
    ALLOWED_ORIGINS: list = []  # 从环境变量读取

    # 生产环境启用速率限制
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000

    # 生产环境使用较大的连接池
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    REDIS_POOL_SIZE: int = 20

    # 生产环境必须配置密钥
    SECRET_KEY: str = ""  # 从环境变量读取
