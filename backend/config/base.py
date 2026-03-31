"""配置基类模块

提供基础配置类和通用配置项。
"""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BaseConfig(BaseSettings):
    """基础配置类

    提供应用的基础配置项，包括环境、API、日志等。
    """

    # 环境配置
    ENVIRONMENT: str = Field(
        default="development",
        description="运行环境：development, testing, production"
    )
    DEBUG: bool = Field(
        default=False,
        description="调试模式"
    )

    # API配置
    API_HOST: str = Field(
        default="0.0.0.0",
        description="API服务监听地址"
    )
    API_PORT: int = Field(
        default=8000,
        description="API服务端口"
    )

    # 日志配置
    LOG_LEVEL: str = Field(
        default="INFO",
        description="日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式"
    )

    # 应用信息
    APP_NAME: str = Field(
        default="智能知识系统",
        description="应用名称"
    )
    APP_VERSION: str = Field(
        default="1.0.0",
        description="应用版本"
    )

    # 检索配置
    MAX_RESULTS: int = Field(
        default=10,
        ge=1,
        le=100,
        description="最大搜索结果数"
    )
    SIMILARITY_THRESHOLD: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="相似度阈值"
    )

    # BGE嵌入配置
    BGE_API_URL: Optional[str] = Field(
        default=None,
        description="BGE嵌入API地址"
    )
    EMBEDDING_DIM: int = Field(
        default=512,
        description="嵌入向量维度（bge-small-zh-v1.5=512, bge-large-zh-v1.5=1024）"
    )

    # DeepSeek配置
    DEEPSEEK_API_URL: Optional[str] = Field(
        default=None,
        description="DeepSeek API地址"
    )
    DEEPSEEK_MODEL: str = Field(
        default="deepseek-chat",
        description="DeepSeek模型名称"
    )

    # 分类配置
    VALID_CATEGORIES: list = Field(
        default=["气功", "中医", "儒家"],
        description="有效的分类列表"
    )

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}

    def __repr__(self) -> str:
        """配置字符串表示"""
        return (
            f"BaseConfig("
            f"ENVIRONMENT={self.ENVIRONMENT}, "
            f"API_HOST={self.API_HOST}, "
            f"API_PORT={self.API_PORT}, "
            f"LOG_LEVEL={self.LOG_LEVEL}"
            f")"
        )
