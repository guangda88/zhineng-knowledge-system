"""上下文管理 API

提供上下文管理、Token 估算、消息评分、上下文压缩等功能。
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/context", tags=["context"])


# ===== 请求/响应模型 =====


class TokenEstimateRequest(BaseModel):
    """Token 估算请求"""

    text: str = Field(..., description="要估算的文本", min_length=1)
    model: str = Field(default="claude-opus-4", description="模型名称")


class TokenEstimateResponse(BaseModel):
    """Token 估算响应"""

    token_count: int
    model: str
    encoding: str
    estimated: bool


class RecordMessageRequest(BaseModel):
    """记录消息请求"""

    role: str = Field(..., description="消息角色: user/assistant/system")
    content: str = Field(..., description="消息内容", min_length=1)
    is_important: bool = Field(default=False, description="是否为重要消息")


class MessageScoreRequest(BaseModel):
    """消息评分请求"""

    messages: List[Dict] = Field(..., description="消息列表")


class MessageScoreResponse(BaseModel):
    """消息评分响应"""

    scores: List[Dict]
    total_messages: int
    average_importance: float


class CompressRequest(BaseModel):
    """压缩请求"""

    session_id: Optional[str] = Field(None, description="会话 ID（可选）")


class CompressResponse(BaseModel):
    """压缩响应"""

    summary: str
    session_id: str
    timestamp: str


class TaskRequest(BaseModel):
    """任务请求"""

    task: str = Field(..., description="任务描述", min_length=1)
    completed: bool = Field(default=False, description="是否已完成")


class DecisionRequest(BaseModel):
    """决策请求"""

    decision: str = Field(..., description="决策内容", min_length=1)


class StatusResponse(BaseModel):
    """状态响应"""

    session_id: str
    message_count: int
    estimated_tokens: int
    token_limit: int
    token_usage_ratio: float
    health_status: str
    tasks_completed: int
    tasks_pending: int
    needs_compression: bool


class SnapshotResponse(BaseModel):
    """快照响应"""

    timestamp: str
    session_id: str
    tasks_completed: List[str]
    tasks_pending: List[str]
    key_decisions: List[str]
    important_files: Dict[str, str]
    context_summary: str
    next_steps: List[str]


# ===== API 端点 =====





@router.post("/messages/score", response_model=MessageScoreResponse)
async def score_messages(request: MessageScoreRequest) -> MessageScoreResponse:
    """评分消息列表

    对消息列表进行多维度评分，包括重要性、相关性、时间、质量等。
    """
    try:
        from backend.services.context_service import get_context_service

        service = get_context_service()
        scores = service.score_messages(request.messages)

        avg_importance = sum(s.importance_score for s in scores) / len(scores) if scores else 0

        return MessageScoreResponse(
            scores=[s.model_dump() for s in scores],
            total_messages=len(scores),
            average_importance=round(avg_importance, 3),
        )
    except Exception as e:
        logger.error(f"消息评分失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"消息评分失败: {e}")


@router.post("/messages/record")
async def record_message(request: RecordMessageRequest) -> Dict[str, Any]:
    """记录一条消息

    将消息添加到上下文跟踪中，自动提取重要信息。
    """
    try:
        from backend.services.context_service import get_context_service

        service = get_context_service()
        service.record_message(request.role, request.content, request.is_important)

        current_status = service.get_status()

        return {
            "message": "Message recorded successfully",
            "session_id": service.session_id,
            "current_status": current_status.model_dump(),
        }
    except Exception as e:
        logger.error(f"消息记录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"消息记录失败: {e}")


@router.post("/compress", response_model=CompressResponse)
async def compress_context(request: CompressRequest) -> CompressResponse:
    """压缩当前上下文

    生成上下文摘要，可用于新会话恢复。
    """
    try:
        from datetime import datetime

        from backend.services.context_service import get_context_service

        service = get_context_service()
        summary = service.compress_now()

        return CompressResponse(
            summary=summary, session_id=service.session_id, timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"上下文压缩失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"上下文压缩失败: {e}")


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """获取当前上下文状态

    返回会话状态、Token 使用情况、任务统计等信息。
    """
    try:
        from backend.services.context_service import get_context_service

        service = get_context_service()
        status = service.get_status()

        return StatusResponse(**status.model_dump())
    except Exception as e:
        logger.error(f"获取状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取状态失败: {e}")


@router.get("/snapshot", response_model=SnapshotResponse)
async def get_snapshot() -> SnapshotResponse:
    """获取当前上下文快照

    返回完整的上下文快照，包括任务、决策、文件等。
    """
    try:
        from backend.services.context_service import get_context_service

        service = get_context_service()
        snapshot = service.get_snapshot()

        return SnapshotResponse(**snapshot.model_dump())
    except Exception as e:
        logger.error(f"获取快照失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取快照失败: {e}")


@router.get("/recovery")
async def get_recovery_summary() -> Dict[str, str]:
    """获取恢复摘要

    获取用于新会话恢复的上下文摘要。
    """
    try:
        from backend.services.context_service import get_context_service

        service = get_context_service()
        summary = service.get_recovery_summary()

        return {"session_id": service.session_id, "recovery_summary": summary}
    except Exception as e:
        logger.error(f"获取恢复摘要失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取恢复摘要失败: {e}")


@router.post("/tasks")
async def add_task(request: TaskRequest) -> Dict[str, Any]:
    """添加任务

    向上下文中添加新任务。
    """
    try:
        from backend.services.context_service import get_context_service

        service = get_context_service()
        service.add_task(request.task, request.completed)

        return {
            "message": "Task added successfully",
            "task": request.task,
            "completed": request.completed,
            "total_pending": len(service.snapshot.tasks_pending),
            "total_completed": len(service.snapshot.tasks_completed),
        }
    except Exception as e:
        logger.error(f"添加任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"添加任务失败: {e}")


@router.put("/tasks/{task_name}")
async def complete_task(task_name: str) -> Dict[str, Any]:
    """标记任务完成

    将指定任务标记为已完成。
    """
    try:
        from backend.services.context_service import get_context_service

        service = get_context_service()
        service.complete_task(task_name)

        return {
            "message": "Task completed successfully",
            "task": task_name,
            "total_pending": len(service.snapshot.tasks_pending),
            "total_completed": len(service.snapshot.tasks_completed),
        }
    except Exception as e:
        logger.error(f"完成任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"完成任务失败: {e}")


@router.post("/decisions")
async def add_decision(request: DecisionRequest) -> Dict[str, Any]:
    """记录关键决策

    向上下文中添加关键决策记录。
    """
    try:
        from backend.services.context_service import get_context_service

        service = get_context_service()
        service.add_decision(request.decision)

        return {
            "message": "Decision recorded successfully",
            "decision": request.decision,
            "total_decisions": len(service.snapshot.key_decisions),
        }
    except Exception as e:
        logger.error(f"记录决策失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"记录决策失败: {e}")


@router.post("/reset")
async def reset_context() -> Dict[str, str]:
    """重置上下文

    创建新的会话，清空当前上下文。
    """
    try:
        from backend.services.context_service import ContextService, _context_service

        old_session_id = _context_service.session_id if _context_service else None

        if _context_service is not None:
            _context_service.compress_now()

        import backend.services.context_service as cs_module

        cs_module._context_service = ContextService()

        new_service = cs_module._context_service

        return {
            "message": "Context reset successfully",
            "old_session_id": old_session_id or "none",
            "new_session_id": new_service.session_id,
        }
    except Exception as e:
        logger.error(f"重置上下文失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重置上下文失败: {e}")


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查

    检查上下文服务状态和 LingFlow 可用性。
    """
    try:
        from backend.services.context_service import get_context_service

        service = get_context_service()

        return {
            "status": "healthy",
            "lingflow_available": service.lingflow_available,
            "session_id": service.session_id,
            "storage_dir": str(service.storage_dir),
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"健康检查失败: {e}")
