"""通用工具模块

提供数据库辅助函数和单例模式工具。
"""

from .db_helpers import (
    check_database_health,
    fetch_one_or_404,
    fetch_paginated,
    get_document_stats,
    require_pool,
    row_to_dict,
    rows_to_list,
    search_documents,
)
from .singleton import async_singleton

__all__ = [
    # Database helpers
    "require_pool",
    "row_to_dict",
    "rows_to_list",
    "fetch_one_or_404",
    "fetch_paginated",
    "search_documents",
    "get_document_stats",
    "check_database_health",
    # Singleton utilities
    "async_singleton",
]
