"""标注服务基类

定义标注系统的通用接口
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AnnotationStatus(Enum):
    """标注状态"""

    PENDING = "pending"  # 待标注
    IN_PROGRESS = "in_progress"  # 标注中
    COMPLETED = "completed"  # 已完成
    REVIEWED = "reviewed"  # 已审核
    REJECTED = "rejected"  # 已拒绝


class AnnotationType(Enum):
    """标注类型"""

    OCR = "ocr"  # OCR文本标注
    TRANSCRIPTION = "transcription"  # 语音转写标注
    VERIFICATION = "verification"  # 内容验证标注


@dataclass
class AnnotationTask:
    """标注任务"""

    task_id: str
    annotation_type: AnnotationType
    original_text: str
    original_source: str  # 原始文件路径或URL
    status: AnnotationStatus = AnnotationStatus.PENDING
    corrected_text: Optional[str] = None
    corrections: List[Dict] = None
    annotator: Optional[str] = None
    reviewer: Optional[str] = None
    created_at: datetime = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.corrections is None:
            self.corrections = []


@dataclass
class Correction:
    """校正记录"""

    position: int  # 字符位置
    original: str  # 原始文本
    corrected: str  # 校正后文本
    correction_type: str  # deletion, insertion, substitution
    confidence: float  # 校正置信度


class BaseAnnotator(ABC):
    """标注器基类"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def create_task(
        self, source_content: str, source_path: str, metadata: Dict[str, Any] = None
    ) -> AnnotationTask:
        """
        创建标注任务

        Args:
            source_content: 原始内容（OCR结果或转写结果）
            source_path: 原始文件路径
            metadata: 额外元数据

        Returns:
            AnnotationTask: 创建的标注任务
        """

    @abstractmethod
    async def submit_correction(
        self, task_id: str, corrected_text: str, corrections: List[Correction], annotator: str
    ) -> AnnotationTask:
        """
        提交校正

        Args:
            task_id: 任务ID
            corrected_text: 校正后的文本
            corrections: 校正详情
            annotator: 标注人

        Returns:
            AnnotationTask: 更新后的任务
        """

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[AnnotationTask]:
        """
        获取标注任务

        Args:
            task_id: 任务ID

        Returns:
            AnnotationTask: 标注任务，不存在则返回None
        """

    @abstractmethod
    async def list_pending_tasks(self, limit: int = 10) -> List[AnnotationTask]:
        """
        列出待标注任务

        Args:
            limit: 返回数量限制

        Returns:
            List[AnnotationTask]: 待标注任务列表
        """

    def calculate_accuracy_improvement(self, original: str, corrected: str) -> Dict[str, Any]:
        """
        计算准确率提升

        Args:
            original: 原始文本
            corrected: 校正后文本

        Returns:
            Dict: 包含改进指标
        """
        # 计算字符错误率（CER）
        cer_before = self._calculate_cer(original, original)
        cer_after = self._calculate_cer(original, corrected)

        improvement = {
            "cer_before": cer_before,
            "cer_after": cer_after,
            "cer_improvement": cer_before - cer_after,
            "improvement_percentage": (
                ((cer_before - cer_after) / cer_before * 100) if cer_before > 0 else 0
            ),
        }

        return improvement

    def _calculate_cer(self, reference: str, hypothesis: str) -> float:
        """
        计算字符错误率

        Args:
            reference: 参考文本
            hypothesis: 假设文本

        Returns:
            float: 字符错误率（0-1）
        """
        if not reference:
            return 0.0

        # 简化实现：基于编辑距离
        import rapidfuzz.distance.Levenshtein as Levenshtein

        distance = Levenshtein.distance(reference, hypothesis)
        cer = distance / len(reference)

        return cer

    def _generate_task_id(self) -> str:
        """生成任务ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import uuid

        unique_id = str(uuid.uuid4())[:8]
        return f"{self.__class__.__name__}_{timestamp}_{unique_id}"
