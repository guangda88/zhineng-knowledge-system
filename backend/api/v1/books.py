"""书籍搜索API路由 — LingFlow 增强版

提供书籍搜索、详情、章节内容等API端点。
LingFlow 增强功能：
- 统一跨源搜索（books + sys_books + guoxue_books）
- book_chapters 全文搜索
- 智能结果合并排序
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_async_session
from backend.core.dependency_injection import get_db_pool as _get_di_db_pool
from backend.models.book import Book
from backend.models.source import DataSource
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
from backend.services.lingflow_book_search import LingFlowBookSearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/library", tags=["书籍搜索"])


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
    db: AsyncSession = Depends(get_async_session),
):
    """搜索书籍（元数据搜索）"""
    try:
        pool = _get_di_db_pool()
        service = BookSearchService(db, pool)
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
    db: AsyncSession = Depends(get_async_session),
):
    """全文内容搜索"""
    try:
        pool = _get_di_db_pool()
        service = BookSearchService(db, pool)
        result = await service.search_content(q, category, page, size)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"全文搜索失败: {str(e)}")


@router.get("/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """获取书籍详情"""
    try:
        pool = _get_di_db_pool()
        service = BookSearchService(db, pool)
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
    db: AsyncSession = Depends(get_async_session),
):
    """获取相关书籍（基于向量相似度）"""
    try:
        pool = _get_di_db_pool()
        service = BookSearchService(db, pool)
        results = await service.search_similar(book_id, top_k, threshold)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取相关书籍失败: {str(e)}")


@router.get("/{book_id}/chapters/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    book_id: int,
    chapter_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """获取章节内容"""
    try:
        pool = _get_di_db_pool()
        service = BookSearchService(db, pool)
        result = await service.get_chapter_content(book_id, chapter_id)
        if not result:
            raise HTTPException(status_code=404, detail="章节不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取章节内容失败: {str(e)}")


@router.get("/filters/list", response_model=FiltersResponse)
async def get_filters(db: AsyncSession = Depends(get_async_session)):
    """获取筛选选项"""
    try:
        categories_stmt = (
            select(distinct(Book.category)).where(Book.category.isnot(None)).order_by(Book.category)
        )
        categories_result = await db.execute(categories_stmt)
        categories = [row[0] for row in categories_result.scalars().all()]

        dynasties_stmt = (
            select(distinct(Book.dynasty)).where(Book.dynasty.isnot(None)).order_by(Book.dynasty)
        )
        dynasties_result = await db.execute(dynasties_stmt)
        dynasties = [row[0] for row in dynasties_result.scalars().all()]

        languages_stmt = (
            select(distinct(Book.language)).where(Book.language.isnot(None)).order_by(Book.language)
        )
        languages_result = await db.execute(languages_stmt)
        languages = [row[0] for row in languages_result.scalars().all()]

        sources_result = await db.execute(
            select(DataSource)
            .where(DataSource.is_active == True)  # noqa: E712
            .order_by(DataSource.sort_order)  # noqa: E712
        )
        sources = [
            DataSourceResponse(
                id=s.id,
                code=s.code,
                name_zh=s.name_zh,
                name_en=s.name_en,
                description=s.description,
                category=s.category,
                supports_search=s.supports_search,
                supports_fulltext=s.supports_fulltext,
                is_active=s.is_active,
            )
            for s in sources_result.scalars().all()
        ]

        return FiltersResponse(
            categories=categories,
            dynasties=dynasties,
            languages=languages,
            sources=sources,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取筛选选项失败: {str(e)}")


# ========== LingFlow 统一搜索端点 ==========


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
    """LingFlow 统一搜索

    同时检索 books、sys_books、guoxue_books 三个数据源，
    合并结果按相关性排序返回。
    """
    pool = _get_di_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接池未初始化")

    service = LingFlowBookSearchService(pool)
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


@router.get("/lingflow/fulltext")
async def lingflow_fulltext_search(
    q: str = Query(..., min_length=1, max_length=200, description="搜索关键词"),
    book_id: Optional[int] = Query(None, description="限定书籍ID"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """LingFlow 书籍全文搜索

    在 book_chapters 中搜索，返回带上下文片段的结果。
    """
    pool = _get_di_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接池未初始化")

    service = LingFlowBookSearchService(pool)
    result = await service.search_books_fulltext(
        query=q,
        book_id=book_id,
        page=page,
        size=size,
    )
    return {"status": "ok", "data": result}
