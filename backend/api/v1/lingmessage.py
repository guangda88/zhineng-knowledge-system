"""灵信通信系统API路由

提供灵字辈Agent之间跨项目讨论的REST API接口。
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.lingmessage.service import LingMessageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lingmessage", tags=["lingmessage"])


def _svc() -> LingMessageService:
    return LingMessageService()


class CreateThreadRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    created_by: str = Field(..., min_length=1, max_length=50)
    priority: str = Field("normal", pattern="^(normal|high|critical)$")
    max_rounds: int = Field(10, ge=1, le=50)


class PostMessageRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=50)
    content: str = Field(..., min_length=1)
    message_type: str = Field("response", pattern="^(opening|response|summary|consensus|dissent)$")
    round_number: Optional[int] = None
    parent_id: Optional[int] = None
    metadata: Optional[dict] = None


class RecordConsensusRequest(BaseModel):
    topic_aspect: str = Field(..., min_length=1, max_length=500)
    consensus_text: str = Field(..., min_length=1)
    agreeing_agents: List[str] = Field(..., min_length=1)
    disagreeing_agents: Optional[List[str]] = None
    confidence: float = Field(0.8, ge=0.0, le=1.0)


class CloseThreadRequest(BaseModel):
    summary: Optional[str] = None
    key_decisions: Optional[list] = None


# ============ Agent ============


@router.get("/agents")
async def list_agents(active_only: bool = Query(True)):
    """获取所有Agent列表"""
    svc = _svc()
    agents = await svc.get_agents(active_only=active_only)
    return {"status": "ok", "data": agents}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """获取单个Agent信息"""
    svc = _svc()
    agent = await svc.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' 不存在")
    return {"status": "ok", "data": agent}


# ============ Thread ============


@router.post("/threads")
async def create_thread(req: CreateThreadRequest):
    """创建讨论线程"""
    svc = _svc()
    agent = await svc.get_agent(req.created_by)
    if not agent:
        raise HTTPException(status_code=400, detail=f"Agent '{req.created_by}' 不存在")
    thread = await svc.create_thread(
        topic=req.topic,
        created_by=req.created_by,
        description=req.description,
        priority=req.priority,
        max_rounds=req.max_rounds,
    )
    return {"status": "ok", "data": thread}


@router.get("/threads")
async def list_threads(
    status: Optional[str] = Query(None, pattern="^(active|closed|archived)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """列出讨论线程"""
    svc = _svc()
    result = await svc.list_threads(status=status, limit=limit, offset=offset)
    return {"status": "ok", "data": result}


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: int):
    """获取讨论线程详情"""
    svc = _svc()
    thread = await svc.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="线程不存在")
    return {"status": "ok", "data": thread}


@router.get("/threads/{thread_id}/summary")
async def get_thread_summary(thread_id: int):
    """获取完整线程摘要（线程+消息+共识）"""
    svc = _svc()
    try:
        summary = await svc.get_thread_summary(thread_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok", "data": summary}


@router.post("/threads/{thread_id}/advance")
async def advance_round(thread_id: int):
    """推进到下一轮讨论"""
    svc = _svc()
    try:
        thread = await svc.advance_round(thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "data": thread}


@router.post("/threads/{thread_id}/close")
async def close_thread(thread_id: int, req: CloseThreadRequest):
    """关闭讨论线程"""
    svc = _svc()
    try:
        thread = await svc.close_thread(
            thread_id, summary=req.summary, key_decisions=req.key_decisions
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok", "data": thread}


# ============ Message ============


@router.post("/threads/{thread_id}/messages")
async def post_message(thread_id: int, req: PostMessageRequest):
    """发送消息到讨论线程"""
    svc = _svc()
    thread = await svc.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="线程不存在")
    if thread["status"] != "active":
        raise HTTPException(status_code=400, detail="线程已关闭，无法发送消息")
    agent = await svc.get_agent(req.agent_id)
    if not agent:
        raise HTTPException(status_code=400, detail=f"Agent '{req.agent_id}' 不存在")
    msg = await svc.post_message(
        thread_id=thread_id,
        agent_id=req.agent_id,
        content=req.content,
        message_type=req.message_type,
        round_number=req.round_number,
        parent_id=req.parent_id,
        metadata=req.metadata,
    )
    return {"status": "ok", "data": msg}


@router.get("/threads/{thread_id}/messages")
async def get_messages(
    thread_id: int,
    round_number: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """获取线程中的消息"""
    svc = _svc()
    messages = await svc.get_messages(
        thread_id=thread_id, round_number=round_number, limit=limit, offset=offset
    )
    return {"status": "ok", "data": messages}


# ============ Consensus ============


@router.post("/threads/{thread_id}/consensus")
async def record_consensus(thread_id: int, req: RecordConsensusRequest):
    """记录共识"""
    svc = _svc()
    thread = await svc.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="线程不存在")
    consensus = await svc.record_consensus(
        thread_id=thread_id,
        topic_aspect=req.topic_aspect,
        consensus_text=req.consensus_text,
        agreeing_agents=req.agreeing_agents,
        disagreeing_agents=req.disagreeing_agents,
        confidence=req.confidence,
    )
    return {"status": "ok", "data": consensus}


@router.get("/threads/{thread_id}/consensus")
async def get_consensus(thread_id: int):
    """获取线程的所有共识"""
    svc = _svc()
    consensus = await svc.get_consensus(thread_id)
    return {"status": "ok", "data": consensus}
