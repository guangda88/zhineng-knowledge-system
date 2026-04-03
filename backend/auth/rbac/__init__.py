"""简化的RBAC模块

重构后的权限控制模块，移除过度设计的功能。
"""

from .manager import RBACManager, get_rbac, reset_rbac
from .models import User
from .permissions import Permission, Role


# 导出装饰器（保持接口兼容）
def require_permission(permission: str):
    """权限检查装饰器工厂函数

    Args:
        permission: 需要的权限字符串

    Returns:
        装饰器函数

    使用示例:
        @require_permission("document:write")
        async def create_document(request: Request):
            ...
    """
    from functools import wraps

    from fastapi import HTTPException, Request, status

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从kwargs中获取request
            request: Request = kwargs.get("request")
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No request context",
                )

            # 从request中获取user（由认证中间件设置）
            user = getattr(request.state, "user", None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            # 检查权限
            rbac = get_rbac()
            if not rbac.check_permission(user, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "User",
    "Permission",
    "Role",
    "RBACManager",
    "get_rbac",
    "reset_rbac",
    "require_permission",
]
