"""保密数据安全搜索服务测试"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from asyncpg import Pool
from typing import Any, Optional, List

from backend.services.qigong.secure_search import (
    SecureSearchService,
    AccessControlError,
    get_secure_search_service
)


class MockRecord:
    """模拟 asyncpg.Record"""
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        return self._data.get(key)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def __contains__(self, key):
        return key in self._data


class MockConnection:
    """模拟数据库连接"""
    def __init__(self):
        self.side_effect = []
        self.fetchrow_calls = []
        self.fetch_calls = []
        self.fetchval_calls = []

    def set_side_effect(self, effects):
        self.side_effect = effects
        self.index = 0

    def _convert_to_mock_record(self, result: Any) -> Any:
        """将结果转换为 MockRecord"""
        if result is None:
            return None
        if isinstance(result, dict):
            return MockRecord(result)
        if isinstance(result, list):
            return [self._convert_to_mock_record(r) if isinstance(r, dict) else r for r in result]
        return result

    async def fetchrow(self, *args, **kwargs):
        self.fetchrow_calls.append((args, kwargs))
        if self.side_effect:
            result = self.side_effect[self.index] if self.index < len(self.side_effect) else None
            self.index += 1
            return self._convert_to_mock_record(result)
        return None

    async def fetch(self, *args, **kwargs):
        self.fetch_calls.append((args, kwargs))
        if self.side_effect:
            result = self.side_effect[self.index] if self.index < len(self.side_effect) else []
            self.index += 1
            return self._convert_to_mock_record(result)
        return []

    async def fetchval(self, *args, **kwargs):
        self.fetchval_calls.append((args, kwargs))
        if self.side_effect:
            result = self.side_effect[self.index] if self.index < len(self.side_effect) else None
            self.index += 1
            return result
        return None

    async def execute(self, *args, **kwargs):
        return "UPDATE 1"

    async def __aenter__(self):
        # 进入上下文时不重置索引，保持调用序列
        return self

    async def __aexit__(self, *args):
        pass


class MockPool:
    """模拟数据库连接池"""
    def __init__(self):
        self.conn = MockConnection()
        self.call_count = 0

    def acquire(self):
        """返回一个异步上下文管理器"""
        self.call_count += 1
        return self.conn

    async def close(self):
        pass

    def __await__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_pool():
    """模拟数据库连接池"""
    return MockPool()


@pytest.fixture
def service(mock_pool):
    """创建测试服务实例"""
    service = SecureSearchService("postgresql://test")
    service._pool = mock_pool
    return service


class TestSecurityLevels:
    """安全级别定义测试"""

    def test_security_levels_order(self):
        """测试安全级别排序"""
        from backend.services.qigong.secure_search import SecureSearchService

        assert SecureSearchService.SECURITY_LEVELS['public'] == 0
        assert SecureSearchService.SECURITY_LEVELS['internal'] == 1
        assert SecureSearchService.SECURITY_LEVELS['confidential'] == 2
        assert SecureSearchService.SECURITY_LEVELS['restricted'] == 3


class TestCheckUserPermission:
    """用户权限检查测试"""

    async def test_public_access_always_allowed(self, service):
        """测试公开访问总是允许"""
        result = await service.check_user_permission("user_123", "public")

        assert result["allowed"] is True
        assert result["required_level"] == "public"

    async def test_restricted_access_with_permission(self, service):
        """测试有权限的用户可以访问限制文档"""
        service._pool.conn.set_side_effect([
            # 用户权限
            {
                "security_level": "restricted",
                "username": "admin",
                "is_active": True,
                "expires_at": None
            },
            # 临时授权（无）
            None
        ])

        result = await service.check_user_permission("user_123", "restricted")

        assert result["allowed"] is True
        assert result["actual_level"] == "restricted"

    async def test_confidential_access_with_only_internal_permission(self, service):
        """测试只有 internal 权限的用户无法访问 confidential 文档"""
        service._pool.conn.set_side_effect([
            # 用户权限 - 只有 internal
            {
                "security_level": "internal",
                "username": "user",
                "is_active": True,
                "expires_at": None
            },
            # 临时授权（无）
            None
        ])

        result = await service.check_user_permission("user_123", "confidential")

        assert result["allowed"] is False
        assert result["reason"] == "insufficient permission level"

    async def test_temporary_grant_elevates_permission(self, service):
        """测试临时授权可以提升权限级别"""
        service._pool.conn.set_side_effect([
            # 用户权限 - 只有 internal
            {
                "security_level": "internal",
                "username": "user",
                "is_active": True,
                "expires_at": None
            },
            # 临时授权 - 有 confidential
            {
                "security_level": "confidential",
                "expires_at": datetime.now() + timedelta(hours=1),
                "access_count": 0,
                "max_access_count": 10
            }
        ])

        result = await service.check_user_permission("user_123", "confidential")

        assert result["allowed"] is True
        assert result["actual_level"] == "confidential"


class TestLogAccess:
    """访问日志测试"""

    async def test_log_access_success(self, service):
        """测试记录成功访问"""
        service._pool.conn.set_side_effect([12345])

        log_id = await service.log_access(
            user_id="user_123",
            document_id=100,
            security_level="public",
            action="view"
        )

        assert log_id == 12345

    async def test_log_access_denied(self, service):
        """测试记录拒绝访问"""
        service._pool.conn.set_side_effect([12346])

        log_id = await service.log_access(
            user_id="user_123",
            document_id=100,
            security_level="confidential",
            action="view",
            result="denied",
            denial_reason="insufficient_permission"
        )

        assert log_id == 12346


class TestGetDocument:
    """获取文档测试"""

    async def test_get_public_document_succeeds(self, service):
        """测试获取公开文档成功"""
        service._pool.conn.set_side_effect([
            # 文档信息
            {
                "id": 1,
                "title": "测试文档",
                "file_path": "/test/path.txt",
                "content": "测试内容",
                "category": "气功",
                "qigong_dims": {},
                "security_level": "public",
                "created_at": datetime.now()
            },
            # log_access 返回值
            999
        ])

        result = await service.get_document("user_123", 1)

        assert result["id"] == 1
        assert result["security_level"] == "public"

    async def test_get_confidential_document_without_permission_fails(self, service):
        """测试无权限获取保密文档失败"""
        service._pool.conn.set_side_effect([
            # 文档信息 - confidential
            {
                "id": 1,
                "title": "保密文档",
                "file_path": "/test/secret.txt",
                "content": "保密内容",
                "category": "气功",
                "qigong_dims": {},
                "security_level": "confidential",
                "created_at": datetime.now()
            },
            # 用户权限 - 无
            None,
            # 临时授权 - 无
            None,
            # log_access 返回值
            998
        ])

        with pytest.raises(AccessControlError) as exc_info:
            await service.get_document("user_123", 1)

        assert "Access denied" in str(exc_info.value)

    async def test_get_confidential_document_with_permission_succeeds(self, service):
        """测试有权限获取保密文档成功"""
        service._pool.conn.set_side_effect([
            # 文档信息
            {
                "id": 1,
                "title": "保密文档",
                "file_path": "/test/secret.txt",
                "content": "保密内容",
                "category": "气功",
                "qigong_dims": {},
                "security_level": "confidential",
                "created_at": datetime.now()
            },
            # 用户权限 - 有 confidential
            {
                "security_level": "confidential",
                "username": "user",
                "is_active": True,
                "expires_at": None
            },
            # 临时授权 - 无
            None,
            # log_access 返回值
            997
        ])

        result = await service.get_document("user_123", 1)

        assert result["id"] == 1
        assert result["security_level"] == "confidential"


class TestGrantPermission:
    """授予权限测试"""

    async def test_grant_permission_as_admin(self, service):
        """测试管理员授予权限"""
        service._pool.conn.set_side_effect([
            # 管理员权限检查 - restricted
            {
                "security_level": "restricted",
                "username": "admin",
                "is_active": True,
                "expires_at": None
            },
            # 临时授权检查 - 无
            None,
            # 授权结果
            123,
            # log_access 返回值
            995
        ])

        result = await service.grant_permission(
            admin_user="admin",
            target_user="user_123",
            target_username="张三",
            security_level="confidential"
        )

        assert result["success"] is True
        assert result["permission_id"] == 123

    async def test_grant_permission_as_non_admin_fails(self, service):
        """测试非管理员无法授予权限"""
        service._pool.conn.set_side_effect([
            # 管理员权限检查 - 无权限
            None,
            # 临时授权检查 - 无
            None
        ])

        with pytest.raises(AccessControlError) as exc_info:
            await service.grant_permission(
                admin_user="user_123",
                target_user="user_456",
                target_username="李四",
                security_level="internal"
            )

        assert "Only administrators" in str(exc_info.value)


class TestRevokePermission:
    """撤销权限测试"""

    async def test_revoke_permission_succeeds(self, service):
        """测试撤销权限成功"""
        service._pool.conn.set_side_effect([
            # 管理员权限检查
            {
                "security_level": "restricted",
                "username": "admin",
                "is_active": True,
                "expires_at": None
            },
            # 临时授权检查 - 无
            None,
            # execute 返回值（row count）
            1,
            # log_access 返回值
            994
        ])

        result = await service.revoke_permission(
            admin_user="admin",
            target_user="user_123",
            security_level="confidential"
        )

        assert result["success"] is True
        assert result["rows_affected"] == 1


class TestCreateTemporaryGrant:
    """创建临时授权测试"""

    async def test_create_temporary_grant(self, service):
        """测试创建临时授权码"""
        service._pool.conn.set_side_effect([
            # 管理员权限检查
            {
                "security_level": "restricted",
                "username": "admin",
                "is_active": True,
                "expires_at": None
            },
            # 临时授权检查 - 无
            None,
            # 创建结果
            456
        ])

        result = await service.create_temporary_grant(
            admin_user="admin",
            security_level="confidential",
            expires_hours=24,
            max_access_count=100
        )

        assert result["success"] is True
        assert result["grant_id"] == 456
        assert "grant_code" in result
        assert result["max_access_count"] == 100


class TestUseTemporaryGrant:
    """使用临时授权测试"""

    async def test_use_temporary_grant_success(self, service):
        """测试使用临时授权成功"""
        service._pool.conn.set_side_effect([
            # 授权码有效
            {
                "id": 1,
                "grant_code": "test_code",
                "security_level": "confidential",
                "document_ids": None,
                "expires_at": datetime.now() + timedelta(hours=1),
                "max_access_count": 10,
                "access_count": 5,
                "is_active": True
            },
            # 权限创建结果
            789
        ])

        result = await service.use_temporary_grant(
            grant_code="test_code",
            user_id="user_123",
            username="张三"
        )

        assert result["success"] is True

    async def test_use_temporary_grant_expired_fails(self, service):
        """测试使用过期授权码失败"""
        service._pool.conn.set_side_effect([
            # 授权码无效/过期
            None
        ])

        with pytest.raises(AccessControlError) as exc_info:
            await service.use_temporary_grant(
                grant_code="expired_code",
                user_id="user_123",
                username="张三"
            )

        assert "Invalid or expired" in str(exc_info.value)


class TestSearchDocuments:
    """搜索文档测试"""

    async def test_search_returns_only_public_for_unauthorized_user(self, service):
        """测试未授权用户只能搜索公开文档"""
        # search_documents 调用 check_user_permission("user_123", "public")
        # 当 required_level == "public" 时直接返回，不访问数据库
        # 然后在 async with 块内调用 fetchval, fetch, log_access
        service._pool.conn.set_side_effect([
            # search_documents 内部的 async with pool.acquire() 调用
            100,  # fetchval: 计数
            # fetch: 结果 (需要返回 MockRecord 列表)
            [
                {"id": 1, "title": "公开文档1", "file_path": "/public/1.txt",
                 "category": "气功", "qigong_dims": {}, "created_at": None},
                {"id": 2, "title": "公开文档2", "file_path": "/public/2.txt",
                 "category": "气功", "qigong_dims": {}, "created_at": None}
            ],
            # log_access (在 search_documents 内部) fetchval
            996
        ])

        result = await service.search_documents(
            user_id="user_123",
            query="形神庄"
        )

        assert len(result["results"]) == 2
        assert result["user_max_level"] == "public"


class TestGetAccessStatistics:
    """访问统计测试"""

    async def test_get_access_statistics(self, service):
        """测试获取访问统计"""
        service._pool.conn.set_side_effect([
            # 统计结果
            [
                {"action": "view", "security_level": "public", "result": "success", "count": 100},
                {"action": "view", "security_level": "confidential", "result": "success", "count": 10},
                {"action": "download", "security_level": "public", "result": "success", "count": 5}
            ]
        ])

        result = await service.get_access_statistics(days=30)

        assert result["period_days"] == 30
        assert len(result["statistics"]) == 3
