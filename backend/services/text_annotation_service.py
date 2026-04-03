"""
文本标注服务（Text Annotation Service）

文字处理工程流A-5的服务层

功能：
1. 标注CRUD操作
2. 标注导出（JSON/CSV/XML）
3. 标注统计和分析
4. 协作功能（评论）
"""

import csv
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.models.text_annotation import (
    AnnotationComment,
    AnnotationTag,
    TextAnnotation,
)

logger = logging.getLogger(__name__)


class TextAnnotationService:
    """文本标注服务"""

    def __init__(self, db_session: Session):
        """初始化服务

        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    # ========== CRUD操作 ==========

    def create_annotation(
        self,
        text_block_id: int,
        annotation_type: str,
        content: str,
        start_pos: Optional[int] = None,
        end_pos: Optional[int] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        importance: str = "medium",
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        attributes: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> TextAnnotation:
        """创建标注

        Args:
            text_block_id: 文本块ID
            annotation_type: 标注类型
            content: 标注内容
            start_pos: 开始位置
            end_pos: 结束位置
            start_line: 开始行
            end_line: 结束行
            importance: 重要性
            confidence: 置信度
            metadata: 元数据
            attributes: 属性
            created_by: 创建人

        Returns:
            创建的标注对象
        """
        annotation = TextAnnotation(
            text_block_id=text_block_id,
            annotation_type=annotation_type,
            content=content,
            start_pos=start_pos,
            end_pos=end_pos,
            start_line=start_line,
            end_line=end_line,
            importance=importance,
            confidence=confidence,
            metadata=metadata or {},
            attributes=attributes or {},
            created_by=created_by,
        )

        self.db.add(annotation)
        self.db.commit()
        self.db.refresh(annotation)

        logger.info(f"创建标注: id={annotation.id}, type={annotation_type}")
        return annotation

    def get_annotation(self, annotation_id: int) -> Optional[TextAnnotation]:
        """获取标注

        Args:
            annotation_id: 标注ID

        Returns:
            标注对象或None
        """
        return self.db.query(TextAnnotation).filter(TextAnnotation.id == annotation_id).first()

    def update_annotation(
        self,
        annotation_id: int,
        content: Optional[str] = None,
        importance: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Optional[TextAnnotation]:
        """更新标注

        Args:
            annotation_id: 标注ID
            content: 新内容
            importance: 新重要性
            confidence: 新置信度
            metadata: 新元数据
            attributes: 新属性

        Returns:
            更新后的标注对象或None
        """
        annotation = self.get_annotation(annotation_id)
        if not annotation:
            return None

        if content is not None:
            annotation.content = content
        if importance is not None:
            annotation.importance = importance
        if confidence is not None:
            annotation.confidence = confidence
        if metadata is not None:
            annotation.extra_metadata = metadata
        if attributes is not None:
            annotation.attributes = attributes

        # 更新版本号
        annotation.version += 1
        annotation.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(annotation)

        logger.info(f"更新标注: id={annotation_id}, version={annotation.version}")
        return annotation

    def delete_annotation(self, annotation_id: int) -> bool:
        """删除标注

        Args:
            annotation_id: 标注ID

        Returns:
            是否成功删除
        """
        annotation = self.get_annotation(annotation_id)
        if not annotation:
            return False

        self.db.delete(annotation)
        self.db.commit()

        logger.info(f"删除标注: id={annotation_id}")
        return True

    # ========== 查询操作 ==========

    def list_annotations(
        self,
        text_block_id: Optional[int] = None,
        annotation_type: Optional[str] = None,
        importance: Optional[str] = None,
        created_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TextAnnotation]:
        """列出标注

        Args:
            text_block_id: 文本块ID筛选
            annotation_type: 标注类型筛选
            importance: 重要性筛选
            created_by: 创建人筛选
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            标注列表
        """
        query = self.db.query(TextAnnotation)

        # 应用筛选条件
        if text_block_id is not None:
            query = query.filter(TextAnnotation.text_block_id == text_block_id)
        if annotation_type is not None:
            query = query.filter(TextAnnotation.annotation_type == annotation_type)
        if importance is not None:
            query = query.filter(TextAnnotation.importance == importance)
        if created_by is not None:
            query = query.filter(TextAnnotation.created_by == created_by)

        # 排序和分页
        query = query.order_by(TextAnnotation.created_at.desc())
        query = query.limit(limit).offset(offset)

        return query.all()

    def search_annotations(self, keyword: str, limit: int = 100) -> List[TextAnnotation]:
        """搜索标注

        Args:
            keyword: 关键词
            limit: 返回数量限制

        Returns:
            标注列表
        """
        query = self.db.query(TextAnnotation).filter(
            or_(
                TextAnnotation.content.contains(keyword),
                TextAnnotation.metadata["key"].astext.contains(keyword),
            )
        )

        return query.limit(limit).all()

    # ========== 统计分析 ==========

    def get_annotation_statistics(self, text_block_id: Optional[int] = None) -> Dict[str, Any]:
        """获取标注统计信息

        Args:
            text_block_id: 文本块ID（可选）

        Returns:
            统计信息字典
        """
        query = self.db.query(TextAnnotation)

        if text_block_id is not None:
            query = query.filter(TextAnnotation.text_block_id == text_block_id)

        annotations = query.all()

        # 按类型统计
        type_counts = {}
        for ann in annotations:
            type_counts[ann.annotation_type] = type_counts.get(ann.annotation_type, 0) + 1

        # 按重要性统计
        importance_counts = {}
        for ann in annotations:
            importance_counts[ann.importance] = importance_counts.get(ann.importance, 0) + 1

        # 平均置信度
        avg_confidence = (
            sum(ann.confidence for ann in annotations) / len(annotations) if annotations else 0.0
        )

        return {
            "total_annotations": len(annotations),
            "type_distribution": type_counts,
            "importance_distribution": importance_counts,
            "average_confidence": avg_confidence,
        }

    # ========== 导出功能 ==========

    def export_annotations(
        self,
        format: str = "json",
        text_block_id: Optional[int] = None,
        annotation_type: Optional[str] = None,
        export_name: Optional[str] = None,
    ) -> tuple[str, str]:
        """导出标注

        Args:
            format: 导出格式（json/csv/xml）
            text_block_id: 文本块ID筛选
            annotation_type: 标注类型筛选
            export_name: 导出名称

        Returns:
            (文件内容, MIME类型)
        """
        # 获取标注
        annotations = self.list_annotations(
            text_block_id=text_block_id, annotation_type=annotation_type, limit=10000  # 大量导出
        )

        # 转换为字典
        annotation_dicts = [ann.to_dict() for ann in annotations]

        # 根据格式导出
        if format.lower() == "json":
            return self._export_json(annotation_dicts), "application/json"
        elif format.lower() == "csv":
            return self._export_csv(annotation_dicts), "text/csv"
        elif format.lower() == "xml":
            return self._export_xml(annotation_dicts), "application/xml"
        else:
            raise ValueError(f"不支持的导出格式: {format}")

    def _export_json(self, annotations: List[Dict[str, Any]]) -> str:
        """导出为JSON"""
        return json.dumps(annotations, ensure_ascii=False, indent=2)

    def _export_csv(self, annotations: List[Dict[str, Any]]) -> str:
        """导出为CSV"""
        output = StringIO()

        if not annotations:
            return ""

        # CSV字段
        fieldnames = [
            "id",
            "text_block_id",
            "annotation_type",
            "content",
            "importance",
            "confidence",
            "created_by",
            "created_at",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for ann in annotations:
            # 只写入指定字段
            row = {k: ann.get(k, "") for k in fieldnames}
            writer.writerow(row)

        return output.getvalue()

    def _export_xml(self, annotations: List[Dict[str, Any]]) -> str:
        """导出为XML"""
        root = ET.Element("annotations")

        for ann in annotations:
            ann_elem = ET.SubElement(root, "annotation")
            ann_elem.set("id", str(ann["id"]))

            for key, value in ann.items():
                if key == "id":
                    continue
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)

                elem = ET.SubElement(ann_elem, key)
                elem.text = str(value)

        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    # ========== 评论功能 ==========

    def add_comment(self, annotation_id: int, content: str, author: str) -> AnnotationComment:
        """添加评论

        Args:
            annotation_id: 标注ID
            content: 评论内容
            author: 作者

        Returns:
            评论对象
        """
        comment = AnnotationComment(annotation_id=annotation_id, content=content, author=author)

        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)

        logger.info(f"添加评论: annotation_id={annotation_id}, comment_id={comment.id}")
        return comment

    def get_comments(self, annotation_id: int) -> List[AnnotationComment]:
        """获取标注的所有评论

        Args:
            annotation_id: 标注ID

        Returns:
            评论列表
        """
        return (
            self.db.query(AnnotationComment)
            .filter(AnnotationComment.annotation_id == annotation_id)
            .order_by(AnnotationComment.created_at.asc())
            .all()
        )


class AnnotationTagService:
    """标注标签服务"""

    def __init__(self, db_session: Session):
        """初始化服务

        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def create_tag(
        self,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None,
        parent_id: Optional[int] = None,
    ) -> AnnotationTag:
        """创建标签

        Args:
            name: 标签名称
            description: 描述
            color: 颜色
            parent_id: 父标签ID

        Returns:
            标签对象
        """
        tag = AnnotationTag(name=name, description=description, color=color, parent_id=parent_id)

        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)

        logger.info(f"创建标签: id={tag.id}, name={name}")
        return tag

    def list_tags(self) -> List[AnnotationTag]:
        """列出所有标签"""
        return self.db.query(AnnotationTag).order_by(AnnotationTag.usage_count.desc()).all()

    def get_tag(self, tag_id: int) -> Optional[AnnotationTag]:
        """获取标签

        Args:
            tag_id: 标签ID

        Returns:
            标签对象或None
        """
        return self.db.query(AnnotationTag).filter(AnnotationTag.id == tag_id).first()

    def increment_usage(self, tag_id: int):
        """增加标签使用次数

        Args:
            tag_id: 标签ID
        """
        tag = self.get_tag(tag_id)
        if tag:
            tag.usage_count += 1
            self.db.commit()


__all__ = [
    "TextAnnotationService",
    "AnnotationTagService",
]
