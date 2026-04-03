"""国学经典检索API — LingFlow 增强版

提供对 guoxue_content（26.3万条）和 guoxue_books（109部典籍）的搜索、浏览功能。
LingFlow 增强功能：
- 多模式全文搜索（精确/模糊/宽泛）
- 跨典籍联合搜索
- 上下文片段高亮
- 相关性评分
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.common.db_helpers import row_to_dict
from backend.core.dependency_injection import get_db_pool as _get_di_db_pool
from backend.services.lingflow_guoxue_search import LingFlowGuoxueSearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/guoxue", tags=["国学经典"])


def _pool():
    pool = _get_di_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接池未初始化")
    return pool


def _guoxue_service() -> LingFlowGuoxueSearchService:
    return LingFlowGuoxueSearchService(_pool())


@router.get("/books")
async def list_books(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """典籍列表

    返回所有典籍及其章节/字符统计。
    """
    try:
        pool = _pool()

        total = await pool.fetchval("SELECT COUNT(*) FROM guoxue_books")

        offset = (page - 1) * size
        rows = await pool.fetch(
            """
            SELECT book_id, title, description, source_table,
                   content_count, total_chars, created_at
            FROM guoxue_books
            ORDER BY content_count DESC
            LIMIT $1 OFFSET $2
            """,
            size,
            offset,
        )

        return {
            "status": "ok",
            "data": {
                "total": total or 0,
                "page": page,
                "size": size,
                "results": [row_to_dict(r) for r in rows],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_books failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询典籍列表失败")


@router.get("/books/{book_id}")
async def get_book(book_id: int):
    """获取单部典籍详情"""
    try:
        pool = _pool()

        row = await pool.fetchrow(
            """
            SELECT book_id, title, description, source_table,
                   content_count, total_chars, created_at
            FROM guoxue_books
            WHERE book_id = $1
            """,
            book_id,
        )

        if not row:
            raise HTTPException(status_code=404, detail=f"典籍 {book_id} 不存在")

        return {"status": "ok", "data": row_to_dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_book failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询典籍详情失败")


@router.get("/books/{book_id}/chapters")
async def list_chapters(
    book_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """获取典籍的章节列表"""
    try:
        pool = _pool()

        book = await pool.fetchrow(
            "SELECT book_id, title FROM guoxue_books WHERE book_id = $1",
            book_id,
        )
        if not book:
            raise HTTPException(status_code=404, detail=f"典籍 {book_id} 不存在")

        total = await pool.fetchval(
            "SELECT COUNT(*) FROM guoxue_content WHERE book_id = $1",
            book_id,
        )

        offset = (page - 1) * size
        rows = await pool.fetch(
            """
            SELECT id, book_id, chapter_id, body_length, created_at
            FROM guoxue_content
            WHERE book_id = $1
            ORDER BY chapter_id, id
            LIMIT $2 OFFSET $3
            """,
            book_id,
            size,
            offset,
        )

        return {
            "status": "ok",
            "data": {
                "book": row_to_dict(book),
                "total": total or 0,
                "page": page,
                "size": size,
                "results": [row_to_dict(r) for r in rows],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_chapters failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询章节列表失败")


@router.get("/content/{content_id}")
async def get_content(content_id: int):
    """获取单条内容详情（含完整正文）"""
    try:
        pool = _pool()

        row = await pool.fetchrow(
            """
            SELECT id, book_id, chapter_id, body, body_length,
                   source_table, created_at
            FROM guoxue_content
            WHERE id = $1
            """,
            content_id,
        )

        if not row:
            raise HTTPException(status_code=404, detail=f"内容 {content_id} 不存在")

        return {"status": "ok", "data": row_to_dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_content failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询内容详情失败")


@router.get("/search")
async def search_content(
    q: str = Query(..., min_length=1, max_length=200, description="搜索关键词"),
    book_id: Optional[int] = Query(None, description="限定典籍ID"),
    mode: str = Query("fulltext", pattern="^(fulltext|fuzzy|broad)$", description="搜索模式"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """LingFlow 增强全文搜索

    支持三种搜索模式：
    - fulltext: 三元组全文搜索（默认，精确匹配优先）
    - fuzzy: 模糊搜索（容错匹配，适合错别字场景）
    - broad: 宽泛搜索（典籍级别匹配，适合探索性搜索）

    使用 CTE 避免重复扫描，estimated count 提升性能。
    """
    try:
        service = _guoxue_service()
        result = await service.search(
            query=q,
            book_id=book_id,
            search_mode=mode,
            page=page,
            size=size,
        )
        return {"status": "ok", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"search_content failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="搜索失败")


@router.get("/search/cross-book")
async def cross_book_search(
    q: str = Query(..., min_length=1, max_length=200, description="搜索关键词"),
    top_k: int = Query(5, ge=1, le=20, description="返回典籍数量"),
    per_book: int = Query(3, ge=1, le=10, description="每部典籍返回条数"),
):
    """LingFlow 跨典籍搜索

    在所有典籍中搜索关键词，返回每部典籍最相关的条目。
    适合发现某个概念在不同经典中的论述。
    """
    try:
        service = _guoxue_service()
        results = await service.cross_book_search(
            keyword=q,
            top_k=top_k,
            per_book=per_book,
        )
        return {"status": "ok", "data": {"query": q, "results": results}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"cross_book_search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="跨典籍搜索失败")


@router.get("/stats")
async def get_stats():
    """国学典籍统计"""
    try:
        pool = _pool()

        book_total = await pool.fetchval("SELECT COUNT(*) FROM guoxue_books")

        content_estimate = await pool.fetchrow(
            "SELECT reltuples::bigint AS estimate FROM pg_class WHERE oid = 'guoxue_content'::regclass"
        )
        content_total = content_estimate["estimate"] if content_estimate else 263767

        total_chars = await pool.fetchval("SELECT SUM(total_chars) FROM guoxue_books")

        top_books = await pool.fetch("""
            SELECT book_id, title, content_count, total_chars
            FROM guoxue_books
            ORDER BY content_count DESC
            LIMIT 20
            """)

        return {
            "status": "ok",
            "data": {
                "book_count": book_total,
                "content_count": content_total,
                "total_chars": total_chars or 0,
                "top_books": [row_to_dict(r) for r in top_books],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询统计失败")
