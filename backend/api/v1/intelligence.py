"""情报系统API路由

提供情报采集、查询、管理的REST API接口。
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from backend.services.intelligence.service import IntelligenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


def _get_service() -> IntelligenceService:
    """获取情报服务实例"""
    return IntelligenceService()


@router.post("/collect")
async def trigger_collection(
    background_tasks: BackgroundTasks,
    source: Optional[str] = Query(
        None,
        description="采集来源: github, npm, huggingface。为空时采集全部",
    ),
):
    """触发情报采集（后台执行）"""
    try:
        if source and source not in ("github", "npm", "huggingface"):
            raise HTTPException(
                status_code=400,
                detail=f"不支持的来源: {source}，可选: github, npm, huggingface",
            )

        sources = [source] if source else None
        service = _get_service()
        background_tasks.add_task(service.collect_all, sources)

        return {
            "status": "ok",
            "message": f"情报采集任务已提交{'(来源: ' + source + ')' if source else '(全部来源)'}",
            "source": source or "all",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"trigger_collection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="触发情报采集失败")


@router.get("/items")
async def list_items(
    source: Optional[str] = Query(None, description="来源过滤"),
    relevance_category: Optional[str] = Query(
        None, description="相关性分类: high_value, medium_value, monitoring"
    ),
    is_read: Optional[bool] = Query(None, description="已读状态"),
    starred: Optional[bool] = Query(None, description="收藏状态"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """查询情报条目列表"""
    try:
        service = _get_service()
        result = await service.get_items(
            source=source,
            relevance_category=relevance_category,
            is_read=is_read,
            starred=starred,
            search=search,
            limit=limit,
            offset=offset,
        )
        return {"status": "ok", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_items failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询情报列表失败")


@router.get("/items/{item_id}")
async def get_item(item_id: int):
    """获取情报条目详情"""
    try:
        service = _get_service()
        item = await service.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="情报条目不存在")
        return {"status": "ok", "data": item}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_item failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取情报详情失败")


@router.post("/items/{item_id}/mark-read")
async def mark_item_read(
    item_id: int,
    is_read: bool = Query(True, description="是否已读"),
):
    """标记情报条目为已读/未读"""
    try:
        service = _get_service()
        success = await service.mark_read(item_id, is_read)
        if not success:
            raise HTTPException(status_code=404, detail="情报条目不存在")
        return {"status": "ok", "message": f"已{'标记为已读' if is_read else '标记为未读'}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"mark_item_read failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="标记已读状态失败")


@router.post("/items/{item_id}/star")
async def toggle_star(item_id: int):
    """切换情报条目收藏状态"""
    try:
        service = _get_service()
        result = await service.toggle_star(item_id)
        if result is None:
            raise HTTPException(status_code=404, detail="情报条目不存在")
        return {"status": "ok", "data": {"starred": result}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"toggle_star failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="切换收藏状态失败")


@router.put("/items/{item_id}/notes")
async def update_notes(
    item_id: int,
    notes: str = Query(..., description="备注内容"),
):
    """更新情报条目备注"""
    try:
        service = _get_service()
        success = await service.update_notes(item_id, notes)
        if not success:
            raise HTTPException(status_code=404, detail="情报条目不存在")
        return {"status": "ok", "message": "备注已更新"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_notes failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新备注失败")


@router.get("/dashboard")
async def get_dashboard():
    """获取情报仪表盘摘要"""
    try:
        service = _get_service()
        data = await service.get_dashboard()
        return {"status": "ok", "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_dashboard failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取情报仪表盘失败")


@router.post("/refresh")
async def refresh_intelligence(
    background_tasks: BackgroundTasks,
    source: Optional[str] = Query(None, description="指定来源，为空时刷新全部"),
):
    """刷新情报数据（同 /collect，语义化别名）"""
    return await trigger_collection(background_tasks, source)
