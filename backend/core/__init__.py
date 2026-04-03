"""核心模块

提供应用核心功能：
- 数据库连接管理
- 中间件配置
- 请求统计
- 生命周期管理
"""

from .database import close_db_pool, get_db_pool, init_db_pool
from .lifespan import lifespan
from .middleware import ConfigError, add_security_headers, get_allowed_origins, log_requests
from .request_stats import get_request_stats, increment_error_count, increment_request_count

__all__ = [
    # Database
    "init_db_pool",
    "close_db_pool",
    "get_db_pool",
    # Middleware
    "get_allowed_origins",
    "add_security_headers",
    "log_requests",
    "ConfigError",
    # Request stats
    "get_request_stats",
    "increment_request_count",
    "increment_error_count",
    # Lifespan
    "lifespan",
]
