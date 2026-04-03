"""
智能气功资料维度管理服务

提供维度解析、批量打标、覆盖率统计等功能
"""

from .batch_tagger import (
    QigongBatchTagger,
    batch_tag_qigong_docs,
    get_tagging_coverage,
)
from .content_parser import (
    QigongContentParser,
    parse_qigong_from_content,
)
from .path_parser import (
    DimensionResult,
    Discipline,
    MediaType,
    QigongPathParser,
    TeachingLevel,
    TheorySystem,
    parse_qigong_dimensions,
)

__all__ = [
    # 路径解析
    "QigongPathParser",
    "DimensionResult",
    "TeachingLevel",
    "Discipline",
    "MediaType",
    "TheorySystem",
    "parse_qigong_dimensions",
    # 内容解析
    "QigongContentParser",
    "parse_qigong_from_content",
    # 批量打标
    "QigongBatchTagger",
    "batch_tag_qigong_docs",
    "get_tagging_coverage",
]
