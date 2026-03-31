"""JWT 认证中间件

提供基于 JWT 的 API 认证功能。
"""

import os
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# 安全方案
security = HTTPBearer()

# JWT 配置
JWT_PRIVATE_KEY_PATH = os.getenv("JWT_PRIVATE_KEY_PATH", "jwt_private.pem")
JWT_PUBLIC_KEY_PATH = os.getenv("JWT_PUBLIC_KEY_PATH", "jwt_public.pem")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "RS256")
JWT_EXPIRATION = int(os.getenv("JWT_EXPIRATION", "3600"))


class JWTManager:
    """JWT 令牌管理器"""

    def __init__(self):
        self._private_key = None
        self._public_key = None
        self._load_keys()

    def _load_keys(self):
        """加载 RSA 密钥对"""
        try:
            with open(JWT_PRIVATE_KEY_PATH, "rb") as f:
                self._private_key = f.read()

            with open(JWT_PUBLIC_KEY_PATH, "rb") as f:
                self._public_key = f.read()

            logger.info("JWT keys loaded successfully")
        except FileNotFoundError as e:
            logger.error(f"JWT key file not found: {e}")
            raise ValueError(
                f"JWT keys not found. Please generate keys first:\n"
                f"Private key: {JWT_PRIVATE_KEY_PATH}\n"
                f"Public key: {JWT_PUBLIC_KEY_PATH}"
            )

    def create_token(
        self,
        user_id: str,
        username: str,
        permissions: list = None,
        additional_claims: dict = None
    ) -> str:
        """创建 JWT 令牌

        Args:
            user_id: 用户ID
            username: 用户名
            permissions: 权限列表
            additional_claims: 额外的声明

        Returns:
            JWT 令牌字符串
        """
        now = datetime.utcnow()
        payload = {
            "user_id": user_id,
            "username": username,
            "iat": now,
            "exp": now + timedelta(seconds=JWT_EXPIRATION),
            "iss": "zhineng-kb",
            "permissions": permissions or [],
        }

        # 添加额外声明
        if additional_claims:
            payload.update(additional_claims)

        try:
            token = jwt.encode(
                payload,
                self._private_key,
                algorithm=JWT_ALGORITHM
            )
            logger.info(f"Token created for user: {username}")
            return token
        except Exception as e:
            logger.error(f"Failed to create token: {e}")
            raise

    def verify_token(self, token: str) -> Dict:
        """验证 JWT 令牌

        Args:
            token: JWT 令牌字符串

        Returns:
            解码后的 payload

        Raises:
            HTTPException: 令牌无效或过期
        """
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=[JWT_ALGORITHM]
            )
            logger.info(f"Token verified for user: {payload.get('username')}")
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def refresh_token(self, token: str) -> str:
        """刷新 JWT 令牌

        Args:
            token: 旧的 JWT 令牌

        Returns:
            新的 JWT 令牌
        """
        try:
            # 验证旧令牌（忽略过期）
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False}
            )

            # 创建新令牌
            new_token = self.create_token(
                user_id=payload["user_id"],
                username=payload["username"],
                permissions=payload.get("permissions", [])
            )

            logger.info(f"Token refreshed for user: {payload.get('username')}")
            return new_token

        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to refresh token"
            )


# 全局 JWT 管理器实例
jwt_manager = JWTManager()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict:
    """获取当前用户（依赖注入）

    Args:
        credentials: HTTP Bearer 凭证

    Returns:
        用户信息字典

    Raises:
        HTTPException: 认证失败
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = jwt_manager.verify_token(token)

    return {
        "user_id": payload["user_id"],
        "username": payload["username"],
        "permissions": payload.get("permissions", []),
    }


# 装饰器：要求认证
def require_auth(func):
    """要求认证的装饰器"""
    async def wrapper(*args, current_user: Dict = None, **kwargs):
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        return await func(*args, current_user=current_user, **kwargs)
    return wrapper


# 装饰器：要求特定权限
def require_permission(permission: str):
    """要求特定权限的装饰器"""
    def decorator(func):
        async def wrapper(*args, current_user: Dict = None, **kwargs):
            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            user_permissions = current_user.get("permissions", [])
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission required: {permission}"
                )

            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator
