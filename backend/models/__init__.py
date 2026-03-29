"""
Backend 数据模型模块
"""

# 灵知模型
from .lingzhi import (
    LingZhiBook,
    LingZhiChapter,
    LingZhiCategory,
    ExtractionLog
)

__all__ = [
    # 灵知模型
    "LingZhiBook",
    "LingZhiChapter",
    "LingZhiCategory",
    "ExtractionLog",
]
