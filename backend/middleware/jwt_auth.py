"""JWT 认证模块 — 已废弃

此模块已被 backend.auth.jwt 和 backend.auth.middleware 替代。
新代码请使用:
  - backend.auth.jwt (JWTAuth, token 创建/验证)
  - backend.auth.middleware (AuthMiddleware, get_authenticated_user)
  - backend.auth.rbac (RBACManager, User, permissions)

保留此文件仅为向后兼容，如有旧引用请迁移到 backend.auth。
"""

import logging

logger = logging.getLogger(__name__)

logger.warning(
    "backend.middleware.jwt_auth is DEPRECATED. "
    "Use backend.auth.jwt and backend.auth.middleware instead."
)
