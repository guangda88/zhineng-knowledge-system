"""检索反馈闭环 API

用户对搜索结果提交反馈，用于评估和优化检索质量。
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.core.database import init_db_pool
from backend.services.retrieval.feedback import (
    get_doc_quality_scores,
    get_feedback_stats,
    list_feedback,
    submit_feedback,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


class FeedbackSubmit(BaseModel):
    query: str
    feedback_type: str
    doc_id: Optional[int] = None
    rating: Optional[int] = None
    category: Optional[str] = None
    search_method: Optional[str] = None
    rank_position: Optional[int] = None
    similarity_score: Optional[float] = None
    comment: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[dict] = None


class DocQualityRequest(BaseModel):
    doc_ids: list[int]


@router.post("")
async def post_feedback(req: FeedbackSubmit):
    """提交检索反馈"""
    try:
        pool = await init_db_pool()
        fb_id = await submit_feedback(
            pool,
            query=req.query,
            feedback_type=req.feedback_type,
            doc_id=req.doc_id,
            rating=req.rating,
            category=req.category,
            search_method=req.search_method,
            rank_position=req.rank_position,
            similarity_score=req.similarity_score,
            comment=req.comment,
            session_id=req.session_id,
            metadata=req.metadata,
        )
        return {"status": "ok", "data": {"id": fb_id}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"提交反馈失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_feedback_list(
    feedback_type: Optional[str] = Query(None, pattern="^(helpful|not_helpful|wrong|irrelevant|partial)$"),
    doc_id: Optional[int] = None,
    query: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """查询反馈列表"""
    try:
        pool = await init_db_pool()
        feedbacks = await list_feedback(
            pool, feedback_type=feedback_type, doc_id=doc_id,
            query=query, limit=limit, offset=offset,
        )
        return {"status": "ok", "data": feedbacks, "count": len(feedbacks)}
    except Exception as e:
        logger.error(f"查询反馈失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def feedback_stats():
    """反馈统计概览"""
    try:
        pool = await init_db_pool()
        stats = await get_feedback_stats(pool)
        return {"status": "ok", "data": stats}
    except Exception as e:
        logger.error(f"获取反馈统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/doc-quality")
async def doc_quality(req: DocQualityRequest):
    """批量获取文档反馈质量评分"""
    try:
        pool = await init_db_pool()
        scores = await get_doc_quality_scores(pool, req.doc_ids)
        return {"status": "ok", "data": scores}
    except Exception as e:
        logger.error(f"获取文档质量评分失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
