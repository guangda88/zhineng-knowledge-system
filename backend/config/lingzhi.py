"""灵知系统配置模块

提供灵知古籍知识系统的特定配置。
包含 LingFlow 搜索引擎的配置参数。
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class LingZhiConfig(BaseSettings):
    """灵知系统配置类

    管理灵知古籍知识系统的特定配置。
    """

    # 缓存配置
    ENABLE_CACHE: bool = Field(default=True, description="是否启用缓存")
    CACHE_TTL: int = Field(default=3600, ge=60, description="缓存过期时间（秒）")

    # 查询配置
    QUERY_TIMEOUT: float = Field(default=30.0, ge=1.0, description="查询超时时间（秒）")

    # 连接池配置
    MAX_CONNECTIONS: int = Field(default=10, ge=1, le=50, description="最大连接数")
    CONNECTION_TIMEOUT: int = Field(default=10, ge=1, le=60, description="连接超时时间（秒）")

    # LingFlow 搜索引擎配置
    LINGFLOW_ENABLED: bool = Field(default=True, description="是否启用 LingFlow 搜索引擎")
    LINGFLOW_DEFAULT_MODE: str = Field(
        default="fulltext", description="LingFlow 默认搜索模式（fulltext/fuzzy/broad）"
    )
    LINGFLOW_SEARCH_TIMEOUT: float = Field(
        default=60.0, ge=5.0, description="LingFlow 搜索超时时间（秒）"
    )
    LINGFLOW_SNIPPET_LENGTH: int = Field(
        default=300, ge=50, le=1000, description="搜索结果上下文片段长度（字符数）"
    )
    LINGFLOW_UNIFIED_PAGE_SIZE: int = Field(
        default=20, ge=1, le=100, description="统一搜索默认每页数量"
    )

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}
