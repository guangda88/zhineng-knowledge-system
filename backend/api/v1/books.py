"""书籍搜索API路由 — lingflow 增强版

提供书籍搜索、详情、章节内容等API端点。
lingflow 增强功能：
- 统一跨源搜索（books + sys_books + guoxue_books）
- book_chapters 全文搜索
- 智能结果合并排序
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.dependency_injection import get_db_pool as _get_di_db_pool
from backend.schemas.book import (
    BookDetailResponse,
    BookSearchResult,
    ChapterResponse,
    ContentSearchResponse,
    DataSourceResponse,
    FiltersResponse,
    SimilarBookResponse,
)
from backend.services.book_search import BookSearchService
from backend.services.lingflow_book_search import lingflowBookSearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/library", tags=["书籍搜索"])


def _get_service() -> BookSearchService:
    pool = _get_di_db_pool()
    return BookSearchService(pool)


@router.get("/search", response_model=BookSearchResult)
async def search_books(
    q: str = Query("", max_length=200, description="搜索关键词"),
    category: Optional[str] = Query(
        None, description="分类筛选（气功/中医/儒家/佛家/道家/武术/哲学/科学/心理学）"
    ),
    dynasty: Optional[str] = Query(None, description="朝代筛选"),
    author: Optional[str] = Query(None, description="作者筛选"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """搜索书籍（元数据搜索）"""
    try:
        service = _get_service()
        result = await service.search_metadata(q, category, dynasty, author, page, size)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/search/content", response_model=ContentSearchResponse)
async def search_book_content(
    q: str = Query(..., max_length=200, description="搜索关键词"),
    category: Optional[str] = Query(None, description="分类筛选"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """全文内容搜索"""
    try:
        service = _get_service()
        result = await service.search_content(q, category, page, size)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"全文搜索失败: {str(e)}")


@router.get("/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: int,
):
    """获取书籍详情"""
    try:
        service = _get_service()
        result = await service.get_book_detail(book_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"书籍 {book_id} 不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取书籍详情失败: {str(e)}")


@router.get("/{book_id}/related", response_model=List[SimilarBookResponse])
async def get_related_books(
    book_id: int,
    top_k: int = Query(10, ge=1, le=50, description="返回数量"),
    threshold: float = Query(0.6, ge=0.0, le=1.0, description="相似度阈值"),
):
    """获取相关书籍（基于向量相似度）"""
    try:
        pool = _get_di_db_pool()
        if pool is None:
            logger.warning("DB pool not initialized, returning empty related books")
            return []
        service = BookSearchService(pool)
        results = await service.search_similar(book_id, top_k, threshold)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取相关书籍失败: {str(e)}")


@router.get("/{book_id}/chapters/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    book_id: int,
    chapter_id: int,
):
    """获取章节内容"""
    try:
        service = _get_service()
        result = await service.get_chapter_content(book_id, chapter_id)
        if not result:
            raise HTTPException(status_code=404, detail="章节不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取章节内容失败: {str(e)}")


@router.get("/filters/list", response_model=FiltersResponse)
async def get_filters():
    """获取筛选选项"""
    try:
        service = _get_service()
        result = await service.get_filters()
        return FiltersResponse(
            categories=result["categories"],
            dynasties=result["dynasties"],
            languages=result["languages"],
            sources=[DataSourceResponse(**s) for s in result["sources"]],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取筛选选项失败: {str(e)}")


# ========== lingflow 统一搜索端点 ==========


@router.get("/lingflow/unified")
async def lingflow_unified_search(
    q: str = Query(..., min_length=1, max_length=200, description="搜索关键词"),
    category: Optional[str] = Query(None, description="分类筛选"),
    dynasty: Optional[str] = Query(None, description="朝代筛选"),
    author: Optional[str] = Query(None, description="作者筛选"),
    source: Optional[str] = Query(None, description="数据源标识"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """lingflow 统一搜索"""
    try:
        pool = _get_di_db_pool()
        if pool is None:
            raise HTTPException(status_code=503, detail="数据库连接池未初始化")

        service = lingflowBookSearchService(pool)
        result = await service.unified_search(
            query=q,
            category=category,
            dynasty=dynasty,
            author=author,
            source=source,
            page=page,
            size=size,
        )
        return {"status": "ok", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"lingflow_unified_search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="统一搜索失败")


@router.get("/lingflow/fulltext")
async def lingflow_fulltext_search(
    q: str = Query(..., min_length=1, max_length=200, description="搜索关键词"),
    book_id: Optional[int] = Query(None, description="限定书籍ID"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """lingflow 书籍全文搜索"""
    try:
        pool = _get_di_db_pool()
        if pool is None:
            raise HTTPException(status_code=503, detail="数据库连接池未初始化")

        service = lingflowBookSearchService(pool)
        result = await service.search_books_fulltext(
            query=q,
            book_id=book_id,
            page=page,
            size=size,
        )
        return {"status": "ok", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"lingflow_fulltext_search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="全文搜索失败")
