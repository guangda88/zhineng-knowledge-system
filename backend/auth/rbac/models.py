"""简化的用户和角色模型

基于实际需求，只保留必要的用户信息。
"""

from dataclasses import dataclass, field
from typing import Optional, Set


@dataclass
class User:
    """用户信息数据结构（简化版）

    只保留实际使用的字段，移除未使用的复杂功能。

    Attributes:
        id: 用户唯一标识符
        username: 用户名
        role: 用户角色
        permissions: 用户额外权限集合（除角色权限外）
        enabled: 账户是否启用
        email: 用户邮箱（可选）
    """

    id: str
    username: str
    role: str
    permissions: Set[str] = field(default_factory=set)
    enabled: bool = True
    email: Optional[str] = None

    def has_permission(self, permission: str, role_permissions: Set[str]) -> bool:
        """检查用户是否拥有指定权限

        Args:
            permission: 要检查的权限字符串
            role_permissions: 用户角色的权限集合

        Returns:
            是否拥有权限
        """
        if not self.enabled:
            return False

        # 检查用户直接权限
        if permission in self.permissions:
            return True

        # 检查角色权限
        if permission in role_permissions:
            return True

        return False

    def has_any_permission(self, permissions: set, role_permissions: Set[str]) -> bool:
        """检查是否拥有任意一个权限

        Args:
            permissions: 权限集合
            role_permissions: 用户角色的权限集合

        Returns:
            是否拥有至少一个权限
        """
        return any(self.has_permission(p.value, role_permissions) for p in permissions)

    def has_role(self, role: str) -> bool:
        """检查用户是否拥有指定角色

        Args:
            role: 要检查的角色

        Returns:
            是否拥有该角色
        """
        if not self.enabled:
            return False
        return self.role == role
