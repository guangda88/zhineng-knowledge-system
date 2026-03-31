"""数据库查询辅助函数模块

提供常用的数据库查询辅助函数，减少代码重复。
"""

import asyncio
import logging
import re
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

import asyncpg
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# 允许在分页查询中使用的SQL关键字白名单
_ALLOWED_QUERY_KEYWORDS: Set[str] = {
    "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "LIKE",
    "ILIKE", "IS", "NULL", "AS", "ON", "JOIN", "LEFT", "RIGHT",
    "INNER", "OUTER", "CROSS", "GROUP", "BY", "HAVING", "ORDER",
    "ASC", "DESC", "DISTINCT", "BETWEEN", "EXISTS", "CASE", "WHEN",
    "THEN", "ELSE", "END", "WITH", "UNION", "ALL", "ANY",
    "TRUE", "FALSE",
}

# 允许在字段名中使用的字符模式
_SAFE_FIELD_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


async def require_pool(
    pool_getter: Callable[[], Any],
) -> Any:
    """确保数据库连接池可用

    Args:
        pool_getter: 获取连接池的函数

    Returns:
        数据库连接池
    """
    return await pool_getter()


def row_to_dict(row: asyncpg.Record) -> Dict[str, Any]:
    """将数据库记录行转换为字典

    Args:
        row: asyncpg记录行

    Returns:
        字典形式的记录
    """
    return dict(row)


def rows_to_list(rows: List[asyncpg.Record]) -> List[Dict[str, Any]]:
    """将多行数据库记录转换为字典列表

    Args:
        rows: asyncpg记录列表

    Returns:
        字典列表
    """
    return [dict(row) for row in rows]


async def fetch_one_or_404(
    pool: asyncpg.Pool,
    query: str,
    *args: Any,
    error_message: str = "资源不存在",
) -> Dict[str, Any]:
    """查询单条记录，不存在则返回404错误

    Args:
        pool: 数据库连接池
        query: SQL查询语句
        *args: 查询参数
        error_message: 404错误消息

    Returns:
        记录字典

    Raises:
        HTTPException: 404当记录不存在时
    """
    row = await pool.fetchrow(query, *args)
    if not row:
        raise HTTPException(status_code=404, detail=error_message)
    return dict(row)


def _validate_paginated_query(query: str) -> None:
    """验证分页查询的安全性，防止SQL注入

    Args:
        query: SQL查询语句

    Raises:
        ValueError: 查询包含不安全内容
    """
    query_upper = query.upper().strip()
    if not query_upper.startswith("SELECT"):
        raise ValueError("分页查询必须以SELECT开头")
    dangerous = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
                 "TRUNCATE", "EXECUTE", "GRANT", "REVOKE"}
    tokens = re.findall(r'[a-zA-Z_]+', query_upper)
    for token in tokens:
        if token in dangerous:
            raise ValueError(f"分页查询不允许包含 {token} 操作")


async def fetch_paginated(
    pool: asyncpg.Pool,
    query: str,
    *args: Any,
    limit: int = 10,
    offset: int = 0,
) -> Dict[str, Any]:
    """分页查询数据

    Args:
        pool: 数据库连接池
        query: SQL查询语句（不含LIMIT/OFFSET，必须为SELECT查询）
        *args: 查询参数
        limit: 每页数量
        offset: 偏移量

    Returns:
        包含total和results的字典

    Raises:
        ValueError: 查询未通过安全验证
    """
    _validate_paginated_query(query)

    # 首先获取总数
    count_query = f"SELECT COUNT(*) FROM ({query}) AS subq"
    total = await pool.fetchval(count_query, *args)

    # 获取分页数据
    paginated_query = f"{query} ORDER BY id LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}"
    rows = await pool.fetch(paginated_query, *args, limit, offset)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": rows_to_list(rows),
    }


async def search_documents(
    pool: asyncpg.Pool,
    search_term: str,
    category: Optional[str] = None,
    limit: int = 10,
    fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """搜索文档（模糊匹配）

    Args:
        pool: 数据库连接池
        search_term: 搜索关键词
        category: 分类筛选
        limit: 返回数量
        fields: 要搜索的字段列表，默认为title和content

    Returns:
        文档列表
    """
    if fields is None:
        fields = ["title", "content"]

    for field in fields:
        if not _SAFE_FIELD_PATTERN.match(field):
            raise ValueError(f"非法字段名: {field}")

    search_term_escaped = search_term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    search_pattern = f"%{search_term_escaped}%"

    if category:
        field_conditions = " OR ".join([f"{field} ILIKE $2" for field in fields])
        query = f"""
            SELECT id, title, content, category
            FROM documents
            WHERE category = $1 AND ({field_conditions})
            ORDER BY id LIMIT $3
        """
        rows = await pool.fetch(query, category, search_pattern, limit)
    else:
        field_conditions = " OR ".join([f"{field} ILIKE $1" for field in fields])
        query = f"""
            SELECT id, title, content, category
            FROM documents
            WHERE {field_conditions}
            ORDER BY id LIMIT $2
        """
        rows = await pool.fetch(query, search_pattern, limit)

    return rows_to_list(rows)


async def get_document_stats(
    pool: asyncpg.Pool,
) -> Dict[str, Any]:
    """获取文档统计信息

    Args:
        pool: 数据库连接池

    Returns:
        统计信息字典
    """
    doc_count, category_stats = await asyncio.gather(
        pool.fetchval("SELECT COUNT(*) FROM documents"),
        pool.fetch(
            """SELECT category, COUNT(*) as count
               FROM documents GROUP BY category"""
        ),
    )

    return {
        "document_count": doc_count,
        "category_stats": rows_to_list(category_stats),
    }


async def check_database_health(pool: asyncpg.Pool) -> Dict[str, Any]:
    """检查数据库健康状态

    Args:
        pool: 数据库连接池

    Returns:
        健康状态信息
    """
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {
            "status": "ok",
            "database": "ok",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("数据库健康检查失败", exc_info=True)
        return {
            "status": "degraded",
            "database": "unavailable",
            "timestamp": datetime.now().isoformat(),
        }
