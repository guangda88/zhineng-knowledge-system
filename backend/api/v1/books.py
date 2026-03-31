"""书籍搜索API路由

提供书籍搜索、详情、章节内容等API端点
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from core.database import get_async_session
from core.dependency_injection import get_db_pool as _get_di_db_pool
from schemas.book import (
    BookSearchResult,
    BookDetailResponse,
    ContentSearchResponse,
    SimilarBookResponse,
    ChapterResponse,
    FiltersResponse,
    DataSourceResponse
)
from services.book_search import BookSearchService
from models.source import DataSource

router = APIRouter(prefix="/library", tags=["书籍搜索"])


@router.get("/search", response_model=BookSearchResult)
async def search_books(
    q: str = Query("", max_length=200, description="搜索关键词"),
    category: Optional[str] = Query(None, description="分类筛选（气功/中医/儒家）"),
    dynasty: Optional[str] = Query(None, description="朝代筛选"),
    author: Optional[str] = Query(None, description="作者筛选"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_async_session)
):
    """
    搜索书籍（元数据搜索）

    搜索标题、作者、描述等元数据字段
    """
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
    db: AsyncSession = Depends(get_async_session)
):
    """
    全文内容搜索

    搜索书籍章节内容
    """
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
    db: AsyncSession = Depends(get_async_session)
):
    """
    获取书籍详情

    包含书籍元数据和章节列表
    """
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
    db: AsyncSession = Depends(get_async_session)
):
    """
    获取相关书籍

    基于向量相似度推荐相关书籍
    """
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
    db: AsyncSession = Depends(get_async_session)
):
    """
    获取章节内容

    返回指定章节的完整内容
    """
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
    """
    获取筛选选项

    返回可用的分类、朝代、语言等筛选选项
    """
    try:
        # 获取分类
        categories_result = await db.execute(
            "SELECT DISTINCT category FROM books WHERE category IS NOT NULL ORDER BY category"
        )
        categories = [row[0] for row in categories_result.fetchall()]

        # 获取朝代
        dynasties_result = await db.execute(
            "SELECT DISTINCT dynasty FROM books WHERE dynasty IS NOT NULL ORDER BY dynasty"
        )
        dynasties = [row[0] for row in dynasties_result.fetchall()]

        # 获取语言
        languages_result = await db.execute(
            "SELECT DISTINCT language FROM books WHERE language IS NOT NULL ORDER BY language"
        )
        languages = [row[0] for row in languages_result.fetchall()]

        # 获取数据源
        sources_result = await db.execute(
            select(DataSource).where(DataSource.is_active == True).order_by(DataSource.sort_order)
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
                is_active=s.is_active
            )
            for s in sources_result.scalars().all()
        ]

        return FiltersResponse(
            categories=categories,
            dynasties=dynasties,
            languages=languages,
            sources=sources
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取筛选选项失败: {str(e)}")
