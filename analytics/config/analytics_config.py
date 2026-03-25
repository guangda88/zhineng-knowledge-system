# -*- coding: utf-8 -*-
"""
数据分析配置
Data Analysis Configuration

配置数据分析相关的参数，包括数据源、分析目标、输出格式等
"""

from typing import Dict, List, Any
from enum import Enum
from pathlib import Path

# =============================================================================
# 数据源配置
# =============================================================================

class DataSourceType(Enum):
    """数据源类型"""
    POSTGRES = "postgres"
    MILVUS = "milvus"
    ELASTICSEARCH = "elasticsearch"
    REDIS = "redis"
    FILE = "file"

DATA_SOURCES = {
    DataSourceType.POSTGRES: {
        "host": "localhost",
        "port": 5432,
        "database": "tcm_knowledge",
        "user": "tcmuser",
        "password": "tcmpassword",
        "pool_size": 10,
        "max_overflow": 20,
    },
    DataSourceType.MILVUS: {
        "host": "localhost",
        "port": 19530,
        "collection_name": "document_chunks",
    },
    DataSourceType.ELASTICSEARCH: {
        "host": "localhost",
        "port": 9200,
        "index_name": "document_index",
    },
    DataSourceType.REDIS: {
        "host": "localhost",
        "port": 6379,
        "db": 0,
    },
}

# =============================================================================
# 分析类型配置
# =============================================================================

class AnalysisType(Enum):
    """分析类型"""
    DATA_QUALITY = "data_quality"          # 数据质量分析
    PERFORMANCE = "performance"              # 性能分析
    SEARCH_EFFECTIVENESS = "search"         # 搜索效果分析
    USER_BEHAVIOR = "user_behavior"        # 用户行为分析
    SYSTEM_HEALTH = "system_health"         # 系统健康分析
    STORAGE_USAGE = "storage_usage"         # 存储使用分析
    QUERY_PATTERN = "query_pattern"          # 查询模式分析

ANALYSIS_CONFIGS = {
    AnalysisType.DATA_QUALITY: {
        "enabled": True,
        "metrics": [
            "completeness",      # 完整性
            "accuracy",          # 准确性
            "consistency",       # 一致性
            "validity",          # 有效性
            "uniqueness",        # 唯一性
        ],
        "tables": ["users", "documents", "document_chunks", "annotations"],
    },
    AnalysisType.PERFORMANCE: {
        "enabled": True,
        "metrics": [
            "query_response_time",      # 查询响应时间
            "index_build_time",         # 索引构建时间
            "throughput",               # 吞吐量
            "concurrency",              # 并发能力
        ],
        "test_sizes": [100, 1000, 10000, 100000],
    },
    AnalysisType.SEARCH_EFFECTIVENESS: {
        "enabled": True,
        "metrics": [
            "precision",               # 精确率
            "recall",                  # 召回率
            "f1_score",                # F1分数
            "relevance_ranking",        # 相关性排序
        ],
        "test_queries": 100,
    },
    AnalysisType.USER_BEHAVIOR: {
        "enabled": True,
        "metrics": [
            "session_duration",         # 会话时长
            "search_frequency",         # 搜索频率
            "document_access_pattern",   # 文档访问模式
            "feature_usage",           # 功能使用情况
        ],
        "time_range_days": 30,
    },
    AnalysisType.SYSTEM_HEALTH: {
        "enabled": True,
        "metrics": [
            "cpu_usage",               # CPU使用率
            "memory_usage",            # 内存使用率
            "disk_io",                 # 磁盘I/O
            "network_io",              # 网络I/O
            "service_availability",     # 服务可用性
        ],
        "monitoring_interval_seconds": 60,
    },
    AnalysisType.STORAGE_USAGE: {
        "enabled": True,
        "metrics": [
            "total_size",              # 总大小
            "growth_rate",             # 增长率
            "file_type_distribution",   # 文件类型分布
            "age_distribution",        # 文档年龄分布
        ],
        "threshold_percent": 80,      # 告警阈值
    },
    AnalysisType.QUERY_PATTERN: {
        "enabled": True,
        "metrics": [
            "query_length_distribution", # 查询长度分布
            "query_term_frequency",   # 查询词频率
            "query_type_distribution", # 查询类型分布
            "failed_query_analysis",  # 失败查询分析
        ],
        "analysis_days": 7,
    },
}

# =============================================================================
# 输出配置
# =============================================================================

class OutputFormat(Enum):
    """输出格式"""
    JSON = "json"
    CSV = "csv"
    HTML = "html"
    PDF = "pdf"
    CONSOLE = "console"

OUTPUT_CONFIG = {
    "default_format": OutputFormat.JSON,
    "report_dir": Path("/home/ai/zhineng-knowledge-system/analytics/reports"),
    "data_dir": Path("/home/ai/zhineng-knowledge-system/analytics/data"),
    "include_charts": True,
    "chart_format": "png",
    "chart_dpi": 300,
}

# =============================================================================
# 数据生成配置
# =============================================================================

DATA_GENERATION_CONFIG = {
    "users": {
        "count": 100,
        "min": 1,
        "max": 1000,
    },
    "documents": {
        "count": 1000,
        "types": ["txt", "md", "pdf", "docx", "xlsx"],
        "size_range": (1024, 10 * 1024 * 1024),  # 1KB - 10MB
    },
    "annotations": {
        "count_per_document": 5,
    },
    "search_history": {
        "count_per_user": 50,
    },
}

# =============================================================================
# 性能测试配置
# =============================================================================

PERFORMANCE_TEST_CONFIG = {
    "concurrency_levels": [1, 10, 50, 100],
    "query_types": ["simple", "complex", "full_text", "semantic"],
    "warm_up_iterations": 10,
    "test_iterations": 100,
    "timeout_seconds": 30,
}

# =============================================================================
# 数据质量规则
# =============================================================================

DATA_QUALITY_RULES = {
    "users": {
        "username_min_length": 3,
        "username_max_length": 50,
        "email_format": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "password_min_length": 8,
        "required_fields": ["username", "email", "password_hash"],
    },
    "documents": {
        "title_max_length": 500,
        "content_min_length": 10,
        "file_extensions": [".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv"],
        "max_file_size": 50 * 1024 * 1024,  # 50MB
        "required_fields": ["title", "content", "uploader_id"],
    },
    "document_chunks": {
        "min_chunk_size": 100,
        "max_chunk_size": 10000,
        "overlap_ratio": 0.1,
        "required_fields": ["document_id", "content", "chunk_index"],
    },
}

# =============================================================================
# 采样配置
# =============================================================================

SAMPLING_CONFIG = {
    "enabled": True,
    "sample_size_percent": 10,  # 采样百分比
    "max_sample_size": 10000,   # 最大样本数
    "sampling_method": "random",  # random, stratified, systematic
}

# =============================================================================
# 缓存配置
# =============================================================================

CACHE_CONFIG = {
    "enabled": True,
    "cache_dir": Path("/home/ai/zhineng-knowledge-system/analytics/data/cache"),
    "ttl_seconds": 3600,  # 1小时
    "max_size_mb": 1000,
}
