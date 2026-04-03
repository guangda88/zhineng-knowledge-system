# -*- coding: utf-8 -*-
"""
CSRF 保护中间件
CSRF Protection Middleware

实现CSRF Token生成和验证机制，防止跨站请求伪造攻击
"""

import logging
import secrets
from typing import Callable, Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadSignature, URLSafeTimedSerializer

logger = logging.getLogger(__name__)


class CSRFTokenError(Exception):
    """CSRF Token错误"""

    pass


class CSRFProtectionMiddleware:
    """
    CSRF保护中间件

    功能:
    - 生成CSRF Token
    - 验证CSRF Token
    - Token过期控制
    - 密钥签名保护
    """

    def __init__(
        self,
        secret_key: Optional[str] = None,
        max_age: int = 3600,  # Token有效期：1小时
        token_header: str = "X-CSRF-Token",
        cookie_name: str = "csrf_token",
    ):
        """
        初始化CSRF保护中间件

        Args:
            secret_key: 签名密钥，如果未提供则自动生成
            max_age: Token最大有效期（秒）
            token_header: CSRF Token的HTTP头名称
            cookie_name: CSRF Token的Cookie名称
        """
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.max_age = max_age
        self.token_header = token_header
        self.cookie_name = cookie_name

        # 使用itsdangerous进行安全的Token签名
        self.serializer = URLSafeTimedSerializer(self.secret_key, salt="csrf-protection-salt")

        logger.info("CSRF Protection Middleware initialized")

    def generate_token(self) -> str:
        """
        生成新的CSRF Token

        Returns:
            CSRF Token字符串
        """
        random_token = secrets.token_urlsafe(32)
        signed_token = self.serializer.dumps(random_token)
        return signed_token

    def validate_token(self, token: str, max_age: Optional[int] = None) -> bool:
        """
        验证CSRF Token

        Args:
            token: 待验证的Token
            max_age: Token最大有效期（秒），默认使用初始化时的设置

        Returns:
            验证是否通过
        """
        if not token:
            return False

        try:
            # 验证签名和有效期
            max_age = max_age or self.max_age
            self.serializer.loads(token, max_age=max_age)
            return True
        except BadSignature:
            logger.warning("CSRF token signature verification failed")
            return False
        except Exception as e:
            logger.warning(f"CSRF token validation error: {e}")
            return False

    def set_csrf_cookie(self, response, token: str, secure: bool = False):
        """
        在响应中设置CSRF Cookie

        Args:
            response: FastAPI响应对象
            token: CSRF Token
            secure: 是否使用安全Cookie（HTTPS）
        """
        response.set_cookie(
            key=self.cookie_name,
            value=token,
            max_age=self.max_age,
            httponly=False,  # CSRF token需要被JavaScript读取
            secure=secure,
            samesite="lax",
        )

    def get_token_from_header(self, request: Request) -> Optional[str]:
        """
        从请求头获取CSRF Token

        Args:
            request: FastAPI请求对象

        Returns:
            CSRF Token或None
        """
        return request.headers.get(self.token_header)

    def get_token_from_cookie(self, request: Request) -> Optional[str]:
        """
        从Cookie获取CSRF Token

        Args:
            request: FastAPI请求对象

        Returns:
            CSRF Token或None
        """
        return request.cookies.get(self.cookie_name)

    async def verify_csrf_token(self, request: Request, skip_methods: Optional[set] = None) -> bool:
        """
        验证请求的CSRF Token

        Args:
            request: FastAPI请求对象
            skip_methods: 跳过CSRF验证的HTTP方法集合（如{"GET", "HEAD", "OPTIONS"}）

        Returns:
            验证是否通过

        Raises:
            HTTPException: Token验证失败
        """
        # 默认跳过安全的HTTP方法
        if skip_methods is None:
            skip_methods = {"GET", "HEAD", "OPTIONS"}

        # 跳过安全的HTTP方法
        if request.method in skip_methods:
            return True

        # 从请求头获取Token
        header_token = self.get_token_from_header(request)

        # 从Cookie获取Token
        cookie_token = self.get_token_from_cookie(request)

        # 验证Token
        if not header_token or not cookie_token:
            logger.warning(f"CSRF token missing for {request.method} {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing",
            )

        if not self.validate_token(header_token):
            logger.warning(f"Invalid CSRF token for {request.method} {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token",
            )

        if header_token != cookie_token:
            logger.warning(f"CSRF token mismatch for {request.method} {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token mismatch",
            )

        return True

    def create_csrf_dependency(self, skip_methods: Optional[set] = None) -> Callable:
        """
        创建FastAPI依赖函数

        Args:
            skip_methods: 跳过CSRF验证的HTTP方法集合

        Returns:
            FastAPI依赖函数
        """

        async def csrf_protected(request: Request):
            """CSRF保护依赖函数"""
            await self.verify_csrf_token(request, skip_methods)
            return True

        return csrf_protected


# 全局CSRF保护实例
csrf_protection = CSRFProtectionMiddleware()


# 便捷函数
def generate_csrf_token() -> str:
    """生成CSRF Token"""
    return csrf_protection.generate_token()


def validate_csrf_token(token: str, max_age: Optional[int] = None) -> bool:
    """验证CSRF Token"""
    return csrf_protection.validate_token(token, max_age)


def csrf_protected(skip_methods: Optional[set] = None) -> Callable:
    """
    CSRF保护依赖函数

    Args:
        skip_methods: 跳过CSRF验证的HTTP方法集合

    Returns:
        FastAPI依赖函数
    """
    return csrf_protection.create_csrf_dependency(skip_methods)


__all__ = [
    "CSRFProtectionMiddleware",
    "CSRFTokenError",
    "csrf_protection",
    "generate_csrf_token",
    "validate_csrf_token",
    "csrf_protected",
]
