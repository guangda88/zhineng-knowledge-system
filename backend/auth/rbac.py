"""基于角色的访问控制（RBAC）模块

提供完整的RBAC功能，包括用户、角色、权限管理以及访问控制检查。
支持细粒度的权限控制和灵活的角色继承。

特性：
- 角色继承机制
- 细粒度权限控制
- 异步友好的设计
- 装饰器式权限检查
- 批量权限验证
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)

from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Permission(Enum):
    """权限枚举定义

    系统中所有可用权限的集中定义。
    采用 <资源>:<操作> 的命名约定。
    """

    # ========== 文档相关 ==========
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_SHARE = "document:share"
    DOCUMENT_EXPORT = "document:export"

    # ========== 查询相关 ==========
    QUERY_EXECUTE = "query:execute"
    QUERY_ADVANCED = "query:advanced"
    QUERY_HISTORY = "query:history"
    QUERY_SAVE = "query:save"

    # ========== 推理相关 ==========
    REASONING_EXECUTE = "reasoning:execute"
    REASONING_GRAPH = "reasoning:graph"
    REASONING_TRACE = "reasoning:trace"
    REASONING_CONFIG = "reasoning:config"

    # ========== 知识图谱相关 ==========
    GRAPH_READ = "graph:read"
    GRAPH_WRITE = "graph:write"
    GRAPH_EDIT = "graph:edit"
    GRAPH_MERGE = "graph:merge"

    # ========== 系统相关 ==========
    SYSTEM_METRICS = "system:metrics"
    SYSTEM_HEALTH = "system:health"
    SYSTEM_LOGS = "system:logs"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_BACKUP = "system:backup"
    SYSTEM_RESTORE = "system:restore"

    # ========== 用户管理 ==========
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    USER_MANAGE_ROLES = "user:manage_roles"

    # ========== 领域管理 ==========
    DOMAIN_READ = "domain:read"
    DOMAIN_CREATE = "domain:create"
    DOMAIN_UPDATE = "domain:update"
    DOMAIN_DELETE = "domain:delete"

    # ========== API相关 ==========
    API_READ = "api:read"
    API_WRITE = "api:write"
    API_KEY_MANAGE = "api:key_manage"

    # ========== 通知相关 ==========
    NOTIFICATION_SEND = "notification:send"
    NOTIFICATION_READ = "notification:read"


class Role(Enum):
    """角色枚举定义

    系统中所有可用角色的集中定义。
    角色按权限等级从高到低排列。
    """

    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"
    GUEST = "guest"


@dataclass
class PermissionCondition:
    """权限条件

    用于实现更细粒度的权限控制，支持基于条件的访问判断。

    Attributes:
        resource_id: 资源ID，用于特定资源的权限控制
        attributes: 额外属性键值对
    """

    resource_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    def matches(self, **kwargs) -> bool:
        """检查条件是否匹配

        Args:
            **kwargs: 要匹配的键值对

        Returns:
            是否所有条件都匹配
        """
        for key, value in kwargs.items():
            if key == "resource_id" and self.resource_id is not None:
                if self.resource_id != value:
                    return False
            elif key in self.attributes:
                if self.attributes[key] != value:
                    return False
        return True


@dataclass
class User:
    """用户信息数据结构

    Attributes:
        id: 用户唯一标识符
        username: 用户名
        email: 用户邮箱
        role: 用户角色
        permissions: 用户额外权限集合（除角色权限外）
        enabled: 账户是否启用
        conditions: 权限条件映射
        metadata: 额外的用户元数据
    """

    id: str
    username: str
    role: str
    permissions: Set[str] = field(default_factory=set)
    enabled: bool = True
    email: Optional[str] = None
    conditions: Dict[str, PermissionCondition] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_permission(
        self, permission: str, rbac_manager: "RBACManager", **context
    ) -> bool:
        """检查用户是否拥有指定权限

        Args:
            permission: 要检查的权限字符串
            rbac_manager: RBAC管理器实例
            **context: 权限检查上下文

        Returns:
            是否拥有权限
        """
        if not self.enabled:
            return False

        # 检查用户直接权限
        if permission in self.permissions:
            # 检查权限条件
            if permission in self.conditions:
                return self.conditions[permission].matches(**context)
            return True

        # 检查角色权限（包括继承的权限）
        role_permissions = rbac_manager.get_role_permissions(self.role)
        if permission in role_permissions:
            if permission in self.conditions:
                return self.conditions[permission].matches(**context)
            return True

        return False

    def has_any_permission(
        self, permissions: List[str], rbac_manager: "RBACManager", **context
    ) -> bool:
        """检查是否拥有任意一个权限

        Args:
            permissions: 权限列表
            rbac_manager: RBAC管理器实例
            **context: 权限检查上下文

        Returns:
            是否拥有至少一个权限
        """
        return any(
            self.has_permission(p, rbac_manager, **context) for p in permissions
        )

    def has_all_permissions(
        self, permissions: List[str], rbac_manager: "RBACManager", **context
    ) -> bool:
        """检查是否拥有所有权限

        Args:
            permissions: 权限列表
            rbac_manager: RBAC管理器实例
            **context: 权限检查上下文

        Returns:
            是否拥有所有权限
        """
        return all(
            self.has_permission(p, rbac_manager, **context) for p in permissions
        )

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

    def add_permission(self, permission: str) -> None:
        """添加权限

        Args:
            permission: 要添加的权限
        """
        self.permissions.add(permission)

    def remove_permission(self, permission: str) -> None:
        """移除权限

        Args:
            permission: 要移除的权限
        """
        self.permissions.discard(permission)

    def set_permission_condition(
        self, permission: str, condition: PermissionCondition
    ) -> None:
        """设置权限条件

        Args:
            permission: 权限字符串
            condition: 权限条件
        """
        self.conditions[permission] = condition

    def remove_permission_condition(self, permission: str) -> None:
        """移除权限条件

        Args:
            permission: 权限字符串
        """
        self.conditions.pop(permission, None)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            包含用户信息的字典
        """
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "permissions": list(self.permissions),
            "enabled": self.enabled,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        """从字典创建用户实例

        Args:
            data: 包含用户信息的字典

        Returns:
            User实例
        """
        return cls(
            id=data["id"],
            username=data["username"],
            role=data.get("role", Role.USER.value),
            permissions=set(data.get("permissions", [])),
            enabled=data.get("enabled", True),
            email=data.get("email"),
            metadata=data.get("metadata", {}),
        )


# ========== 角色继承配置 ==========
# 子角色可以继承父角色的权限
ROLE_HIERARCHY: Dict[str, Optional[str]] = {
    Role.ADMIN.value: None,  # 最高级别
    Role.OPERATOR.value: Role.ADMIN.value,
    Role.USER.value: Role.OPERATOR.value,
    Role.GUEST.value: Role.USER.value,
}

# 基础角色权限映射
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    Role.ADMIN.value: {
        # 管理员拥有所有权限
        p.value for p in Permission
    },
    Role.OPERATOR.value: {
        # 运维人员权限
        Permission.DOCUMENT_READ.value,
        Permission.DOCUMENT_WRITE.value,
        Permission.QUERY_EXECUTE.value,
        Permission.QUERY_ADVANCED.value,
        Permission.QUERY_HISTORY.value,
        Permission.REASONING_EXECUTE.value,
        Permission.REASONING_GRAPH.value,
        Permission.GRAPH_READ.value,
        Permission.SYSTEM_METRICS.value,
        Permission.SYSTEM_HEALTH.value,
        Permission.SYSTEM_LOGS.value,
        Permission.DOMAIN_READ.value,
        Permission.DOMAIN_CREATE.value,
        Permission.DOMAIN_UPDATE.value,
        Permission.API_READ.value,
        Permission.NOTIFICATION_SEND.value,
        Permission.NOTIFICATION_READ.value,
    },
    Role.USER.value: {
        # 普通用户权限
        Permission.DOCUMENT_READ.value,
        Permission.QUERY_EXECUTE.value,
        Permission.QUERY_HISTORY.value,
        Permission.QUERY_SAVE.value,
        Permission.REASONING_EXECUTE.value,
        Permission.GRAPH_READ.value,
        Permission.API_READ.value,
        Permission.NOTIFICATION_READ.value,
    },
    Role.GUEST.value: {
        # 访客权限
        Permission.DOCUMENT_READ.value,
    },
}


class UserRepository(ABC):
    """用户仓储抽象接口

    定义用户持久化操作的标准接口。
    实际实现可以基于数据库、缓存或其他存储方式。
    """

    @abstractmethod
    async def get(self, user_id: str) -> Optional[User]:
        """获取用户

        Args:
            user_id: 用户ID

        Returns:
            用户实例，不存在返回None
        """
        pass

    @abstractmethod
    async def save(self, user: User) -> bool:
        """保存用户

        Args:
            user: 用户实例

        Returns:
            是否保存成功
        """
        pass

    @abstractmethod
    async def delete(self, user_id: str) -> bool:
        """删除用户

        Args:
            user_id: 用户ID

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    async def list_all(self) -> List[User]:
        """列出所有用户

        Returns:
            用户列表
        """
        pass

    @abstractmethod
    async def find_by_username(self, username: str) -> Optional[User]:
        """根据用户名查找用户

        Args:
            username: 用户名

        Returns:
            用户实例，不存在返回None
        """
        pass


class InMemoryUserRepository(UserRepository):
    """内存用户仓储实现

    用于开发测试环境，生产环境应使用数据库实现。
    """

    def __init__(self):
        """初始化内存仓储"""
        self._users: Dict[str, User] = {}
        self._username_index: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(self, user_id: str) -> Optional[User]:
        """获取用户"""
        async with self._lock:
            return self._users.get(user_id)

    async def save(self, user: User) -> bool:
        """保存用户"""
        async with self._lock:
            self._users[user.id] = user
            self._username_index[user.username] = user.id
            return True

    async def delete(self, user_id: str) -> bool:
        """删除用户"""
        async with self._lock:
            user = self._users.get(user_id)
            if user:
                del self._users[user_id]
                self._username_index.pop(user.username, None)
                return True
            return False

    async def list_all(self) -> List[User]:
        """列出所有用户"""
        async with self._lock:
            return list(self._users.values())

    async def find_by_username(self, username: str) -> Optional[User]:
        """根据用户名查找用户"""
        async with self._lock:
            user_id = self._username_index.get(username)
            if user_id:
                return self._users.get(user_id)
            return None


class RBACManager:
    """RBAC管理器

    管理用户、角色和权限的核心类。
    支持角色继承、权限缓存和异步操作。

    Example:
        >>> rbac = RBACManager()
        >>> await rbac.create_user("user123", "alice", Role.USER.value)
        >>> user = await rbac.get_user("user123")
        >>> has_perm = await rbac.check_permission(user, Permission.DOCUMENT_READ.value)
    """

    def __init__(
        self,
        user_repository: Optional[UserRepository] = None,
        role_permissions: Optional[Dict[str, Set[str]]] = None,
        role_hierarchy: Optional[Dict[str, Optional[str]]] = None,
    ):
        """初始化RBAC管理器

        Args:
            user_repository: 用户仓储，默认使用内存实现
            role_permissions: 角色权限映射
            role_hierarchy: 角色继承配置
        """
        self._user_repo = user_repository or InMemoryUserRepository()
        self._role_permissions = role_permissions or ROLE_PERMISSIONS.copy()
        self._role_hierarchy = role_hierarchy or ROLE_HIERARCHY.copy()
        self._permission_cache: Dict[str, Set[str]] = {}

        # 初始化默认用户
        asyncio.create_task(self._initialize_default_users())

    async def _initialize_default_users(self) -> None:
        """初始化默认用户"""
        # 默认管理员
        admin = User(
            id="admin",
            username="admin",
            email="admin@zhineng.kb",
            role=Role.ADMIN.value,
        )
        await self._user_repo.save(admin)

        # 默认访客
        guest = User(
            id="guest",
            username="guest",
            role=Role.GUEST.value,
        )
        await self._user_repo.save(guest)

        logger.info("默认用户初始化完成")

    def get_role_permissions(self, role: str) -> Set[str]:
        """获取角色的所有权限（包括继承的权限）

        Args:
            role: 角色名称

        Returns:
            权限集合
        """
        # 检查缓存
        if role in self._permission_cache:
            return self._permission_cache[role]

        permissions = set()

        # 获取角色直接权限
        permissions.update(self._role_permissions.get(role, set()))

        # 递归获取继承的权限
        parent_role = self._role_hierarchy.get(role)
        if parent_role:
            permissions.update(self.get_role_permissions(parent_role))

        # 缓存结果
        self._permission_cache[role] = permissions
        return permissions

    def invalidate_permission_cache(self, role: Optional[str] = None) -> None:
        """使权限缓存失效

        Args:
            role: 要失效的角色，None表示全部
        """
        if role:
            self._permission_cache.pop(role, None)
        else:
            self._permission_cache.clear()

    async def create_user(
        self,
        user_id: str,
        username: str,
        role: str = Role.USER.value,
        permissions: Optional[List[str]] = None,
        email: Optional[str] = None,
    ) -> User:
        """创建用户

        Args:
            user_id: 用户ID
            username: 用户名
            role: 角色
            permissions: 额外权限列表
            email: 用户邮箱

        Returns:
            创建的用户

        Raises:
            ValueError: 如果用户已存在
        """
        existing = await self._user_repo.get(user_id)
        if existing:
            raise ValueError(f"用户已存在: {user_id}")

        existing_by_username = await self._user_repo.find_by_username(username)
        if existing_by_username:
            raise ValueError(f"用户名已被使用: {username}")

        user = User(
            id=user_id,
            username=username,
            role=role,
            permissions=set(permissions or []),
            email=email,
        )
        await self._user_repo.save(user)
        logger.info(f"创建用户: {username}({user_id}), 角色: {role}")
        return user

    async def get_user(self, user_id: str) -> Optional[User]:
        """获取用户

        Args:
            user_id: 用户ID

        Returns:
            用户实例，不存在返回None
        """
        return await self._user_repo.get(user_id)

    async def find_by_username(self, username: str) -> Optional[User]:
        """根据用户名查找用户

        Args:
            username: 用户名

        Returns:
            用户实例，不存在返回None
        """
        return await self._user_repo.find_by_username(username)

    async def update_user(
        self,
        user_id: str,
        role: Optional[str] = None,
        permissions: Optional[Set[str]] = None,
        enabled: Optional[bool] = None,
    ) -> bool:
        """更新用户信息

        Args:
            user_id: 用户ID
            role: 新角色
            permissions: 新权限集合
            enabled: 是否启用

        Returns:
            是否更新成功
        """
        user = await self._user_repo.get(user_id)
        if not user:
            return False

        if role is not None:
            user.role = role
            self.invalidate_permission_cache(role)

        if permissions is not None:
            user.permissions = permissions

        if enabled is not None:
            user.enabled = enabled

        await self._user_repo.save(user)
        logger.info(f"更新用户: {user_id}")
        return True

    async def delete_user(self, user_id: str) -> bool:
        """删除用户

        Args:
            user_id: 用户ID

        Returns:
            是否删除成功
        """
        result = await self._user_repo.delete(user_id)
        if result:
            logger.info(f"删除用户: {user_id}")
        return result

    async def add_user_permission(self, user_id: str, permission: str) -> bool:
        """为用户添加权限

        Args:
            user_id: 用户ID
            permission: 权限

        Returns:
            是否添加成功
        """
        user = await self._user_repo.get(user_id)
        if not user:
            return False

        user.add_permission(permission)
        await self._user_repo.save(user)
        logger.info(f"为用户添加权限: {user_id} -> {permission}")
        return True

    async def remove_user_permission(self, user_id: str, permission: str) -> bool:
        """从用户移除权限

        Args:
            user_id: 用户ID
            permission: 权限

        Returns:
            是否移除成功
        """
        user = await self._user_repo.get(user_id)
        if not user:
            return False

        user.remove_permission(permission)
        await self._user_repo.save(user)
        logger.info(f"从用户移除权限: {user_id} -> {permission}")
        return True

    async def check_permission(
        self, user_id: str, permission: str, **context
    ) -> bool:
        """检查用户权限

        Args:
            user_id: 用户ID
            permission: 权限
            **context: 权限检查上下文

        Returns:
            是否有权限
        """
        user = await self._user_repo.get(user_id)
        return user.has_permission(permission, self, **context) if user else False

    async def check_any_permission(
        self, user_id: str, permissions: List[str], **context
    ) -> bool:
        """检查是否有任意一个权限

        Args:
            user_id: 用户ID
            permissions: 权限列表
            **context: 权限检查上下文

        Returns:
            是否有任意权限
        """
        user = await self._user_repo.get(user_id)
        return (
            user.has_any_permission(permissions, self, **context) if user else False
        )

    async def check_all_permissions(
        self, user_id: str, permissions: List[str], **context
    ) -> bool:
        """检查是否有所有权限

        Args:
            user_id: 用户ID
            permissions: 权限列表
            **context: 权限检查上下文

        Returns:
            是否有所有权限
        """
        user = await self._user_repo.get(user_id)
        return (
            user.has_all_permissions(permissions, self, **context) if user else False
        )

    async def list_users(self) -> List[Dict[str, Any]]:
        """获取所有用户列表

        Returns:
            用户信息字典列表
        """
        users = await self._user_repo.list_all()
        return [user.to_dict() for user in users]

    async def get_user_count(self) -> int:
        """获取用户总数

        Returns:
            用户数量
        """
        users = await self._user_repo.list_all()
        return len(users)

    def get_all_permissions(self) -> Set[str]:
        """获取系统中定义的所有权限

        Returns:
            权限集合
        """
        return {p.value for p in Permission}

    def get_all_roles(self) -> Set[str]:
        """获取系统中定义的所有角色

        Returns:
            角色集合
        """
        return {r.value for r in Role}


# ========== 全局RBAC管理器 ==========
_global_rbac: Optional[RBACManager] = None


def get_rbac() -> RBACManager:
    """获取全局RBAC管理器实例

    Returns:
        RBACManager实例
    """
    global _global_rbac
    if _global_rbac is None:
        _global_rbac = RBACManager()
    return _global_rbac


def set_rbac(rbac: RBACManager) -> None:
    """设置全局RBAC管理器

    Args:
        rbac: RBAC管理器实例
    """
    global _global_rbac
    _global_rbac = rbac


def reset_rbac() -> None:
    """重置全局RBAC管理器

    主要用于测试环境
    """
    global _global_rbac
    _global_rbac = None


# ========== 权限检查装饰器 ==========
def require_permission(*permissions: str):
    """权限检查装饰器

    要求用户拥有所有指定权限才能访问。

    Args:
        *permissions: 所需权限列表

    Example:
        @require_permission(Permission.DOCUMENT_WRITE.value)
        async def create_document(request: Request):
            ...
    """

    def decorator(
        func: Union[Callable[..., T], Callable[..., Awaitable[T]]]
    ) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # 尝试从多个可能的位置获取request
            request: Optional[Request] = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            if not request:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="缺少认证上下文",
                )

            # 从请求状态获取用户信息
            user: Optional[User] = getattr(request.state, "user", None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未认证用户",
                )

            # 获取RBAC管理器
            rbac = kwargs.get("rbac") or get_rbac()

            # 检查权限
            for permission in permissions:
                if not user.has_permission(permission, rbac):
                    logger.warning(
                        f"权限不足: 用户 {user.username} "
                        f"尝试访问需要权限 {permission} 的资源"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"权限不足，需要权限: {permission}",
                    )

            return (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )

        return wrapper

    return decorator


def require_any_permission(*permissions: str):
    """权限检查装饰器（任意一个）

    要求用户拥有至少一个指定权限才能访问。

    Args:
        *permissions: 所需权限列表

    Example:
        @require_any_permission(
            Permission.DOCUMENT_WRITE.value,
            Permission.DOCUMENT_DELETE.value
        )
        async def modify_document(request: Request):
            ...
    """

    def decorator(
        func: Union[Callable[..., T], Callable[..., Awaitable[T]]]
    ) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            request: Optional[Request] = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            if not request:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="缺少认证上下文",
                )

            user: Optional[User] = getattr(request.state, "user", None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未认证用户",
                )

            rbac = kwargs.get("rbac") or get_rbac()

            # 检查是否有任意一个权限
            if not user.has_any_permission(list(permissions), rbac):
                logger.warning(
                    f"权限不足: 用户 {user.username} "
                    f"尝试访问需要权限之一 {permissions} 的资源"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限不足，需要以下权限之一: {', '.join(permissions)}",
                )

            return (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )

        return wrapper

    return decorator


def require_role(*roles: str):
    """角色检查装饰器

    要求用户拥有指定角色之一才能访问。

    Args:
        *roles: 所需角色列表

    Example:
        @require_role(Role.ADMIN.value, Role.OPERATOR.value)
        async def admin_panel(request: Request):
            ...
    """

    def decorator(
        func: Union[Callable[..., T], Callable[..., Awaitable[T]]]
    ) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            request: Optional[Request] = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            if not request:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="缺少认证上下文",
                )

            user: Optional[User] = getattr(request.state, "user", None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未认证用户",
                )

            if user.role not in roles:
                logger.warning(
                    f"角色不足: 用户 {user.username} (角色: {user.role}) "
                    f"尝试访问需要角色之一 {roles} 的资源"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限不足，需要以下角色之一: {', '.join(roles)}",
                )

            return (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )

        return wrapper

    return decorator


class RequirePermission:
    """基于类的权限检查器

    可以用于FastAPI依赖注入。

    Example:
        @app.get("/documents")
        async def list_documents(
            auth: RequirePermission = Depends(RequirePermission(Permission.DOCUMENT_READ.value))
        ):
            ...
    """

    def __init__(
        self,
        *permissions: str,
        require_all: bool = True,
    ):
        """初始化权限检查器

        Args:
            *permissions: 所需权限
            require_all: True要求所有权限，False要求任意一个
        """
        self.permissions = permissions
        self.require_all = require_all

    async def __call__(self, request: Request) -> User:
        """执行权限检查

        Args:
            request: FastAPI请求对象

        Returns:
            当前用户

        Raises:
            HTTPException: 权限不足时
        """
        user: Optional[User] = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未认证用户",
            )

        rbac = get_rbac()

        if self.require_all:
            # 需要所有权限
            for permission in self.permissions:
                if not user.has_permission(permission, rbac):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"权限不足，需要权限: {permission}",
                    )
        else:
            # 需要任意一个权限
            if not user.has_any_permission(list(self.permissions), rbac):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限不足，需要以下权限之一: {', '.join(self.permissions)}",
                )

        return user
