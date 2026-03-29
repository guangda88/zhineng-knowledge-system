"""测试环境配置"""

from ..base import BaseConfig
from ..database import DatabaseConfig
from ..redis import RedisConfig
from ..security import SecurityConfig


class TestingConfig(BaseConfig, DatabaseConfig, RedisConfig, SecurityConfig):
    """测试环境配置"""

    ENVIRONMENT: str = "testing"
    DEBUG: bool = True

    # 测试环境使用WARNING级别日志（减少输出）
    LOG_LEVEL: str = "WARNING"

    # 测试环境允许本地来源
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000"
    ]

    # 测试环境禁用速率限制
    RATE_LIMIT_ENABLED: bool = False

    # 测试环境使用最小的连接池
    DB_POOL_SIZE: int = 2
    REDIS_POOL_SIZE: int = 2

    # 测试环境使用内存数据库
    DATABASE_URL: str = "sqlite:///:memory:"
