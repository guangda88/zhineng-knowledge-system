"""知识缺口感知 API

暴露灵知的知识缺口数据，供灵克/灵通问道/灵依等消费。
这是"第一个反射弧"的数据出口。
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.core.database import init_db_pool
from backend.services.retrieval.gap_tracker import (
    get_gaps,
    get_gaps_stats,
    update_gap_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge-gaps", tags=["knowledge-gaps"])


class GapStatusUpdate(BaseModel):
    status: str = Query(..., pattern="^(acknowledged|filling|resolved|dismissed)$")
    resolved_by: Optional[int] = None


@router.get("")
async def list_gaps(
    status: str = Query("open", pattern="^(open|acknowledged|filling|resolved|dismissed|all)$"),
    category: Optional[str] = None,
    min_hits: int = Query(1, ge=1, description="最小重复次数"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """查询知识缺口列表"""
    try:
        pool = await init_db_pool()
        effective_status = None if status == "all" else status
        gaps = await get_gaps(pool, effective_status, category, min_hits, limit, offset)
        return {"status": "ok", "data": gaps, "count": len(gaps)}
    except Exception as e:
        logger.error(f"查询知识缺口失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def gaps_stats():
    """知识缺口统计"""
    try:
        pool = await init_db_pool()
        stats = await get_gaps_stats(pool)
        return {"status": "ok", "data": stats}
    except Exception as e:
        logger.error(f"获取缺口统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{gap_id}")
async def patch_gap(gap_id: int, req: GapStatusUpdate):
    """更新缺口状态（如标记为已解决）"""
    try:
        pool = await init_db_pool()
        ok = await update_gap_status(pool, gap_id, req.status, req.resolved_by)
        if not ok:
            raise HTTPException(status_code=404, detail=f"缺口 {gap_id} 不存在")
        return {"status": "ok", "data": {"id": gap_id, "status": req.status}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新缺口状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
