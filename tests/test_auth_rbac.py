"""RBAC模块测试

测试重构后的RBAC系统功能
"""

from backend.auth.rbac import (
    Permission,
    Role,
    User,
    get_rbac,
    require_permission,
    reset_rbac,
)


class TestPermission:
    """权限枚举测试"""

    def test_permission_values(self):
        """测试权限枚举值"""
        assert Permission.DOCUMENT_READ.value == "document:read"
        assert Permission.DOCUMENT_WRITE.value == "document:write"
        assert Permission.SYSTEM_ADMIN.value == "system:admin"

    def test_permission_count(self):
        """测试权限数量"""
        # 应该有9个核心权限
        permissions = list(Permission)
        assert len(permissions) == 9


class TestRole:
    """角色枚举测试"""

    def test_role_values(self):
        """测试角色枚举值"""
        assert Role.ADMIN.value == "admin"
        assert Role.USER.value == "user"
        assert Role.GUEST.value == "guest"

    def test_role_count(self):
        """测试角色数量"""
        # 应该有3个角色
        roles = list(Role)
        assert len(roles) == 3


class TestUser:
    """用户模型测试"""

    def test_user_creation(self):
        """测试用户创建"""
        user = User(
            id="test1",
            username="alice",
            role="user",
            permissions={"document:read"},
        )
        assert user.id == "test1"
        assert user.username == "alice"
        assert user.role == "user"
        assert "document:read" in user.permissions

    def test_user_default_values(self):
        """测试用户默认值"""
        user = User(id="test1", username="bob", role="guest")
        assert user.permissions == set()
        assert user.enabled is True
        assert user.email is None

    def test_has_permission_with_direct_permission(self):
        """测试直接权限检查"""
        user = User(
            id="test1",
            username="alice",
            role="guest",
            permissions={"document:write"},
        )
        assert user.has_permission("document:write", set()) is True
        assert user.has_permission("document:read", set()) is False

    def test_has_permission_with_role_permission(self):
        """测试角色权限检查"""
        user = User(id="test1", username="bob", role="user")
        role_permissions = {"document:read", "document:write"}
        assert user.has_permission("document:read", role_permissions) is True
        assert user.has_permission("document:write", role_permissions) is True
        assert user.has_permission("system:admin", role_permissions) is False

    def test_has_permission_disabled_user(self):
        """测试禁用用户"""
        user = User(id="test1", username="charlie", role="admin", enabled=False)
        assert user.has_permission("system:admin", {"system:admin"}) is False

    def test_has_role(self):
        """测试角色检查"""
        user = User(id="test1", username="dave", role="user")
        assert user.has_role("user") is True
        assert user.has_role("admin") is False

    def test_has_role_disabled(self):
        """测试禁用用户的角色检查"""
        user = User(id="test1", username="eve", role="admin", enabled=False)
        assert user.has_role("admin") is False


class TestRBACManager:
    """RBAC管理器测试"""

    def setup_method(self):
        """每个测试前重置RBAC"""
        reset_rbac()

    def test_singleton(self):
        """测试单例模式"""
        rbac1 = get_rbac()
        rbac2 = get_rbac()
        assert rbac1 is rbac2

    def test_create_user(self):
        """测试创建用户"""
        rbac = get_rbac()
        user = rbac.create_user("u1", "alice", Role.USER.value)
        assert user.id == "u1"
        assert user.username == "alice"
        assert user.role == "user"

    def test_add_and_get_user(self):
        """测试添加和获取用户"""
        rbac = get_rbac()
        user = User(id="u1", username="bob", role="guest")
        rbac.add_user(user)

        retrieved = rbac.get_user("u1")
        assert retrieved is not None
        assert retrieved.username == "bob"

    def test_get_nonexistent_user(self):
        """测试获取不存在的用户"""
        rbac = get_rbac()
        user = rbac.get_user("nonexistent")
        assert user is None

    def test_get_role_permissions_admin(self):
        """测试管理员权限"""
        rbac = get_rbac()
        perms = rbac.get_role_permissions("admin")
        assert Permission.SYSTEM_ADMIN.value in perms
        assert Permission.DOCUMENT_WRITE.value in perms
        assert len(perms) > 5  # 管理员应该有很多权限

    def test_get_role_permissions_user(self):
        """测试普通用户权限"""
        rbac = get_rbac()
        perms = rbac.get_role_permissions("user")
        assert Permission.DOCUMENT_READ.value in perms
        assert Permission.DOCUMENT_WRITE.value in perms
        assert Permission.SYSTEM_ADMIN.value not in perms

    def test_get_role_permissions_guest(self):
        """测试访客权限"""
        rbac = get_rbac()
        perms = rbac.get_role_permissions("guest")
        assert Permission.DOCUMENT_READ.value in perms
        assert Permission.DOCUMENT_WRITE.value not in perms

    def test_get_role_permissions_unknown(self):
        """测试未知角色"""
        rbac = get_rbac()
        perms = rbac.get_role_permissions("unknown")
        assert perms == set()

    def test_check_permission_with_direct_permission(self):
        """测试直接权限检查"""
        rbac = get_rbac()
        user = rbac.create_user("u1", "alice", Role.GUEST.value, permissions={"document:write"})
        assert rbac.check_permission(user, "document:write") is True

    def test_check_permission_with_role_permission(self):
        """测试角色权限检查"""
        rbac = get_rbac()
        user = rbac.create_user("u1", "bob", Role.USER.value)
        assert rbac.check_permission(user, "document:read") is True
        assert rbac.check_permission(user, "system:admin") is False

    def test_check_permission_disabled_user(self):
        """测试禁用用户权限检查"""
        rbac = get_rbac()
        user = rbac.create_user("u1", "charlie", Role.ADMIN.value, enabled=False)
        assert rbac.check_permission(user, "system:admin") is False


class TestRequirePermission:
    """权限装饰器测试"""

    def test_require_permission_returns_decorator(self):
        """测试装饰器返回装饰器函数"""
        decorator = require_permission("document:read")
        assert callable(decorator)

    def test_require_permission_with_async_func(self):
        """测试异步函数装饰"""
        decorator = require_permission("document:write")

        @decorator
        async def test_func(request):
            return {"success": True}

        assert callable(test_func)


class TestRBACIntegration:
    """RBAC集成测试"""

    def setup_method(self):
        """每个测试前重置RBAC"""
        reset_rbac()

    def test_complete_permission_flow(self):
        """测试完整权限流程"""
        rbac = get_rbac()

        # 创建不同角色的用户
        admin = rbac.create_user("admin1", "admin_user", Role.ADMIN.value)
        user = rbac.create_user("user1", "normal_user", Role.USER.value)
        guest = rbac.create_user("guest1", "guest_user", Role.GUEST.value)

        # 管理员应该有所有权限
        assert rbac.check_permission(admin, "system:admin") is True
        assert rbac.check_permission(admin, "document:write") is True

        # 普通用户应该有基础权限
        assert rbac.check_permission(user, "document:write") is True
        assert rbac.check_permission(user, "system:admin") is False

        # 访客只有读权限
        assert rbac.check_permission(guest, "document:read") is True
        assert rbac.check_permission(guest, "document:write") is False

    def test_custom_permissions_override_role(self):
        """测试自定义权限覆盖角色权限"""
        rbac = get_rbac()

        # 给访客添加写权限（覆盖角色限制）
        guest = rbac.create_user(
            "guest1", "special_guest", Role.GUEST.value, permissions={"document:write"}
        )

        assert rbac.check_permission(guest, "document:write") is True

    def test_multiple_users_isolation(self):
        """测试多用户隔离"""
        rbac = get_rbac()

        user1 = rbac.create_user("u1", "alice", Role.USER.value)
        user2 = rbac.create_user("u2", "bob", Role.GUEST.value)

        # user1应该有写权限
        assert rbac.check_permission(user1, "document:write") is True

        # user2不应该有写权限
        assert rbac.check_permission(user2, "document:write") is False
