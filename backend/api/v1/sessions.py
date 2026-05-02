"""会话持久化 API — 自动保存、断点恢复、错误重试"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.core.database import init_db_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    title: str | None = None


class SessionRestore(BaseModel):
    session_id: str


class SessionListResponse(BaseModel):
    sessions: list[dict]


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[dict]
    has_more: bool


@router.post("/create", summary="创建新会话")
async def create_session(body: SessionCreate | None = None):
    """创建一个新的会话，返回 session_id。"""
    pool = await init_db_pool()
    session_id = datetime.now().strftime("%Y%m%d%H%M%S") + f"_{id(body):x}"[-4:]
    title = (body.title if body else None) or f"会话 {session_id[:10]}"

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sessions (id, title, status, message_count, last_message_at)
            VALUES ($1, $2, 'active', 0, CURRENT_TIMESTAMP)
            """,
            session_id,
            title,
        )

    return {"status": "ok", "session_id": session_id, "title": title}


@router.get("/list", summary="列出最近会话")
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """列出最近的会话，按最后消息时间倒序。"""
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.id, s.title, s.status, s.message_count,
                   s.last_message_at, s.created_at
            FROM sessions s
            ORDER BY s.last_message_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        total = await conn.fetchval("SELECT count(*) FROM sessions")

    sessions = []
    for r in rows:
        sessions.append(
            {
                "session_id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "message_count": r["message_count"],
                "last_message_at": (
                    r["last_message_at"].isoformat() if r["last_message_at"] else None
                ),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
        )

    return {"status": "ok", "sessions": sessions, "total": total}


@router.get("/{session_id}/history", summary="获取会话历史")
async def get_session_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None, description="分页：加载此 ID 之前的消息"),
):
    """获取某个会话的聊天历史，支持向上翻页。含上下文元数据。"""
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        session = await conn.fetchrow(
            "SELECT id, status, metadata FROM sessions WHERE id = $1", session_id
        )
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        if before_id:
            rows = await conn.fetch(
                """
                SELECT id, role, content, created_at, metadata
                FROM chat_history
                WHERE session_id = $1 AND id < $2
                ORDER BY id DESC
                LIMIT $3
                """,
                session_id,
                before_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, role, content, created_at, metadata
                FROM chat_history
                WHERE session_id = $1
                ORDER BY id DESC
                LIMIT $2
                """,
                session_id,
                limit,
            )

    # 倒序返回（最旧在前），方便前端渲染
    messages = []
    for r in reversed(rows):
        msg = {
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        if r["metadata"]:
            msg["metadata"] = r["metadata"]
        messages.append(msg)

    has_more = len(rows) == limit and len(rows) > 0

    result = {
        "status": "ok",
        "session_id": session_id,
        "session_status": session["status"],
        "messages": messages,
        "has_more": has_more,
    }
    if session["metadata"]:
        result["context"] = session["metadata"]

    return result


@router.post("/{session_id}/interrupt", summary="标记会话中断")
async def mark_interrupted(session_id: str):
    """标记会话为中断状态（前端检测到错误时调用）。"""
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE sessions SET status = 'interrupted',
                                metadata = jsonb_set(COALESCE(metadata, '{}'), '{interrupted_at}', to_jsonb(NOW()::text))
            WHERE id = $1
            """,
            session_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="会话不存在")

    return {"status": "ok", "message": "会话已标记为中断"}


@router.post("/{session_id}/resume", summary="恢复中断的会话")
async def resume_session(session_id: str):
    """恢复中断的会话，返回完整历史和上下文元数据。"""
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        session = await conn.fetchrow(
            """
            UPDATE sessions SET status = 'active',
                                last_message_at = CURRENT_TIMESTAMP,
                                metadata = jsonb_set(COALESCE(metadata, '{}'), '{resumed_at}', to_jsonb(NOW()::text))
            WHERE id = $1
            RETURNING id, title, status, message_count, metadata
            """,
            session_id,
        )
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        rows = await conn.fetch(
            """
            SELECT id, role, content, created_at
            FROM chat_history
            WHERE session_id = $1
            ORDER BY id ASC
            """,
            session_id,
        )

    messages = [
        {
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]

    result = {
        "status": "ok",
        "session": {
            "session_id": session["id"],
            "title": session["title"],
            "message_count": session["message_count"],
        },
        "messages": messages,
    }
    metadata = session["metadata"]
    if metadata:
        result["context"] = metadata if isinstance(metadata, dict) else json.loads(metadata)

    return result


@router.delete("/{session_id}", summary="删除会话")
async def delete_session(session_id: str):
    """删除会话及其聊天历史。"""
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chat_history WHERE session_id = $1", session_id)
        result = await conn.execute("DELETE FROM sessions WHERE id = $1", session_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="会话不存在")

    return {"status": "ok"}
