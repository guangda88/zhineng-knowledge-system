"""JWT 认证模块测试

测试 JWT 令牌的生成、验证和黑名单功能
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Set
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.auth.jwt import AuthConfig, JWTAuth, TokenBlacklist, TokenPair, TokenPayload, TokenType


class TestTokenType:
    """Token 类型测试"""

    def test_token_type_values(self):
        """测试 token 类型值"""
        assert TokenType.ACCESS.value == "access"
        assert TokenType.REFRESH.value == "refresh"

    def test_token_type_enum(self):
        """测试 token 类型枚举"""
        assert TokenType.ACCESS == TokenType.ACCESS
        assert TokenType.ACCESS != TokenType.REFRESH


class TestTokenPayload:
    """Token 载荷测试"""

    def test_token_payload_creation(self):
        """测试创建 token payload"""
        now = int(datetime.now(timezone.utc).timestamp())
        payload = TokenPayload(
            user_id="user123",
            username="testuser",
            role="user",
            exp=now + 3600,
            iat=now,
            jti="test-jti",
            type="access",
        )

        assert payload.user_id == "user123"
        assert payload.username == "testuser"
        assert payload.role == "user"
        assert payload.type == "access"
        assert payload.iss == "zhineng-kb"

    def test_token_payload_with_permissions(self):
        """测试带权限的 token payload"""
        now = int(datetime.now(timezone.utc).timestamp())
        permissions = {"read:documents", "write:documents"}

        payload = TokenPayload(
            user_id="user123",
            username="testuser",
            role="user",
            exp=now + 3600,
            iat=now,
            jti="test-jti",
            type="access",
            permissions=permissions,
        )

        assert payload.permissions == permissions

    def test_token_payload_to_dict(self):
        """测试序列化 token payload"""
        now = int(datetime.now(timezone.utc).timestamp())
        payload = TokenPayload(
            user_id="user123",
            username="testuser",
            role="user",
            exp=now + 3600,
            iat=now,
            jti="test-jti",
            type="access",
        )

        data = payload.to_dict()

        assert data["user_id"] == "user123"
        assert data["username"] == "testuser"
        assert data["role"] == "user"
        assert data["type"] == "access"
        assert isinstance(data["permissions"], list)

    def test_token_payload_from_dict(self):
        """测试从字典创建 token payload"""
        now = int(datetime.now(timezone.utc).timestamp())
        data = {
            "user_id": "user123",
            "username": "testuser",
            "role": "user",
            "exp": now + 3600,
            "iat": now,
            "jti": "test-jti",
            "type": "access",
            "permissions": ["read:documents"],
        }

        payload = TokenPayload.from_dict(data)

        assert payload.user_id == "user123"
        assert payload.username == "testuser"
        assert "read:documents" in payload.permissions


class TestAuthConfig:
    """认证配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = AuthConfig()

        assert config.issuer == "zhineng-kb"
        assert config.access_token_expire_minutes == 30
        assert config.refresh_token_expire_days == 7
        assert config.algorithm == "RS256"

    def test_custom_config(self):
        """测试自定义配置"""
        config = AuthConfig(
            issuer="custom-issuer",
            access_token_expire_minutes=60,
            refresh_token_expire_days=14,
            algorithm="HS256",
        )

        assert config.issuer == "custom-issuer"
        assert config.access_token_expire_minutes == 60
        assert config.refresh_token_expire_days == 14
        assert config.algorithm == "HS256"


class TestTokenPair:
    """Token 对测试"""

    def test_token_pair_creation(self):
        """测试创建 token 对"""
        token_pair = TokenPair(
            access_token="access_token_value", refresh_token="refresh_token_value", expires_in=1800
        )

        assert token_pair.access_token == "access_token_value"
        assert token_pair.refresh_token == "refresh_token_value"
        assert token_pair.expires_in == 1800


class TestTokenBlacklist:
    """Token 黑名单测试"""

    def test_token_blacklist_init(self):
        """测试黑名单初始化"""
        blacklist = TokenBlacklist()
        assert blacklist is not None
        assert blacklist._blacklisted == {}

    @pytest.mark.asyncio
    async def test_add_to_blacklist(self):
        """测试添加到黑名单"""
        blacklist = TokenBlacklist()
        jti = "test-jti-123"
        exp = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())

        await blacklist.add(jti, exp)

        # 检查是否在黑名单中
        is_blacklisted = await blacklist.is_blacklisted(jti)
        assert is_blacklisted is True

    @pytest.mark.asyncio
    async def test_check_not_blacklisted(self):
        """测试检查不在黑名单中的 token"""
        blacklist = TokenBlacklist()

        is_blacklisted = await blacklist.is_blacklisted("non-existent-jti")
        assert is_blacklisted is False

    @pytest.mark.asyncio
    async def test_expired_cleanup(self):
        """测试过期 token 清理"""
        blacklist = TokenBlacklist()

        # 添加一个已过期的 JTI (使用内部方法)
        jti = "expired-jti"
        exp = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
        await blacklist.add(jti, exp)

        # 直接操作内部存储来触发清理检查
        # 设置上次清理时间为很久以前
        blacklist._last_cleanup = 0

        # 调用内部清理方法
        await blacklist._cleanup_if_needed()

        # 应该不在黑名单中
        is_blacklisted = await blacklist.is_blacklisted(jti)
        assert is_blacklisted is False


class TestJWTAuth:
    """JWT 认证测试"""

    def test_jwt_auth_init(self):
        """测试 JWT 认证初始化"""
        config = AuthConfig(algorithm="HS256", access_token_expire_minutes=30)
        auth = JWTAuth(config=config)

        assert auth is not None
        assert auth.config.algorithm == "HS256"

    def test_jwt_auth_default_config(self):
        """测试使用默认配置初始化"""
        auth = JWTAuth()

        assert auth is not None
        assert auth.config.issuer == "zhineng-kb"
        assert auth.blacklist is not None
