"""认证中间件模块

提供FastAPI应用的认证和授权中间件。
支持JWT令牌验证、用户上下文注入和权限检查。

特性：
- JWT令牌自动验证
- 用户上下文自动注入
- 可配置的公开路由
- 请求日志记录
- 异步处理
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Set

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .jwt import JWTAuth, get_auth
from .rbac import RBACManager, User, get_rbac

logger = logging.getLogger(__name__)


@dataclass
class AuthConfig:
    """认证中间件配置

    Attributes:
        token_header: 令牌HTTP头名称
        token_prefix: 令牌前缀（如 "Bearer "）
        cookie_name: 令牌Cookie名称
        enable_cookie_auth: 是否启用Cookie认证
        enable_header_auth: 是否启用Header认证
        auto_refresh: 是否自动刷新令牌
        public_paths: 公开路径集合（不需要认证）
        public_path_prefixes: 公开路径前缀集合
        protected_path_prefixes: 受保护的路径前缀（必须认证）
        log_denied: 是否记录拒绝访问的请求
        require_auth_for_api: API路径是否需要认证
    """

    token_header: str = "Authorization"
    token_prefix: str = "Bearer "
    cookie_name: str = "access_token"
    enable_cookie_auth: bool = True
    enable_header_auth: bool = True
    auto_refresh: bool = True
    public_paths: Set[str] = frozenset(
        {
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
        }
    )
    public_path_prefixes: Set[str] = frozenset(
        {
            "/static",
            "/favicon",
        }
    )
    protected_path_prefixes: Set[str] = frozenset(
        {
            "/api",
        }
    )
    log_denied: bool = True
    require_auth_for_api: bool = True


def is_public_path(path: str, config: AuthConfig) -> bool:
    """检查路径是否为公开路径

    Args:
        path: 请求路径
        config: 认证配置

    Returns:
        是否为公开路径
    """
    # 完全匹配
    if path in config.public_paths:
        return True

    # 前缀匹配
    for prefix in config.public_path_prefixes:
        if path.startswith(prefix):
            return True

    return False


def extract_token_from_header(request: Request, config: AuthConfig) -> Optional[str]:
    """从请求头提取令牌

    Args:
        request: FastAPI请求对象
        config: 认证配置

    Returns:
        令牌字符串，不存在返回None
    """
    authorization = request.headers.get(config.token_header)
    if not authorization:
        return None

    if not authorization.startswith(config.token_prefix):
        logger.warning(f"无效的令牌格式: {authorization[:20]}...")
        return None

    return authorization[len(config.token_prefix) :]


def extract_token_from_cookie(request: Request, config: AuthConfig) -> Optional[str]:
    """从Cookie提取令牌

    Args:
        request: FastAPI请求对象
        config: 认证配置

    Returns:
        令牌字符串，不存在返回None
    """
    return request.cookies.get(config.cookie_name)


async def load_user_from_token(
    token: str,
    auth: JWTAuth,
    rbac: RBACManager,
    config: AuthConfig,
) -> Optional[User]:
    """从令牌加载用户

    Args:
        token: JWT令牌
        auth: JWT认证器
        rbac: RBAC管理器
        config: 认证配置

    Returns:
        用户对象，加载失败返回None
    """
    payload = await auth.verify_access_token(token, check_blacklist=True)
    if not payload:
        return None

    # 从RBAC系统获取完整用户信息
    user = await rbac.get_user(payload.user_id)
    if not user:
        logger.warning(f"令牌中用户不存在: {payload.user_id}")
        return None

    # 验证用户状态
    if not user.enabled:
        logger.warning(f"用户账户已禁用: {user.username}")
        return None

    # 验证角色是否匹配
    if user.role != payload.role:
        logger.warning(
            f"用户角色不匹配: {user.username}, " f"令牌: {payload.role}, 实际: {user.role}"
        )
        return None

    return user


class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件

    自动处理请求的JWT认证，将用户信息注入到请求状态中。
    支持Header和Cookie两种令牌传递方式。

    使用方式:
        app = FastAPI()
        app.add_middleware(AuthMiddleware)
    """

    def __init__(
        self,
        app: ASGIApp,
        auth: Optional[JWTAuth] = None,
        rbac: Optional[RBACManager] = None,
        config: Optional[AuthConfig] = None,
    ):
        """初始化认证中间件

        Args:
            app: ASGI应用
            auth: JWT认证器，默认使用全局实例
            rbac: RBAC管理器，默认使用全局实例
            config: 认证配置，默认使用默认配置
        """
        super().__init__(app)
        self.auth = auth or get_auth()
        self.rbac = rbac or get_rbac()
        self.config = config or AuthConfig()

        logger.info("认证中间件已初始化")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """处理请求

        Args:
            request: FastAPI请求对象
            call_next: 下一个中间件/路由处理器

        Returns:
            HTTP响应
        """
        path = request.url.path

        # 公开路径直接放行
        if is_public_path(path, self.config):
            return await call_next(request)

        # 尝试提取令牌
        token: Optional[str] = None

        if self.config.enable_header_auth:
            token = extract_token_from_header(request, self.config)

        if not token and self.config.enable_cookie_auth:
            token = extract_token_from_cookie(request, self.config)

        # 没有令牌，设置匿名用户
        if not token:
            await self._set_anonymous_user(request)
            if self.config.log_denied:
                logger.info(f"未认证请求: {path}")

            # 检查是否是需要认证的受保护路径
            if self._is_protected_path(path):
                return Response(
                    content='{"error": "authentication_required", "message": "此端点需要认证"}',
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    media_type="application/json",
                )
            # 公开路径继续处理
            return await call_next(request)

        # 验证令牌并加载用户
        user = await load_user_from_token(token, self.auth, self.rbac, self.config)

        if not user:
            await self._set_anonymous_user(request)
            if self.config.log_denied:
                logger.warning(f"无效令牌: {path}")
            # 令牌无效，返回401
            return Response(
                content='{"error": "invalid_token", "message": "无效或过期的访问令牌"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
            )

        # 注入用户到请求状态
        await self._set_user_context(request, user, token)

        # 处理请求
        response = await call_next(request)

        # 自动刷新令牌
        if self.config.auto_refresh:
            response = await self._handle_token_refresh(request, response, user)

        return response

    async def _set_user_context(
        self,
        request: Request,
        user: User,
        token: str,
    ) -> None:
        """设置用户上下文到请求状态

        Args:
            request: FastAPI请求对象
            user: 用户对象
            token: 令牌字符串
        """
        request.state.user = user
        request.state.token = token
        request.state.authenticated = True

        # 添加请求日志
        logger.debug(f"用户认证成功: {user.username} ({user.role}) - {request.url.path}")

    async def _set_anonymous_user(self, request: Request) -> None:
        """设置匿名用户上下文

        Args:
            request: FastAPI请求对象
        """
        request.state.user = None
        request.state.token = None
        request.state.authenticated = False

    def _is_protected_path(self, path: str) -> bool:
        """检查路径是否需要认证

        Args:
            path: 请求路径

        Returns:
            是否需要认证
        """
        # 检查是否在受保护的路径前缀下
        for prefix in self.config.protected_path_prefixes:
            if path.startswith(prefix):
                return True
        return False

    async def _handle_token_refresh(
        self,
        request: Request,
        response: Response,
        user: User,
    ) -> Response:
        """处理令牌自动刷新

        Args:
            request: FastAPI请求对象
            response: HTTP响应
            user: 当前用户

        Returns:
            可能包含新令牌的响应
        """
        token = getattr(request.state, "token", None)
        if not token:
            return response

        payload = self.auth.decode_token(token)
        if not payload:
            return response

        # 检查是否即将过期（剩余时间小于5分钟）
        expires_in = payload.expires_in()
        if expires_in < 300 and expires_in > 0:
            new_token = self.auth.create_access_token(
                user_id=user.id,
                username=user.username,
                role=user.role,
                permissions=user.permissions,
            )

            # 在响应头中返回新令牌
            response.headers["X-New-Access-Token"] = new_token
            response.headers["X-Token-Expires-In"] = str(
                self.auth.config.access_token_expire_minutes * 60
            )

            # 如果使用Cookie，更新Cookie
            if self.config.enable_cookie_auth:
                response.set_cookie(
                    key=self.config.cookie_name,
                    value=new_token,
                    max_age=self.auth.config.access_token_expire_minutes * 60,
                    httponly=True,
                    secure=True,  # 生产环境应启用
                    samesite="lax",
                )

            logger.debug(f"为用户 {user.username} 自动刷新令牌")

        return response


class RefreshTokenMiddleware(BaseHTTPMiddleware):
    """刷新令牌中间件

    专门处理 /auth/refresh 端点的中间件。
    从Cookie或请求体中提取刷新令牌并返回新的令牌对。
    """

    def __init__(
        self,
        app: ASGIApp,
        auth: Optional[JWTAuth] = None,
        refresh_cookie_name: str = "refresh_token",
    ):
        """初始化刷新令牌中间件

        Args:
            app: ASGI应用
            auth: JWT认证器
            refresh_cookie_name: 刷新令牌Cookie名称
        """
        super().__init__(app)
        self.auth = auth or get_auth()
        self.refresh_cookie_name = refresh_cookie_name

    def _build_token_response(self, token_pair) -> Response:
        response_data = {
            "access_token": token_pair.access_token,
            "refresh_token": token_pair.refresh_token,
            "expires_in": token_pair.expires_in,
            "token_type": "Bearer",
        }
        response = Response(
            content=json.dumps(response_data),
            status_code=status.HTTP_200_OK,
            media_type="application/json",
        )
        response.set_cookie(
            key="access_token",
            value=token_pair.access_token,
            max_age=token_pair.expires_in,
            httponly=True,
            secure=True,
            samesite="lax",
        )
        response.set_cookie(
            key=self.refresh_cookie_name,
            value=token_pair.refresh_token,
            max_age=60 * 60 * 24 * 7,
            httponly=True,
            secure=True,
            samesite="lax",
        )
        return response

    async def _extract_refresh_token(self, request: Request) -> Optional[str]:
        token = request.cookies.get(self.refresh_cookie_name)
        if not token:
            try:
                body = await request.json()
                token = body.get("refresh_token")
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.debug(f"No refresh_token in request body: {e}")
        return token

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path != "/auth/refresh":
            return await call_next(request)

        refresh_token = await self._extract_refresh_token(request)
        if not refresh_token:
            return Response(
                content='{"error": "missing_refresh_token"}',
                status_code=status.HTTP_400_BAD_REQUEST,
                media_type="application/json",
            )

        token_pair = await self.auth.refresh_access_token(refresh_token)
        if not token_pair:
            return Response(
                content='{"error": "invalid_refresh_token"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
            )

        return self._build_token_response(token_pair)


class LogoutMiddleware(BaseHTTPMiddleware):
    """登出中间件

    处理用户登出请求，将当前令牌加入黑名单。
    """

    def __init__(
        self,
        app: ASGIApp,
        auth: Optional[JWTAuth] = None,
    ):
        """初始化登出中间件

        Args:
            app: ASGI应用
            auth: JWT认证器
        """
        super().__init__(app)
        self.auth = auth or get_auth()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """处理请求

        Args:
            request: FastAPI请求对象
            call_next: 下一个处理器

        Returns:
            HTTP响应
        """
        # 只处理登出端点
        if request.url.path != "/auth/logout":
            return await call_next(request)

        # 从请求状态获取用户和令牌
        user: Optional[User] = getattr(request.state, "user", None)
        token: Optional[str] = getattr(request.state, "token", None)

        if user and token:
            payload = self.auth.decode_token(token)
            if payload:
                await self.auth.revoke_token(payload.jti, payload.exp)
                logger.info(f"用户登出: {user.username}")

        # 清除Cookie
        response = Response(
            content='{"message": "logged_out"}',
            status_code=status.HTTP_200_OK,
            media_type="application/json",
        )

        response.delete_cookie(key="access_token")
        response.delete_cookie(key="refresh_token")

        return response


# ========== 便捷函数 ==========


def get_current_user(request: Request) -> Optional[User]:
    """获取当前请求的认证用户

    Args:
        request: FastAPI请求对象

    Returns:
        当前用户，未认证返回None
    """
    return getattr(request.state, "user", None)


def get_current_user_required(request: Request) -> User:
    """获取当前请求的认证用户（必须认证）

    Args:
        request: FastAPI请求对象

    Returns:
        当前用户

    Raises:
        HTTPException: 未认证时抛出401
    """
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要认证",
        )
    return user


def is_authenticated(request: Request) -> bool:
    """检查请求是否已认证

    Args:
        request: FastAPI请求对象

    Returns:
        是否已认证
    """
    return getattr(request.state, "authenticated", False)


def get_current_token(request: Request) -> Optional[str]:
    """获取当前请求的令牌

    Args:
        request: FastAPI请求对象

    Returns:
        令牌字符串，未认证返回None
    """
    return getattr(request.state, "token", None)


# ========== FastAPI依赖 ==========


async def get_current_user_dependency(request: Request) -> Optional[User]:
    """FastAPI依赖：获取当前用户

    Example:
        @app.get("/profile")
        async def profile(user: Optional[User] = Depends(get_current_user_dependency)):
            ...
    """
    return get_current_user(request)


async def get_authenticated_user(request: Request) -> User:
    """FastAPI依赖：获取认证用户（必须认证）

    Example:
        @app.get("/profile")
        async def profile(user: User = Depends(get_authenticated_user)):
            ...
    """
    return get_current_user_required(request)
