"""
检索反馈闭环服务

记录用户对搜索结果的反馈，用于：
1. 评估检索质量
2. 修正缺口判定阈值
3. 优化排序权重
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

_DOC_QUALITY_CACHE_TTL = 300
_DOC_QUALITY_NAMESPACE = "doc_quality"

VALID_FEEDBACK_TYPES = {"helpful", "not_helpful", "wrong", "irrelevant", "partial"}


async def submit_feedback(
    pool: asyncpg.Pool,
    query: str,
    feedback_type: str,
    doc_id: Optional[int] = None,
    rating: Optional[int] = None,
    category: Optional[str] = None,
    search_method: Optional[str] = None,
    rank_position: Optional[int] = None,
    similarity_score: Optional[float] = None,
    comment: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    提交一条检索反馈。

    Args:
        pool: 数据库连接池
        query: 查询文本
        feedback_type: 反馈类型 (helpful/not_helpful/wrong/irrelevant/partial)
        doc_id: 关联文档 ID
        rating: 1-5 星评分
        category: 分类
        search_method: 检索方法
        rank_position: 结果排序位置
        similarity_score: 相似度分数
        comment: 文字反馈
        session_id: 会话 ID
        metadata: 额外元数据

    Returns:
        反馈 ID
    """
    if feedback_type not in VALID_FEEDBACK_TYPES:
        raise ValueError(f"无效反馈类型: {feedback_type}, 有效值: {VALID_FEEDBACK_TYPES}")
    if rating is not None and not (1 <= rating <= 5):
        raise ValueError(f"评分必须在 1-5 之间: {rating}")

    async with pool.acquire() as conn:
        fb_id = await conn.fetchval(
            """
            INSERT INTO search_feedback
                (query, doc_id, feedback_type, rating, category,
                 search_method, rank_position, similarity_score,
                 comment, session_id, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
            """,
            query,
            doc_id,
            feedback_type,
            rating,
            category,
            search_method,
            rank_position,
            similarity_score,
            comment,
            session_id,
            json.dumps(metadata or {}),
        )

    logger.info(f"检索反馈已记录: id={fb_id}, query='{query}', type={feedback_type}")
    return fb_id


async def get_feedback_stats(pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    获取反馈统计概览。

    Returns:
        统计信息
    """
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM search_feedback") or 0
        by_type = await conn.fetch(
            "SELECT feedback_type, COUNT(*) as count FROM search_feedback GROUP BY feedback_type"
        )
        avg_rating = (
            await conn.fetchval(
                "SELECT ROUND(AVG(rating)::numeric, 2) FROM search_feedback WHERE rating IS NOT NULL"
            )
            or 0
        )
        helpful_rate = (
            await conn.fetchval(
                """
            SELECT CASE WHEN COUNT(*) = 0 THEN 0
                ELSE ROUND(100.0 * SUM(CASE WHEN feedback_type = 'helpful' THEN 1 ELSE 0 END) / COUNT(*), 1)
                END
            FROM search_feedback
            """
            )
            or 0.0
        )
        recent_7d = (
            await conn.fetchval(
                "SELECT COUNT(*) FROM search_feedback WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '7 days'"
            )
            or 0
        )

        top_queries = await conn.fetch(
            """
            SELECT query,
                   COUNT(*) as feedback_count,
                   SUM(CASE WHEN feedback_type = 'helpful' THEN 1 ELSE 0 END) as helpful,
                   SUM(CASE WHEN feedback_type != 'helpful' THEN 1 ELSE 0 END) as not_helpful
            FROM search_feedback
            GROUP BY query
            ORDER BY feedback_count DESC
            LIMIT 10
            """,
        )

    return {
        "total": total,
        "by_type": {r["feedback_type"]: r["count"] for r in by_type},
        "avg_rating": float(avg_rating),
        "helpful_rate": float(helpful_rate),
        "recent_7d": recent_7d,
        "top_queries": [dict(r) for r in top_queries],
    }


async def _fetch_quality_from_db(
    pool: asyncpg.Pool, doc_ids: List[int]
) -> Dict[int, Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT doc_id,
                   COUNT(*) as total_feedback,
                   SUM(CASE WHEN feedback_type = 'helpful' THEN 1 ELSE 0 END) as helpful_count,
                   ROUND(AVG(rating)::numeric, 2) as avg_rating
            FROM search_feedback
            WHERE doc_id = ANY($1)
            GROUP BY doc_id
            """,
            doc_ids,
        )

    result = {}
    for r in rows:
        did = r["doc_id"]
        total = r["total_feedback"]
        helpful = r["helpful_count"]
        result[did] = {
            "helpful_count": helpful,
            "total_feedback": total,
            "helpful_ratio": round(helpful / total, 3) if total > 0 else 0,
            "avg_rating": float(r["avg_rating"]) if r["avg_rating"] else None,
        }

    return result


async def get_doc_quality_scores(
    pool: asyncpg.Pool,
    doc_ids: List[int],
) -> Dict[int, Dict[str, Any]]:
    """
    批量获取文档的反馈质量评分（带缓存）。

    Args:
        pool: 数据库连接池
        doc_ids: 文档 ID 列表

    Returns:
        {doc_id: {helpful_count, total_feedback, helpful_ratio, avg_rating}}
    """
    if not doc_ids:
        return {}

    try:
        from backend.cache.manager import get_cache_manager

        cache_mgr = get_cache_manager()
        cache_key = ",".join(str(did) for did in sorted(doc_ids))

        return await cache_mgr.get_or_set(
            cache_key,
            lambda: _fetch_quality_from_db(pool, doc_ids),
            namespace=_DOC_QUALITY_NAMESPACE,
            ttl=_DOC_QUALITY_CACHE_TTL,
        )
    except Exception:
        logger.debug("缓存不可用，直接查询数据库")
        return await _fetch_quality_from_db(pool, doc_ids)


async def list_feedback(
    pool: asyncpg.Pool,
    feedback_type: Optional[str] = None,
    doc_id: Optional[int] = None,
    query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    查询反馈列表。

    Args:
        pool: 数据库连接池
        feedback_type: 反馈类型过滤
        doc_id: 文档 ID 过滤
        query: 查询文本过滤（精确匹配）
        limit: 返回数量
        offset: 偏移量

    Returns:
        反馈列表
    """
    conditions = []
    params: list = []
    idx = 1

    if feedback_type:
        conditions.append(f"feedback_type = ${idx}")
        params.append(feedback_type)
        idx += 1
    if doc_id is not None:
        conditions.append(f"doc_id = ${idx}")
        params.append(doc_id)
        idx += 1
    if query:
        conditions.append(f"query = ${idx}")
        params.append(query)
        idx += 1

    where = ""
    if conditions:
        where = " WHERE " + " AND ".join(conditions)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, query, doc_id, feedback_type, rating, category,
                   search_method, rank_position, similarity_score,
                   comment, session_id, created_at, metadata
            FROM search_feedback
            {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )

    return [dict(r) for r in rows]
