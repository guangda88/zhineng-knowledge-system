"""JWT 认证端点 — 使用统一的 auth 模块

登录/刷新/受保护端点，统一走 backend.auth 体系。
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.middleware import get_authenticated_user
from backend.auth.rbac import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["authenticated"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    token: str


class DocumentCreate(BaseModel):
    title: str
    content: str
    category: str = "通用"


@router.post("/auth/login")
async def login(request: LoginRequest):
    """用户登录 - 返回 JWT 令牌"""
    from backend.auth.jwt import get_auth

    auth = get_auth()

    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")

    import hmac

    if not admin_username or not admin_password:
        raise HTTPException(
            status_code=503,
            detail="Authentication not configured. Set ADMIN_USERNAME and ADMIN_PASSWORD.",
        )

    if hmac.compare_digest(
        request.username.encode(), admin_username.encode()
    ) and hmac.compare_digest(request.password.encode(), admin_password.encode()):
        token_pair = await auth.create_token_pair(
            user_id="1",
            username=request.username,
            role="admin",
            permissions=["document:read", "document:write"],
        )

        return {
            "access_token": token_pair.access_token,
            "refresh_token": token_pair.refresh_token,
            "token_type": "bearer",
            "expires_in": token_pair.expires_in,
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/auth/refresh")
async def refresh_token(request: RefreshRequest):
    """刷新 JWT 令牌"""
    from backend.auth.jwt import get_auth

    auth = get_auth()
    token_pair = await auth.refresh_access_token(request.token)

    if not token_pair:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    return {"access_token": token_pair.access_token, "token_type": "bearer"}


@router.get("/user/profile")
async def get_profile(user: User = Depends(get_authenticated_user)):
    """获取用户资料 - 需要认证"""
    return {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "permissions": user.permissions,
    }


@router.post("/documents")
async def create_document(
    document: DocumentCreate, user: User = Depends(get_authenticated_user)
):
    """创建文档 - 需要认证"""
    from backend.core.database import get_db_pool

    pool = await get_db_pool()
    row = await pool.fetchrow(
        """INSERT INTO documents (title, content, category, created_at)
           VALUES ($1, $2, $3, NOW())
           RETURNING id, title, category, created_at""",
        document.title,
        document.content,
        document.category,
    )
    return {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "created_by": user.username,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: int, user: User = Depends(get_authenticated_user)
):
    """获取文档 - 需要认证"""
    from backend.core.database import get_db_pool

    pool = await get_db_pool()
    row = await pool.fetchrow(
        "SELECT id, title, content, category, tags, created_at " "FROM documents WHERE id = $1",
        document_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "category": row["category"],
        "tags": row["tags"],
        "accessed_by": user.username,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/public/info")
async def public_info():
    """公开端点 - 不需要认证"""
    return {"message": "This is a public endpoint", "version": "1.0.0"}
