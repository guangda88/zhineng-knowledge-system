"""安全配置模块

提供安全相关配置，包括CORS、加密、认证等。
"""

from pydantic import Field, field_validator, ValidationInfo
from pydantic_settings import BaseSettings
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class SecurityConfig(BaseSettings):
    """安全配置类

    管理应用安全相关配置。
    """

    # CORS配置
    ALLOWED_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:8001",
            "http://100.66.1.8:8008",
            "http://100.66.1.8:8008/#"
        ],
        description="允许的CORS来源"
    )
    ALLOWED_CREDENTIALS: bool = Field(
        default=True,
        description="允许携带凭证"
    )
    ALLOWED_METHODS: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="允许的HTTP方法"
    )
    ALLOWED_HEADERS: List[str] = Field(
        default=["*"],
        description="允许的HTTP头"
    )

    # API密钥配置
    DEEPSEEK_API_KEY: Optional[str] = Field(
        default=None,
        description="DeepSeek API密钥"
    )
    BGE_API_KEY: Optional[str] = Field(
        default=None,
        description="BGE API密钥"
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API密钥"
    )

    # 加密配置
    SECRET_KEY: Optional[str] = Field(
        default=None,
        description="应用密钥（用于JWT等）"
    )
    ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        description="加密密钥"
    )

    # JWT配置
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT算法"
    )
    JWT_EXPIRATION: int = Field(
        default=3600,
        ge=60,
        description="JWT过期时间（秒）"
    )

    # 速率限制
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="是否启用速率限制"
    )
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=60,
        ge=1,
        description="每分钟请求限制"
    )
    RATE_LIMIT_PER_HOUR: int = Field(
        default=1000,
        ge=1,
        description="每小时请求限制"
    )

    # 安全头
    ENABLE_SECURITY_HEADERS: bool = Field(
        default=True,
        description="是否启用安全头"
    )

    # 管理API密钥（逗号分隔字符串）
    ADMIN_API_KEYS: str = Field(
        default="",
        description="管理端点API密钥，逗号分隔"
    )

    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v, info):
        """验证密钥"""
        if info.data.get("ENVIRONMENT") == "production" and not v:
            raise ValueError("SECRET_KEY is required in production")
        return v

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}

    def __repr__(self) -> str:
        """配置字符串表示"""
        return (
            f"SecurityConfig("
            f"ALLOWED_ORIGINS={len(self.ALLOWED_ORIGINS)} origins, "
            f"CREDENTIALS={self.ALLOWED_CREDENTIALS}, "
            f"RATE_LIMIT={self.RATE_LIMIT_ENABLED}"
            f")"
        )
