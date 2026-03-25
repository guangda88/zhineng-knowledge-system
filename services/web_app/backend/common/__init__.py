# -*- coding: utf-8 -*-
"""
通用工具模块
Common Utilities Module

提供项目中通用的工具函数和类
"""

from .exceptions import (
    CommonException,
    ValidationError,
    FileProcessingError,
    ModelNotFoundError,
    ConfigurationError,
)
from .validators import (
    validate_file_size,
    validate_file_type,
    validate_file_path,
    validate_audio_file,
    validate_image_file,
    validate_video_file,
    get_file_mimetype,
    sanitize_filename,
)
from .file_handler import (
    TempFileHandler,
    FileManager,
    ensure_directory,
    safe_delete,
    get_file_hash,
)

# 缓存相关导入
try:
    from .cache_manager import (
        CacheManager,
        CacheKeyPattern,
        CacheTTL,
        MemoryCacheBackend,
        RedisCacheBackend,
        cached,
        cache_invalidate,
        get_cache_manager,
        set_cache_manager,
    )
    from .cache_service import (
        UserCacheService,
        DocumentCacheService,
        SearchCacheService,
        HotwordCacheService,
        SessionCacheService,
        get_user_cache_service,
        get_document_cache_service,
        get_search_cache_service,
        get_hotword_cache_service,
        get_session_cache_service,
    )
    from .cache_middleware import (
        CacheMiddleware,
        setup_cache_middleware,
        cache_response,
        invalidate_cache_pattern,
        cached_endpoint,
        get_cache,
        CacheWarmer,
        CacheControlHeaders,
    )

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

__all__ = [
    # Exceptions
    "CommonException",
    "ValidationError",
    "FileProcessingError",
    "ModelNotFoundError",
    "ConfigurationError",
    # Validators
    "validate_file_size",
    "validate_file_type",
    "validate_file_path",
    "validate_audio_file",
    "validate_image_file",
    "validate_video_file",
    "get_file_mimetype",
    "sanitize_filename",
    # File Handlers
    "TempFileHandler",
    "FileManager",
    "ensure_directory",
    "safe_delete",
    "get_file_hash",
]

# 缓存相关导出
if CACHE_AVAILABLE:
    __all__.extend(
        [
            # Cache Manager
            "CacheManager",
            "CacheKeyPattern",
            "CacheTTL",
            "MemoryCacheBackend",
            "RedisCacheBackend",
            "cached",
            "cache_invalidate",
            "get_cache_manager",
            "set_cache_manager",
            # Cache Services
            "UserCacheService",
            "DocumentCacheService",
            "SearchCacheService",
            "HotwordCacheService",
            "SessionCacheService",
            "get_user_cache_service",
            "get_document_cache_service",
            "get_search_cache_service",
            "get_hotword_cache_service",
            "get_session_cache_service",
            # Cache Middleware
            "CacheMiddleware",
            "setup_cache_middleware",
            "cache_response",
            "invalidate_cache_pattern",
            "cached_endpoint",
            "get_cache",
            "CacheWarmer",
            "CacheControlHeaders",
        ]
    )
