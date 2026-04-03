"""简化的RBAC管理器

提供基础的权限管理功能，移除未使用的复杂特性。
"""

import logging
from typing import Dict, Optional, Set

from .models import User
from .permissions import ROLE_PERMISSIONS, Role

logger = logging.getLogger(__name__)


class RBACManager:
    """简化的RBAC管理器

    提供权限检查的核心功能，不包含持久化。
    实际的用户存储应该在外部实现（如数据库）。
    """

    def __init__(self):
        """初始化RBAC管理器"""
        self._users: Dict[str, User] = {}
        self._role_permissions = ROLE_PERMISSIONS

    def add_user(self, user: User) -> None:
        """添加用户

        Args:
            user: 用户对象
        """
        self._users[user.id] = user
        logger.debug(f"User added: {user.username}")

    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户

        Args:
            user_id: 用户ID

        Returns:
            用户对象，不存在时返回None
        """
        return self._users.get(user_id)

    def get_role_permissions(self, role: str) -> Set[str]:
        """获取角色的权限集合

        Args:
            role: 角色名称

        Returns:
            权限字符串集合
        """
        # 尝试将字符串转换为Role枚举
        try:
            role_enum = Role(role)
            permissions = self._role_permissions.get(role_enum, set())
            return {p.value for p in permissions}
        except ValueError:
            # 未知角色，返回空权限
            logger.warning(f"Unknown role: {role}")
            return set()

    def check_permission(self, user: User, permission: str, **context) -> bool:
        """检查用户是否拥有指定权限

        Args:
            user: 用户对象
            permission: 权限字符串
            **context: 额外的上下文信息（未使用，保留接口兼容性）

        Returns:
            是否拥有权限
        """
        role_permissions = self.get_role_permissions(user.role)
        return user.has_permission(permission, role_permissions)

    def create_user(
        self,
        user_id: str,
        username: str,
        role: str = "user",
        permissions: Optional[Set[str]] = None,
        enabled: bool = True,
        email: Optional[str] = None,
    ) -> User:
        """创建新用户

        Args:
            user_id: 用户ID
            username: 用户名
            role: 角色（默认为user）
            permissions: 额外权限集合
            enabled: 是否启用
            email: 邮箱

        Returns:
            创建的用户对象
        """
        user = User(
            id=user_id,
            username=username,
            role=role,
            permissions=permissions or set(),
            enabled=enabled,
            email=email,
        )
        self.add_user(user)
        return user


# 全局单例
_rbac_manager: Optional[RBACManager] = None


def get_rbac() -> RBACManager:
    """获取全局RBAC管理器实例

    Returns:
        RBAC管理器单例
    """
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
        logger.info("Global RBAC manager initialized")
    return _rbac_manager


def reset_rbac() -> None:
    """重置全局RBAC管理器（主要用于测试）"""
    global _rbac_manager
    _rbac_manager = None
    logger.debug("RBAC manager reset")
