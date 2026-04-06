"""知识临时区 API

灵克/灵通问道整理的知识先暂存，灵知审核后发布。
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.core.database import init_db_pool
from backend.services.staging import (
    approve_and_publish,
    create_staging_doc,
    get_staging_doc,
    get_staging_stats,
    list_staging_docs,
    reject_staging,
    submit_for_review,
    update_staging_doc,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/staging", tags=["staging"])


class StagingDocCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    source: str = "manual"
    source_ref: Optional[dict] = None
    gap_id: Optional[int] = None
    submitted_by: Optional[str] = None
    metadata: Optional[dict] = None


class StagingDocUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[dict] = None


class ReviewRequest(BaseModel):
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None


@router.post("")
async def post_staging_doc(req: StagingDocCreate):
    """创建暂存文档"""
    try:
        pool = await init_db_pool()
        staging_id = await create_staging_doc(
            pool,
            title=req.title,
            content=req.content,
            category=req.category,
            tags=req.tags,
            source=req.source,
            source_ref=req.source_ref,
            gap_id=req.gap_id,
            submitted_by=req.submitted_by,
            metadata=req.metadata,
        )
        return {"status": "ok", "data": {"id": staging_id}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建暂存文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_staging_list(
    status: Optional[str] = Query(None, pattern="^(draft|submitted|reviewing|approved|rejected|published)$"),
    category: Optional[str] = None,
    source: Optional[str] = None,
    gap_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """查询暂存文档列表"""
    try:
        pool = await init_db_pool()
        docs = await list_staging_docs(
            pool, status=status, category=category, source=source,
            gap_id=gap_id, limit=limit, offset=offset,
        )
        return {"status": "ok", "data": docs, "count": len(docs)}
    except Exception as e:
        logger.error(f"查询暂存文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def staging_stats():
    """暂存区统计"""
    try:
        pool = await init_db_pool()
        stats = await get_staging_stats(pool)
        return {"status": "ok", "data": stats}
    except Exception as e:
        logger.error(f"获取暂存统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{staging_id}")
async def get_staging_detail(staging_id: int):
    """获取暂存文档详情"""
    try:
        pool = await init_db_pool()
        doc = await get_staging_doc(pool, staging_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"暂存文档 {staging_id} 不存在")
        return {"status": "ok", "data": doc}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取暂存文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{staging_id}")
async def put_staging_doc(staging_id: int, req: StagingDocUpdate):
    """更新暂存文档（仅 draft/submitted 状态可编辑）"""
    try:
        pool = await init_db_pool()
        ok = await update_staging_doc(pool, staging_id, **req.model_dump(exclude_none=True))
        if not ok:
            raise HTTPException(status_code=404, detail=f"暂存文档 {staging_id} 不存在或不可编辑")
        return {"status": "ok", "data": {"id": staging_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新暂存文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{staging_id}/submit")
async def patch_submit(staging_id: int):
    """提交暂存文档进入审核"""
    try:
        pool = await init_db_pool()
        ok = await submit_for_review(pool, staging_id)
        if not ok:
            raise HTTPException(status_code=400, detail=f"暂存文档 {staging_id} 不在 draft 状态")
        return {"status": "ok", "data": {"id": staging_id, "status": "submitted"}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交审核失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{staging_id}/approve")
async def patch_approve(staging_id: int, req: ReviewRequest):
    """审核通过并发布到 documents 表"""
    try:
        pool = await init_db_pool()
        doc_id = await approve_and_publish(
            pool, staging_id,
            reviewed_by=req.reviewed_by,
            review_notes=req.review_notes,
        )
        if doc_id is None:
            raise HTTPException(status_code=400, detail=f"暂存文档 {staging_id} 不存在或不可发布")
        return {"status": "ok", "data": {"staging_id": staging_id, "published_doc_id": doc_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"审核发布失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{staging_id}/reject")
async def patch_reject(staging_id: int, req: ReviewRequest):
    """拒绝暂存文档"""
    try:
        pool = await init_db_pool()
        ok = await reject_staging(
            pool, staging_id,
            reviewed_by=req.reviewed_by,
            review_notes=req.review_notes,
        )
        if not ok:
            raise HTTPException(status_code=400, detail=f"暂存文档 {staging_id} 不存在或不可拒绝")
        return {"status": "ok", "data": {"id": staging_id, "status": "rejected"}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"拒绝暂存文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
