"""简化权限定义

基于实际使用情况，只保留必要的基础权限。
"""

from enum import Enum


class Permission(Enum):
    """基础权限枚举（简化版）

    根据实际使用情况，只定义系统实际需要的权限。
    采用 <资源>:<操作> 的命名约定。
    """

    # ========== 文档相关 ==========
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"

    # ========== 用户管理 ==========
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_MANAGE_ROLES = "user:manage_roles"

    # ========== 系统管理 ==========
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_METRICS = "system:metrics"
    SYSTEM_CONFIG = "system:config"


class Role(Enum):
    """角色枚举（简化版）

    系统中所有可用角色的集中定义。
    角色按权限等级从高到低排列。
    """

    ADMIN = "admin"  # 系统管理员，拥有所有权限
    USER = "user"  # 普通用户，基础读写权限
    GUEST = "guest"  # 访客，只读权限


# 角色权限映射
ROLE_PERMISSIONS = {
    Role.ADMIN: {
        # 管理员拥有所有权限
        Permission.SYSTEM_ADMIN,
        Permission.SYSTEM_METRICS,
        Permission.SYSTEM_CONFIG,
        Permission.USER_MANAGE_ROLES,
        Permission.USER_WRITE,
        Permission.DOCUMENT_DELETE,
        Permission.DOCUMENT_WRITE,
        Permission.DOCUMENT_READ,
        Permission.USER_READ,
    },
    Role.USER: {
        # 普通用户的基础权限
        Permission.DOCUMENT_WRITE,
        Permission.DOCUMENT_READ,
        Permission.USER_READ,
    },
    Role.GUEST: {
        # 访客的只读权限
        Permission.DOCUMENT_READ,
    },
}
