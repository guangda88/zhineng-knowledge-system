"""
文本标注数据模型（Text Annotation Models）

文字处理工程流A-5的数据模型

标注类型：
1. 关键词标注（keyword）
2. 主题标注（topic）
3. 重要性标注（importance）
4. 情感标注（sentiment）
5. 实体标注（entity）
6. 自定义标注（custom）
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.core.database import Base


class AnnotationType(str, Enum):
    """标注类型"""

    KEYWORD = "keyword"  # 关键词
    TOPIC = "topic"  # 主题
    IMPORTANCE = "importance"  # 重要性
    SENTIMENT = "sentiment"  # 情感
    ENTITY = "entity"  # 实体
    CUSTOM = "custom"  # 自定义


class AnnotationImportance(str, Enum):
    """标注重要性"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TextAnnotation(Base):
    """文本标注表"""

    __tablename__ = "text_annotations"

    id = Column(Integer, primary_key=True, index=True)
    text_block_id = Column(Integer, ForeignKey("text_blocks.id"), nullable=False, index=True)

    # 标注基本信息
    annotation_type = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)  # 标注内容

    # 位置信息
    start_pos = Column(Integer)  # 开始位置
    end_pos = Column(Integer)  # 结束位置
    start_line = Column(Integer)  # 开始行
    end_line = Column(Integer)  # 结束行

    # 属性
    importance = Column(String(20), default="medium")  # 重要性
    confidence = Column(Float, default=1.0)  # 置信度

    # 额外数据
    extra_metadata = Column("metadata", JSON, default=dict)
    attributes = Column(JSON, default=dict)  # 标注属性

    # 审计信息
    created_by = Column(String(100))  # 创建人
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, default=1)  # 版本号

    # 关系（TextBlock is a dataclass, not a SQLAlchemy model, so no relationship defined)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "text_block_id": self.text_block_id,
            "annotation_type": self.annotation_type,
            "content": self.content,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "importance": self.importance,
            "confidence": self.confidence,
            "metadata": self.extra_metadata or {},
            "attributes": self.attributes or {},
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "version": self.version,
        }


class AnnotationTag(Base):
    """标注标签表（用于分类和组织标注）"""

    __tablename__ = "annotation_tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    color = Column(String(20))  # 标签颜色（用于UI展示）
    parent_id = Column(Integer, ForeignKey("annotation_tags.id"))

    # 统计信息
    usage_count = Column(Integer, default=0)  # 使用次数

    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "parent_id": self.parent_id,
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AnnotationComment(Base):
    """标注评论表（用于协作）"""

    __tablename__ = "annotation_comments"

    id = Column(Integer, primary_key=True, index=True)
    annotation_id = Column(Integer, ForeignKey("text_annotations.id"), nullable=False, index=True)

    content = Column(Text, nullable=False)
    author = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    annotation = relationship("TextAnnotation")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "annotation_id": self.annotation_id,
            "content": self.content,
            "author": self.author,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AnnotationExport(Base):
    """标注导出记录表"""

    __tablename__ = "annotation_exports"

    id = Column(Integer, primary_key=True, index=True)
    export_name = Column(String(255), nullable=False)
    format = Column(String(20), nullable=False)  # json, csv, xml
    file_path = Column(String(500))
    filters = Column(JSON)  # 导出时使用的过滤条件
    status = Column(String(20), default="pending")  # pending, completed, failed
    error_message = Column(Text)

    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "export_name": self.export_name,
            "format": self.format,
            "file_path": self.file_path,
            "filters": self.filters or {},
            "status": self.status,
            "error_message": self.error_message,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
