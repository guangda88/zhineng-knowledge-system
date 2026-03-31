"""JWT 认证示例 - 如何在 API 端点中使用认证

这个文件展示了如何在 API 端点中添加 JWT 认证。
"""

import hmac
import os

from fastapi import APIRouter, Depends, HTTPException
from middleware.jwt_auth import get_current_user, require_permission
from pydantic import BaseModel

router = APIRouter(prefix="/api/v2", tags=["authenticated"])


# ========== 数据模型 ==========

class LoginRequest(BaseModel):
    username: str
    password: str


class DocumentCreate(BaseModel):
    title: str
    content: str
class RefreshRequest(BaseModel):
    token: str


# ========== 认证端点 ==========

@router.post("/auth/login")
async def login(request: LoginRequest):
    """用户登录 - 返回 JWT 令牌"""
    from middleware.jwt_auth import jwt_manager

    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_username or not admin_password:
        raise HTTPException(
            status_code=503,
            detail="Authentication not configured. Set ADMIN_USERNAME and ADMIN_PASSWORD environment variables."
        )

    if not (hmac.compare_digest(request.username.encode(), admin_username.encode())
            and hmac.compare_digest(request.password.encode(), admin_password.encode())):
        # 创建 JWT 令牌
        token = jwt_manager.create_token(
            user_id="1",
            username=request.username,
            permissions=["document:read", "document:write"]
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 3600
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/auth/refresh")
async def refresh_token(request: RefreshRequest):
    """刷新 JWT 令牌"""
    from middleware.jwt_auth import jwt_manager

    new_token = jwt_manager.refresh_token(request.token)

    return {
        "access_token": new_token,
        "token_type": "bearer"
    }


# ========== 需要认证的端点 ==========

@router.get("/user/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """获取用户资料 - 需要认证"""
    return {
        "user_id": current_user["user_id"],
        "username": current_user["username"],
        "permissions": current_user["permissions"]
    }


@router.post("/documents")
@require_permission("document:write")
async def create_document(
    document: DocumentCreate,
    current_user: dict = Depends(get_current_user)
):
    """创建文档 - 需要认证和特定权限"""
    # 创建文档逻辑
    return {
        "title": document.title,
        "content": document.content,
        "created_by": current_user["username"]
    }


@router.get("/documents/{document_id}")
async def get_document(document_id: int, current_user: dict = Depends(get_current_user)):
    """获取文档 - 需要认证"""
    # 获取文档逻辑
    return {
        "id": document_id,
        "title": "Sample Document",
        "accessed_by": current_user["username"]
    }


# ========== 可选认证端点 ==========

@router.get("/public/info")
async def public_info():
    """公开端点 - 不需要认证"""
    return {
        "message": "This is a public endpoint",
        "version": "1.0.0"
    }


# 使用示例：
#
# 1. 登录获取令牌（需先设置 ADMIN_USERNAME / ADMIN_PASSWORD 环境变量）：
#    curl -X POST http://localhost:8000/api/v2/auth/login \
#      -H "Content-Type: application/json" \
#      -d '{"username":"<admin_user>","password":"<admin_pass>"}'
#
# 2. 使用令牌访问受保护的端点：
#    curl http://localhost:8000/api/v2/user/profile \
#      -H "Authorization: Bearer <your_token>"
#
# 3. 刷新令牌：
#    curl -X POST http://localhost:8000/api/v2/auth/refresh \
#      -H "Content-Type: application/json" \
#      -d '{"token":"<your_expired_token>"}'
