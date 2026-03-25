"""请求统计模块"""

from typing import Dict

# 请求统计
request_stats: Dict[str, int] = {"total": 0, "errors": 0}


def get_request_stats() -> Dict[str, int]:
    """获取请求统计"""
    return request_stats


def increment_request_count() -> None:
    """增加请求计数"""
    request_stats["total"] += 1


def increment_error_count() -> None:
    """增加错误计数"""
    request_stats["errors"] += 1
