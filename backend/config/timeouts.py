"""统一超时配置

优化目标：
1. 统一所有超时配置
2. 根据操作类型设置合理的超时值
3. 提高系统响应速度和可靠性
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OperationType(Enum):
    """操作类型"""

    # AI API操作
    AI_CHAT = "ai_chat"  # 简单对话
    AI_REASONING = "ai_reasoning"  # 复杂推理
    AI_CODE_GEN = "ai_code_gen"  # 代码生成
    AI_EMBEDDING = "ai_embedding"  # 向量嵌入

    # 数据库操作
    DB_QUERY = "db_query"  # 普通查询
    DB_WRITE = "db_write"  # 写操作
    DB_BATCH = "db_batch"  # 批量操作

    # HTTP请求
    HTTP_API = "http_api"  # API调用
    HTTP_DOWNLOAD = "http_download"  # 文件下载
    HTTP_UPLOAD = "http_upload"  # 文件上传

    # 内部操作
    CACHE_GET = "cache_get"  # 缓存读取
    CACHE_SET = "cache_set"  # 缓存写入
    LOCK_ACQUIRE = "lock_acquire"  # 锁获取


@dataclass
class TimeoutConfig:
    """超时配置"""

    default: float = 30.0
    min_retry_delay: float = 1.0
    max_retry_delay: float = 60.0

    # AI API超时（根据任务复杂度）
    ai_chat_timeout: float = 30.0  # 简单对话：30秒
    ai_reasoning_timeout: float = 60.0  # 复杂推理：60秒
    ai_code_gen_timeout: float = 45.0  # 代码生成：45秒
    ai_embedding_timeout: float = 20.0  # 向量嵌入：20秒

    # 数据库超时
    db_query_timeout: float = 5.0  # 查询：5秒（优化）
    db_write_timeout: float = 10.0  # 写操作：10秒
    db_batch_timeout: float = 30.0  # 批量：30秒
    db_connection_timeout: float = 10.0  # 连接：10秒
    db_command_timeout: float = 10.0  # 命令：10秒（优化）

    # HTTP超时
    http_api_timeout: float = 30.0  # API调用：30秒
    http_connect_timeout: float = 10.0  # 连接：10秒
    http_read_timeout: float = 20.0  # 读取：20秒
    http_download_timeout: float = 120.0  # 下载：2分钟

    # 缓存超时
    cache_timeout: float = 2.0  # 缓存操作：2秒
    redis_timeout: float = 5.0  # Redis：5秒

    # 其他超时
    lock_timeout: float = 5.0  # 锁：5秒
    health_check_timeout: float = 3.0  # 健康检查：3秒

    def get_timeout(self, operation: OperationType) -> float:
        """获取指定操作的超时时间"""
        mapping = {
            OperationType.AI_CHAT: self.ai_chat_timeout,
            OperationType.AI_REASONING: self.ai_reasoning_timeout,
            OperationType.AI_CODE_GEN: self.ai_code_gen_timeout,
            OperationType.AI_EMBEDDING: self.ai_embedding_timeout,
            OperationType.DB_QUERY: self.db_query_timeout,
            OperationType.DB_WRITE: self.db_write_timeout,
            OperationType.DB_BATCH: self.db_batch_timeout,
            OperationType.HTTP_API: self.http_api_timeout,
            OperationType.HTTP_DOWNLOAD: self.http_download_timeout,
            OperationType.CACHE_GET: self.cache_timeout,
            OperationType.CACHE_SET: self.cache_timeout,
            OperationType.LOCK_ACQUIRE: self.lock_timeout,
        }
        return mapping.get(operation, self.default)

    def get_retry_delays(self) -> tuple[float, float]:
        """获取重试延迟配置"""
        return self.min_retry_delay, self.max_retry_delay


# 全局配置实例
_global_config: Optional[TimeoutConfig] = None


def get_timeout_config() -> TimeoutConfig:
    """获取全局超时配置"""
    global _global_config
    if _global_config is None:
        _global_config = TimeoutConfig()
    return _global_config


def get_timeout(operation: OperationType) -> float:
    """便捷函数：获取超时值"""
    return get_timeout_config().get_timeout(operation)


# 预定义的超时值常量（向后兼容）
class Timeouts:
    """超时常量（向后兼容）"""

    # AI API
    AI_CHAT = 30.0
    AI_REASONING = 60.0
    AI_CODE_GEN = 45.0
    AI_EMBEDDING = 20.0

    # 数据库（优化后）
    DB_QUERY = 5.0
    DB_WRITE = 10.0
    DB_CONNECTION = 10.0
    DB_COMMAND = 10.0

    # HTTP
    HTTP_API = 30.0
    HTTP_CONNECT = 10.0
    HTTP_READ = 20.0

    # 缓存
    CACHE = 2.0
    REDIS = 5.0

    # 其他
    LOCK = 5.0
    HEALTH_CHECK = 3.0


def get_env_timeout(operation: OperationType, default: float) -> float:
    """从环境变量获取超时值"""
    env_key = f"TIMEOUT_{operation.value.upper()}"
    return float(os.getenv(env_key, str(default)))
