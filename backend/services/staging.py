"""
知识临时区服务

灵克/灵通问道整理的知识先存入 documents_staging，审核通过后发布到 documents 表。
这是"第一个反射弧"的入库环节。

流程：知识缺口 → 灵克整理 → 暂存(staging) → 灵知审核 → 发布(documents)
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

VALID_STATUSES = {"draft", "submitted", "reviewing", "approved", "rejected", "published"}
VALID_SOURCES = {"manual", "lingke", "lingtong_wendao", "api", "gap_fill"}


async def create_staging_doc(
    pool: asyncpg.Pool,
    title: str,
    content: str,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    source: str = "manual",
    source_ref: Optional[Dict[str, Any]] = None,
    gap_id: Optional[int] = None,
    submitted_by: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    创建暂存文档。

    Args:
        pool: 数据库连接池
        title: 标题
        content: 内容
        category: 分类
        tags: 标签
        source: 来源（manual/lingke/lingtong_wendao/api/gap_fill）
        source_ref: 来源引用
        gap_id: 关联的知识缺口 ID
        submitted_by: 提交者
        metadata: 额外元数据

    Returns:
        暂存文档 ID
    """
    if source not in VALID_SOURCES:
        raise ValueError(f"无效来源: {source}, 有效值: {VALID_SOURCES}")

    async with pool.acquire() as conn:
        staging_id = await conn.fetchval(
            """
            INSERT INTO documents_staging
                (title, content, category, tags, source, source_ref,
                 gap_id, submitted_by, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
            """,
            title,
            content,
            category,
            tags or [],
            source,
            json.dumps(source_ref or {}),
            gap_id,
            submitted_by,
            json.dumps(metadata or {}),
        )

    logger.info(f"暂存文档已创建: id={staging_id}, title='{title}', source={source}")
    return staging_id


async def list_staging_docs(
    pool: asyncpg.Pool,
    status: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    gap_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    查询暂存文档列表。

    Args:
        pool: 数据库连接池
        status: 状态过滤
        category: 分类过滤
        source: 来源过滤
        gap_id: 关联缺口 ID
        limit: 返回数量
        offset: 偏移量

    Returns:
        暂存文档列表
    """
    conditions = []
    params: list = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if category:
        conditions.append(f"category = ${idx}")
        params.append(category)
        idx += 1
    if source:
        conditions.append(f"source = ${idx}")
        params.append(source)
        idx += 1
    if gap_id is not None:
        conditions.append(f"gap_id = ${idx}")
        params.append(gap_id)
        idx += 1

    where = ""
    if conditions:
        where = " WHERE " + " AND ".join(conditions)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, title, content, category, tags, source, source_ref,
                   status, quality_score, gap_id, submitted_by, reviewed_by,
                   review_notes, published_doc_id, created_at, updated_at, metadata
            FROM documents_staging
            {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )

    return [dict(r) for r in rows]


async def get_staging_doc(pool: asyncpg.Pool, staging_id: int) -> Optional[Dict[str, Any]]:
    """
    获取单个暂存文档。

    Args:
        pool: 数据库连接池
        staging_id: 暂存文档 ID

    Returns:
        暂存文档详情，不存在则返回 None
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, content, category, tags, source, source_ref,
                   status, quality_score, gap_id, submitted_by, reviewed_by,
                   review_notes, published_doc_id, created_at, updated_at, metadata
            FROM documents_staging
            WHERE id = $1
            """,
            staging_id,
        )

    return dict(row) if row else None


async def update_staging_doc(
    pool: asyncpg.Pool,
    staging_id: int,
    **fields,
) -> bool:
    """
    更新暂存文档字段。

    Args:
        pool: 数据库连接池
        staging_id: 暂存文档 ID
        fields: 可更新字段（title, content, category, tags, metadata）

    Returns:
        是否成功
    """
    allowed = {"title", "content", "category", "tags", "metadata"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}

    if not updates:
        return False

    if "metadata" in updates and isinstance(updates["metadata"], dict):
        updates["metadata"] = json.dumps(updates["metadata"])

    set_clauses = []
    params: list = []
    idx = 1
    for col, val in updates.items():
        set_clauses.append(f"{col} = ${idx}")
        params.append(val)
        idx += 1

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    params.append(staging_id)

    async with pool.acquire() as conn:
        result = await conn.execute(
            f"""
            UPDATE documents_staging
            SET {', '.join(set_clauses)}
            WHERE id = ${idx} AND status IN ('draft', 'submitted')
            """,
            *params,
        )

    return "UPDATE 1" == result


async def submit_for_review(pool: asyncpg.Pool, staging_id: int) -> bool:
    """
    提交暂存文档进入审核。

    Args:
        pool: 数据库连接池
        staging_id: 暂存文档 ID

    Returns:
        是否成功
    """
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE documents_staging
            SET status = 'submitted', updated_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND status = 'draft'
            """,
            staging_id,
        )
    return "UPDATE 1" == result


async def approve_and_publish(
    pool: asyncpg.Pool,
    staging_id: int,
    reviewed_by: Optional[str] = None,
    review_notes: Optional[str] = None,
) -> Optional[int]:
    """
    审核通过并发布到 documents 表。

    同时更新关联的 knowledge_gap 状态为 resolved。

    Args:
        pool: 数据库连接池
        staging_id: 暂存文档 ID
        reviewed_by: 审核人
        review_notes: 审核备注

    Returns:
        发布后的 documents.id，失败返回 None
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            staging = await conn.fetchrow(
                """
                SELECT id, title, content, category, tags, gap_id, metadata
                FROM documents_staging
                WHERE id = $1 AND status IN ('submitted', 'reviewing')
                FOR UPDATE
                """,
                staging_id,
            )

            if not staging:
                logger.warning(f"暂存文档 {staging_id} 不存在或状态不允许发布")
                return None

            doc_id = await conn.fetchval(
                """
                INSERT INTO documents (title, content, category, tags)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (title) DO UPDATE SET
                    content = EXCLUDED.content,
                    category = EXCLUDED.category,
                    tags = EXCLUDED.tags,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                staging["title"],
                staging["content"],
                staging["category"],
                staging["tags"],
            )

            await conn.execute(
                """
                UPDATE documents_staging
                SET status = 'published',
                    published_doc_id = $1,
                    reviewed_by = $2,
                    review_notes = $3,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $4
                """,
                doc_id,
                reviewed_by,
                review_notes,
                staging_id,
            )

            if staging["gap_id"]:
                await conn.execute(
                    """
                    UPDATE knowledge_gaps
                    SET status = 'resolved', resolved_by = $1
                    WHERE id = $2 AND status != 'resolved'
                    """,
                    doc_id,
                    staging["gap_id"],
                )
                logger.info(f"知识缺口 {staging['gap_id']} 已标记为 resolved，关联文档 {doc_id}")

            logger.info(f"暂存文档 {staging_id} 已发布为 documents.id={doc_id}")
            return doc_id


async def reject_staging(
    pool: asyncpg.Pool,
    staging_id: int,
    reviewed_by: Optional[str] = None,
    review_notes: Optional[str] = None,
) -> bool:
    """
    拒绝暂存文档。

    Args:
        pool: 数据库连接池
        staging_id: 暂存文档 ID
        reviewed_by: 审核人
        review_notes: 拒绝原因

    Returns:
        是否成功
    """
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE documents_staging
            SET status = 'rejected',
                reviewed_by = $1,
                review_notes = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $3 AND status IN ('submitted', 'reviewing')
            """,
            reviewed_by,
            review_notes,
            staging_id,
        )
    return "UPDATE 1" == result


async def get_staging_stats(pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    获取暂存区统计。

    Returns:
        统计信息
    """
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM documents_staging") or 0
        by_status = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM documents_staging GROUP BY status"
        )
        by_source = await conn.fetch(
            "SELECT source, COUNT(*) as count FROM documents_staging GROUP BY source"
        )
        gap_linked = (
            await conn.fetchval("SELECT COUNT(*) FROM documents_staging WHERE gap_id IS NOT NULL")
            or 0
        )

    return {
        "total": total,
        "by_status": {r["status"]: r["count"] for r in by_status},
        "by_source": {r["source"]: r["count"] for r in by_source},
        "gap_linked": gap_linked,
    }
