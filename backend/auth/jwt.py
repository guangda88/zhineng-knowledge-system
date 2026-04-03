"""JWT令牌管理模块

提供基于RS256算法的JWT令牌生成、验证和刷新功能。
支持访问令牌、刷新令牌机制以及令牌黑名单。

安全特性：
- 使用RS256非对称加密算法
- 令牌黑名单防止令牌滥用
- 令牌过期自动清理
- JTI（JWT ID）支持令牌追踪
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional, Set

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

logger = logging.getLogger(__name__)


class TokenType(Enum):
    """令牌类型枚举

    Attributes:
        ACCESS: 访问令牌，用于API认证
        REFRESH: 刷新令牌，用于获取新的访问令牌
    """

    ACCESS = "access"
    REFRESH = "refresh"


@dataclass
class TokenPayload:
    """JWT令牌载荷数据结构

    Attributes:
        user_id: 用户唯一标识符
        username: 用户名
        role: 用户角色
        permissions: 用户权限列表
        exp: 令牌过期时间（Unix时间戳）
        iat: 令牌签发时间（Unix时间戳）
        jti: JWT唯一标识符，用于黑名单追踪
        type: 令牌类型（access/refresh）
        iss: 签发者标识
    """

    user_id: str
    username: str
    role: str
    exp: int
    iat: int
    jti: str
    type: str
    iss: str = "zhineng-kb"
    permissions: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式

        Returns:
            包含令牌载荷数据的字典
        """
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "permissions": list(self.permissions),
            "exp": self.exp,
            "iat": self.iat,
            "jti": self.jti,
            "type": self.type,
            "iss": self.iss,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TokenPayload:
        """从字典创建TokenPayload实例

        Args:
            data: 包含令牌载荷数据的字典

        Returns:
            TokenPayload实例
        """
        permissions = set(data.get("permissions", []))
        if isinstance(permissions, list):
            permissions = set(permissions)

        return cls(
            user_id=data.get("user_id", ""),
            username=data.get("username", ""),
            role=data.get("role", "user"),
            exp=data.get("exp", 0),
            iat=data.get("iat", 0),
            jti=data.get("jti", ""),
            type=data.get("type", TokenType.ACCESS.value),
            iss=data.get("iss", "zhineng-kb"),
            permissions=permissions,
        )

    def is_expired(self) -> bool:
        """检查令牌是否已过期

        Returns:
            True如果令牌已过期，否则False
        """
        now = int(datetime.now(tz=timezone.utc).timestamp())
        return self.exp < now

    def expires_in(self) -> int:
        """获取令牌剩余有效时间（秒）

        Returns:
            剩余秒数，负数表示已过期
        """
        now = int(datetime.now(tz=timezone.utc).timestamp())
        return max(0, self.exp - now)


@dataclass
class TokenPair:
    """令牌对

    Attributes:
        access_token: 访问令牌
        refresh_token: 刷新令牌
        expires_in: 访问令牌过期时间（秒）
    """

    access_token: str
    refresh_token: str
    expires_in: int


@dataclass
class AuthConfig:
    """JWT认证配置

    Attributes:
        private_key_pem: RSA私钥PEM格式字符串
        public_key_pem: RSA公钥PEM格式字符串
        algorithm: JWT签名算法，默认RS256
        access_token_expire_minutes: 访问令牌有效期（分钟）
        refresh_token_expire_days: 刷新令牌有效期（天）
        issuer: 令牌签发者标识
        leeway: 令牌过期时间宽容度（秒）
        blacklist_cleanup_interval: 黑名单清理间隔（秒）
    """

    private_key_pem: Optional[str] = None
    public_key_pem: Optional[str] = None
    algorithm: str = "RS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    issuer: str = "zhineng-kb"
    leeway: int = 10
    blacklist_cleanup_interval: int = 3600

    def __post_init__(self):
        """初始化后验证密钥对（如果未提供）"""
        if self.private_key_pem is None or self.public_key_pem is None:
            import os

            environment = os.getenv("ENVIRONMENT", "development").lower()

            if environment in ("production", "prod"):
                raise ValueError(
                    "安全错误: RSA密钥对在生产环境必须通过环境变量提供。\n"
                    "请设置以下环境变量：\n"
                    "  - JWT_PRIVATE_KEY: RSA私钥PEM格式\n"
                    "  - JWT_PUBLIC_KEY: RSA公钥PEM格式\n\n"
                    "生成密钥对命令:\n"
                    "  openssl genrsa -out private.pem 2048\n"
                    "  openssl rsa -in private.pem -pubout -out public.pem"
                )

            logger.warning(
                "未提供RSA密钥对，生成临时密钥对（仅限开发环境）。" "重启后所有令牌将失效。"
            )
            private_key, public_key = self._generate_rsa_key_pair()
            self.private_key_pem = private_key
            self.public_key_pem = public_key

    @staticmethod
    def _generate_rsa_key_pair(key_size: int = 2048) -> tuple[str, str]:
        """生成RSA密钥对

        Args:
            key_size: 密钥大小（位），默认2048

        Returns:
            (私钥PEM, 公钥PEM)元组
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=key_size, backend=default_backend()
        )

        private_pem = private_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        ).decode("utf-8")

        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")

        return private_pem, public_pem

    @classmethod
    def from_env(cls) -> "AuthConfig":
        """从环境变量加载配置

        环境变量:
            JWT_PRIVATE_KEY: RSA私钥PEM
            JWT_PUBLIC_KEY: RSA公钥PEM
            JWT_ISSUER: 令牌签发者
            JWT_ACCESS_EXPIRE_MINUTES: 访问令牌有效期（分钟）
            JWT_REFRESH_EXPIRE_DAYS: 刷新令牌有效期（天）

        Returns:
            AuthConfig实例
        """
        import os

        return cls(
            private_key_pem=os.getenv("JWT_PRIVATE_KEY"),
            public_key_pem=os.getenv("JWT_PUBLIC_KEY"),
            issuer=os.getenv("JWT_ISSUER", "zhineng-kb"),
            access_token_expire_minutes=int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "30")),
            refresh_token_expire_days=int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7")),
        )


class TokenBlacklist:
    """令牌黑名单管理器

    用于存储已吊销的令牌ID（JTI），防止被登出的令牌继续使用。
    支持自动清理过期记录。
    """

    def __init__(self, cleanup_interval: int = 3600):
        """初始化黑名单管理器

        Args:
            cleanup_interval: 自动清理间隔（秒）
        """
        self._blacklisted: Dict[str, int] = {}
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = int(datetime.now(tz=timezone.utc).timestamp())
        self._lock = asyncio.Lock()

    async def add(self, jti: str, exp: int) -> None:
        """添加令牌到黑名单

        Args:
            jti: JWT唯一标识符
            exp: 令牌过期时间（Unix时间戳）
        """
        async with self._lock:
            self._blacklisted[jti] = exp
            await self._cleanup_if_needed()

    async def is_blacklisted(self, jti: str) -> bool:
        """检查令牌是否在黑名单中

        Args:
            jti: JWT唯一标识符

        Returns:
            True如果令牌已被吊销
        """
        async with self._lock:
            await self._cleanup_if_needed()

            if jti not in self._blacklisted:
                return False

            # 检查是否已过期
            exp = self._blacklisted[jti]
            if int(datetime.now(tz=timezone.utc).timestamp()) > exp:
                del self._blacklisted[jti]
                return False

            return True

    async def remove(self, jti: str) -> bool:
        """从黑名单中移除令牌

        Args:
            jti: JWT唯一标识符

        Returns:
            True如果令牌存在并被移除
        """
        async with self._lock:
            if jti in self._blacklisted:
                del self._blacklisted[jti]
                return True
            return False

    async def _cleanup_if_needed(self) -> None:
        """如果需要则清理过期的黑名单记录"""
        now = int(datetime.now(tz=timezone.utc).timestamp())
        if now - self._last_cleanup < self._cleanup_interval:
            return

        expired_jtis = [jti for jti, exp in self._blacklisted.items() if now > exp]
        for jti in expired_jtis:
            del self._blacklisted[jti]

        self._last_cleanup = now
        if expired_jtis:
            logger.debug(f"清理了 {len(expired_jtis)} 条过期黑名单记录")

    async def clear(self) -> None:
        """清空黑名单"""
        async with self._lock:
            self._blacklisted.clear()

    def get_size(self) -> int:
        """获取黑名单当前大小

        Returns:
            黑名单中的记录数
        """
        return len(self._blacklisted)


class JWTAuth:
    """JWT认证管理器

    提供JWT令牌的生成、验证、刷新和黑名单管理功能。
    使用RS256非对称加密算法确保安全性。

    Example:
        >>> config = AuthConfig.from_env()
        >>> auth = JWTAuth(config)
        >>> token_pair = await auth.create_token_pair("user123", "alice", "admin")
        >>> payload = await auth.verify_access_token(token_pair.access_token)
        >>> await auth.revoke_token(payload.jti)
    """

    def __init__(
        self,
        config: Optional[AuthConfig] = None,
        blacklist: Optional[TokenBlacklist] = None,
    ):
        """初始化JWT认证管理器

        Args:
            config: 认证配置，默认生成临时密钥
            blacklist: 令牌黑名单，默认创建新实例
        """
        self.config = config or AuthConfig()
        self.blacklist = blacklist or TokenBlacklist(
            cleanup_interval=self.config.blacklist_cleanup_interval
        )

        # 加载密钥
        self._private_key = self._load_private_key()
        self._public_key = self._load_public_key()

        if not self._private_key:
            raise ValueError("无法加载RSA私钥")
        if not self._public_key:
            raise ValueError("无法加载RSA公钥")

    def _load_private_key(self) -> Optional[rsa.RSAPrivateKey]:
        """加载RSA私钥

        Returns:
            RSA私钥对象，失败返回None
        """
        try:
            return serialization.load_pem_private_key(
                self.config.private_key_pem.encode("utf-8"),
                password=None,
                backend=default_backend(),
            )
        except Exception as e:
            logger.error(f"加载私钥失败: {e}")
            return None

    def _load_public_key(self) -> Optional[rsa.RSAPublicKey]:
        """加载RSA公钥

        Returns:
            RSA公钥对象，失败返回None
        """
        try:
            return serialization.load_pem_public_key(
                self.config.public_key_pem.encode("utf-8"),
                backend=default_backend(),
            )
        except Exception as e:
            logger.error(f"加载公钥失败: {e}")
            return None

    def _create_payload(
        self,
        user_id: str,
        username: str,
        role: str,
        token_type: TokenType,
        permissions: Optional[Set[str]] = None,
    ) -> TokenPayload:
        """创建令牌载荷

        Args:
            user_id: 用户ID
            username: 用户名
            role: 用户角色
            token_type: 令牌类型
            permissions: 用户权限集合

        Returns:
            TokenPayload实例
        """
        now = datetime.now(tz=timezone.utc)

        # 设置过期时间
        if token_type == TokenType.ACCESS:
            expire_delta = timedelta(minutes=self.config.access_token_expire_minutes)
        else:
            expire_delta = timedelta(days=self.config.refresh_token_expire_days)

        exp = int((now + expire_delta).timestamp())
        iat = int(now.timestamp())
        jti = str(uuid.uuid4())

        return TokenPayload(
            user_id=user_id,
            username=username,
            role=role,
            permissions=permissions or set(),
            exp=exp,
            iat=iat,
            jti=jti,
            type=token_type.value,
            iss=self.config.issuer,
        )

    def _encode(self, payload: TokenPayload) -> str:
        """使用私钥编码JWT

        Args:
            payload: 令牌载荷

        Returns:
            JWT令牌字符串
        """
        payload_dict = payload.to_dict()

        # 移除permissions为空时的字段
        if not payload_dict["permissions"]:
            payload_dict.pop("permissions", None)

        return jwt.encode(
            payload_dict,
            self._private_key,
            algorithm=self.config.algorithm,
        )

    def _decode(self, token: str, verify: bool = True) -> Optional[Dict[str, Any]]:
        """解码JWT令牌

        Args:
            token: JWT令牌字符串
            verify: 是否验证签名

        Returns:
            令牌载荷字典，失败返回None
        """
        try:
            if verify:
                payload = jwt.decode(
                    token,
                    self._public_key,
                    algorithms=[self.config.algorithm],
                    issuer=self.config.issuer,
                    leeway=self.config.leeway,
                )
            else:
                # 不验证签名，仅解码
                parts = token.split(".")
                if len(parts) != 3:
                    return None

                # 解码payload部分
                payload_b64 = parts[1]
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                payload_bytes = base64.urlsafe_b64decode(payload_b64)
                payload = json.loads(payload_bytes)

            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("令牌已过期")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"无效令牌: {e}")
            return None
        except Exception as e:
            logger.error(f"解码令牌失败: {e}")
            return None

    async def create_token_pair(
        self,
        user_id: str,
        username: str,
        role: str = "user",
        permissions: Optional[Set[str]] = None,
    ) -> TokenPair:
        """创建访问令牌和刷新令牌对

        Args:
            user_id: 用户ID
            username: 用户名
            role: 用户角色
            permissions: 用户权限集合

        Returns:
            包含访问令牌和刷新令牌的TokenPair
        """
        access_payload = self._create_payload(
            user_id, username, role, TokenType.ACCESS, permissions
        )
        refresh_payload = self._create_payload(
            user_id, username, role, TokenType.REFRESH, permissions
        )

        access_token = self._encode(access_payload)
        refresh_token = self._encode(refresh_payload)

        logger.info(f"为用户 {username}({user_id}) 创建令牌对, " f"JTI: {access_payload.jti}")

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=access_payload.expires_in(),
        )

    def create_access_token(
        self,
        user_id: str,
        username: str,
        role: str = "user",
        permissions: Optional[Set[str]] = None,
    ) -> str:
        """创建访问令牌（同步方法）

        Args:
            user_id: 用户ID
            username: 用户名
            role: 用户角色
            permissions: 用户权限集合

        Returns:
            访问令牌字符串
        """
        payload = self._create_payload(user_id, username, role, TokenType.ACCESS, permissions)
        return self._encode(payload)

    def create_refresh_token(
        self,
        user_id: str,
        username: str,
        role: str = "user",
        permissions: Optional[Set[str]] = None,
    ) -> str:
        """创建刷新令牌（同步方法）

        Args:
            user_id: 用户ID
            username: 用户名
            role: 用户角色
            permissions: 用户权限集合

        Returns:
            刷新令牌字符串
        """
        payload = self._create_payload(user_id, username, role, TokenType.REFRESH, permissions)
        return self._encode(payload)

    async def verify_access_token(
        self, token: str, check_blacklist: bool = True
    ) -> Optional[TokenPayload]:
        """验证访问令牌

        Args:
            token: 访问令牌字符串
            check_blacklist: 是否检查黑名单

        Returns:
            TokenPayload实例，验证失败返回None
        """
        payload_dict = self._decode(token, verify=True)
        if not payload_dict:
            return None

        payload = TokenPayload.from_dict(payload_dict)

        # 验证令牌类型
        if payload.type != TokenType.ACCESS.value:
            logger.warning(f"令牌类型错误，期望: {TokenType.ACCESS.value}, 实际: {payload.type}")
            return None

        # 检查黑名单
        if check_blacklist:
            if await self.blacklist.is_blacklisted(payload.jti):
                logger.warning(f"令牌已在黑名单中: {payload.jti}")
                return None

        return payload

    async def verify_refresh_token(
        self, token: str, check_blacklist: bool = True
    ) -> Optional[TokenPayload]:
        """验证刷新令牌

        Args:
            token: 刷新令牌字符串
            check_blacklist: 是否检查黑名单

        Returns:
            TokenPayload实例，验证失败返回None
        """
        payload_dict = self._decode(token, verify=True)
        if not payload_dict:
            return None

        payload = TokenPayload.from_dict(payload_dict)

        # 验证令牌类型
        if payload.type != TokenType.REFRESH.value:
            logger.warning(f"令牌类型错误，期望: {TokenType.REFRESH.value}, 实际: {payload.type}")
            return None

        # 检查黑名单
        if check_blacklist:
            if await self.blacklist.is_blacklisted(payload.jti):
                logger.warning(f"令牌已在黑名单中: {payload.jti}")
                return None

        return payload

    async def refresh_access_token(self, refresh_token: str) -> Optional[TokenPair]:
        """使用刷新令牌获取新的访问令牌对

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的TokenPair，失败返回None
        """
        payload = await self.verify_refresh_token(refresh_token)
        if not payload:
            return None

        # 吊销旧的刷新令牌
        await self.revoke_token(payload.jti, payload.exp)

        # 创建新的令牌对
        return await self.create_token_pair(
            user_id=payload.user_id,
            username=payload.username,
            role=payload.role,
            permissions=payload.permissions,
        )

    async def revoke_token(self, jti: str, exp: int) -> None:
        """将令牌加入黑名单

        Args:
            jti: JWT唯一标识符
            exp: 令牌过期时间（Unix时间戳）
        """
        await self.blacklist.add(jti, exp)
        logger.info(f"令牌已吊销: {jti}")

    async def revoke_access_token(self, token: str) -> bool:
        """吊销访问令牌

        Args:
            token: 访问令牌

        Returns:
            是否吊销成功
        """
        payload_dict = self._decode(token, verify=False)
        if not payload_dict:
            return False

        jti = payload_dict.get("jti")
        exp = payload_dict.get("exp", 0)

        if not jti:
            return False

        await self.revoke_token(jti, exp)
        return True

    async def revoke_refresh_token(self, token: str) -> bool:
        """吊销刷新令牌

        Args:
            token: 刷新令牌

        Returns:
            是否吊销成功
        """
        payload_dict = self._decode(token, verify=False)
        if not payload_dict:
            return False

        jti = payload_dict.get("jti")
        exp = payload_dict.get("exp", 0)

        if not jti:
            return False

        await self.revoke_token(jti, exp)
        return True

    def decode_token(self, token: str) -> Optional[TokenPayload]:
        """解码令牌（不验证签名）

        用于调试和查看令牌内容，不应用于认证决策。

        Args:
            token: JWT令牌

        Returns:
            TokenPayload实例，失败返回None
        """
        payload_dict = self._decode(token, verify=False)
        if not payload_dict:
            return None
        return TokenPayload.from_dict(payload_dict)

    def get_public_key_pem(self) -> str:
        """获取公钥PEM字符串

        用于验证JWT签名的方使用公钥。

        Returns:
            公钥PEM格式字符串
        """
        return self.config.public_key_pem


# 全局认证器实例
_global_auth: Optional[JWTAuth] = None


def get_auth(config: Optional[AuthConfig] = None) -> JWTAuth:
    """获取全局JWT认证器实例

    Args:
        config: 认证配置，仅在首次调用时有效

    Returns:
        JWTAuth实例
    """
    global _global_auth
    if _global_auth is None:
        _global_auth = JWTAuth(config or AuthConfig())
    return _global_auth


def reset_auth() -> None:
    """重置全局认证器实例

    主要用于测试环境
    """
    global _global_auth
    _global_auth = None
