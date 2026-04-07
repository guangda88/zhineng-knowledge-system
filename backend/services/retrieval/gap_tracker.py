"""
知识缺口感知服务

记录低置信度/零命中的用户查询，作为知识闭环（第一个反射弧）的数据源头。

流程：用户查询 → 检索结果 → 判定是否为缺口 → 记录/聚合 → 暴露给灵克/灵通问道消费
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

GAP_THRESHOLD_SCORE = 0.3
GAP_THRESHOLD_COUNT = 2
SIMILAR_QUERY_WINDOW_DAYS = 7


async def record_gap(
    pool: asyncpg.Pool,
    query: str,
    category: Optional[str],
    result_count: int,
    best_score: Optional[float],
    source: str = "hybrid",
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """
    记录一次潜在的知识缺口。

    如果相似查询已存在，则累加 hit_count 并更新 last_seen；
    否则新建一条记录。

    Args:
        pool: 数据库连接池
        query: 用户原始查询
        category: 分类（可选）
        result_count: 检索结果数
        best_score: 最佳相似度分数
        source: 检索来源（hybrid/vector/bm25/ask）
        metadata: 额外元数据

    Returns:
        记录 ID
    """
    is_gap = result_count == 0 or (best_score is not None and best_score < GAP_THRESHOLD_SCORE)

    if not is_gap:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, hit_count FROM knowledge_gaps
                WHERE query = $1
                  AND (category = $2 OR (category IS NULL AND $2 IS NULL))
                  AND status = 'open'
                  AND last_seen > CURRENT_TIMESTAMP - INTERVAL '%s days'
                ORDER BY last_seen DESC
                LIMIT 1
                """
                % SIMILAR_QUERY_WINDOW_DAYS,
                query,
                category,
            )

            if row:
                await conn.execute(
                    """
                    UPDATE knowledge_gaps
                    SET hit_count = hit_count + 1,
                        last_seen = CURRENT_TIMESTAMP,
                        best_score = CASE
                            WHEN $1 IS NOT NULL AND (best_score IS NULL OR $1 > best_score)
                            THEN $1 ELSE best_score
                        END,
                        metadata = metadata || $2::jsonb
                    WHERE id = $3
                    """,
                    best_score,
                    (
                        json.dumps({"last_source": source, **(metadata or {})})
                        if metadata
                        else json.dumps({"last_source": source})
                    ),
                    row["id"],
                )
                logger.debug(f"知识缺口聚合: query='{query}', hit_count={row['hit_count'] + 1}")

                new_count = row["hit_count"] + 1
                if new_count == GAP_THRESHOLD_COUNT + 1:
                    await _alert_gap_threshold(query, new_count, category)

                return row["id"]
            else:
                gap_id = await conn.fetchval(
                    """
                    INSERT INTO knowledge_gaps (query, category, result_count, best_score, source, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    query,
                    category,
                    result_count,
                    best_score,
                    source,
                    json.dumps(metadata or {}),
                )
                logger.info(
                    f"新知识缺口: query='{query}', results={result_count}, score={best_score}"
                )
                return gap_id

    except Exception as e:
        logger.error(f"记录知识缺口失败: {e}", exc_info=True)
        return None


async def record_search_outcome(
    pool: asyncpg.Pool,
    query: str,
    results: List[Dict[str, Any]],
    category: Optional[str] = None,
    source: str = "hybrid",
) -> Optional[int]:
    """
    检索后自动调用：根据结果判定是否为缺口并记录。

    Args:
        pool: 数据库连接池
        query: 查询文本
        results: 检索结果列表
        category: 分类
        source: 检索来源

    Returns:
        缺口记录 ID（如果不是缺口则返回 None）
    """
    result_count = len(results)
    best_score = None
    if results:
        scores = [
            r.get("similarity", r.get("score", 0))
            for r in results
            if r.get("similarity") is not None or r.get("score") is not None
        ]
        if scores:
            best_score = max(scores)

    return await record_gap(pool, query, category, result_count, best_score, source)


async def get_gaps(
    pool: asyncpg.Pool,
    status: str = "open",
    category: Optional[str] = None,
    min_hits: int = 1,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    查询知识缺口列表。

    Args:
        pool: 数据库连接池
        status: 缺口状态过滤
        category: 分类过滤
        min_hits: 最小命中次数（过滤低频查询）
        limit: 返回数量
        offset: 偏移量

    Returns:
        缺口列表
    """
    conditions = ["status = $1", "hit_count >= $2"]
    params: list = [status, min_hits]
    idx = 3

    if category:
        conditions.append(f"category = ${idx}")
        params.append(category)
        idx += 1

    where = " AND ".join(conditions)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, query, category, result_count, best_score,
                   source, status, hit_count, first_seen, last_seen,
                   metadata, resolved_by
            FROM knowledge_gaps
            WHERE {where}
            ORDER BY hit_count DESC, last_seen DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )

    return [dict(r) for r in rows]


async def get_gaps_stats(pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    获取知识缺口统计。

    Returns:
        统计信息
    """
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM knowledge_gaps") or 0
        by_status = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM knowledge_gaps GROUP BY status"
        )
        top_unresolved = await conn.fetch(
            """
            SELECT query, category, hit_count, best_score, last_seen
            FROM knowledge_gaps
            WHERE status = 'open'
            ORDER BY hit_count DESC
            LIMIT 10
            """,
        )
        recent = (
            await conn.fetchval(
                """
            SELECT COUNT(*) FROM knowledge_gaps
            WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
            """
            )
            or 0
        )

    return {
        "total": total,
        "by_status": {r["status"]: r["count"] for r in by_status},
        "recent_7d": recent,
        "top_unresolved": [dict(r) for r in top_unresolved],
    }


async def _alert_gap_threshold(
    query: str, hit_count: int, category: Optional[str]
) -> None:
    """当知识缺口命中次数超过阈值时，通过灵信服务发送告警。"""
    try:
        from backend.services.lingmessage.service import LingMessageService

        svc = LingMessageService()
        cat_info = f" (分类: {category})" if category else ""
        topic = f"知识缺口告警: {query}{cat_info}"

        thread = await svc.create_thread(
            topic=topic,
            created_by="lingzhi",
            description=f"查询 '{query}' 已被搜索 {hit_count} 次仍无满意结果，需要补充相关知识。"
            f"分类: {category or '未知'}",
            priority="high",
            max_rounds=5,
        )

        await svc.post_message(
            thread_id=thread["id"],
            agent_id="lingzhi",
            content=(
                f"🔔 知识缺口告警\n\n"
                f"查询: {query}\n"
                f"命中次数: {hit_count}\n"
                f"分类: {category or '未知'}\n\n"
                f"请灵克/灵通关注此缺口，评估是否需要补充相关文档。"
            ),
            message_type="opening",
        )

        logger.info(f"缺口告警已发送: query='{query}', hit_count={hit_count}, thread={thread['id']}")
    except Exception as e:
        logger.warning(f"发送缺口告警失败（不影响主流程）: {e}")


async def update_gap_status(
    pool: asyncpg.Pool,
    gap_id: int,
    status: str,
    resolved_by: Optional[int] = None,
) -> bool:
    """
    更新缺口状态。

    Args:
        pool: 数据库连接池
        gap_id: 缺口 ID
        status: 新状态
        resolved_by: 解决该缺口的文档 ID

    Returns:
        是否成功
    """
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE knowledge_gaps
                SET status = $1, resolved_by = $2
                WHERE id = $3
                """,
                status,
                resolved_by,
                gap_id,
            )
            return "UPDATE 1" == result
    except Exception as e:
        logger.error(f"更新缺口状态失败: {e}", exc_info=True)
        return False
