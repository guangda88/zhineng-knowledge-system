"""认证与授权模块

提供完整的JWT认证和RBAC权限控制功能。

模块组成:
    - jwt.py: JWT令牌管理（RS256算法、令牌黑名单、刷新机制）
    - rbac.py: 基于角色的访问控制（用户、角色、权限管理）
    - middleware.py: FastAPI认证中间件

使用示例:
    ```python
    from backend.auth import get_auth, get_rbac
    from backend.auth.middleware import AuthMiddleware, get_authenticated_user
    from backend.auth.rbac import require_permission, Permission

    # 初始化FastAPI应用
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    # 创建令牌对
    auth = get_auth()
    token_pair = await auth.create_token_pair("user123", "alice", "admin")

    # 使用权限装饰器
    @app.get("/documents")
    @require_permission(Permission.DOCUMENT_READ.value)
    async def list_documents(user: User = Depends(get_authenticated_user)):
        return {"documents": [...]}

    # 使用依赖注入
    @app.delete("/documents/{doc_id}")
    async def delete_document(
        doc_id: str,
        user: User = Depends(get_authenticated_user),
    ):
        # 权限在中间件中已验证
        pass
    ```

配置环境变量:
    JWT_PRIVATE_KEY: RSA私钥PEM格式
    JWT_PUBLIC_KEY: RSA公钥PEM格式
    JWT_ISSUER: 令牌签发者（默认: zhineng-kb）
    JWT_ACCESS_EXPIRE_MINUTES: 访问令牌有效期（默认: 30）
    JWT_REFRESH_EXPIRE_DAYS: 刷新令牌有效期（默认: 7）
"""

from .jwt import (
    TokenType,
    TokenPayload,
    TokenPair,
    TokenBlacklist,
    AuthConfig as JWTAuthConfig,
    JWTAuth,
    get_auth,
    reset_auth,
)

from .rbac import (
    Permission,
    Role,
    PermissionCondition,
    User,
    UserRepository,
    InMemoryUserRepository,
    RBACManager,
    get_rbac,
    set_rbac,
    reset_rbac,
    require_permission,
    require_any_permission,
    require_role,
    RequirePermission,
    ROLE_PERMISSIONS,
    ROLE_HIERARCHY,
)

from .middleware import (
    AuthConfig,
    AuthMiddleware,
    RefreshTokenMiddleware,
    LogoutMiddleware,
    get_current_user,
    get_current_user_required,
    is_authenticated,
    get_current_token,
    get_current_user_dependency,
    get_authenticated_user,
)

__all__ = [
    # JWT模块
    "TokenType",
    "TokenPayload",
    "TokenPair",
    "TokenBlacklist",
    "JWTAuthConfig",
    "JWTAuth",
    "get_auth",
    "reset_auth",
    # RBAC模块
    "Permission",
    "Role",
    "PermissionCondition",
    "User",
    "UserRepository",
    "InMemoryUserRepository",
    "RBACManager",
    "get_rbac",
    "set_rbac",
    "reset_rbac",
    "require_permission",
    "require_any_permission",
    "require_role",
    "RequirePermission",
    "ROLE_PERMISSIONS",
    "ROLE_HIERARCHY",
    # 中间件模块
    "AuthConfig",
    "AuthMiddleware",
    "RefreshTokenMiddleware",
    "LogoutMiddleware",
    "get_current_user",
    "get_current_user_required",
    "is_authenticated",
    "get_current_token",
    "get_current_user_dependency",
    "get_authenticated_user",
]
