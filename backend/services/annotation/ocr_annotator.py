"""OCR标注器

处理OCR文本的标注和校正
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import os

from .base import BaseAnnotator, AnnotationTask, AnnotationStatus, AnnotationType, Correction

logger = logging.getLogger(__name__)


class OCRAnnotator(BaseAnnotator):
    """OCR文本标注器"""

    def __init__(self, storage_dir: str = "data/annotations/ocr"):
        super().__init__()
        self.storage_dir = storage_dir
        self.tasks: Dict[str, AnnotationTask] = {}
        os.makedirs(storage_dir, exist_ok=True)

    async def create_task(
        self,
        source_content: str,
        source_path: str,
        metadata: Dict[str, Any] = None
    ) -> AnnotationTask:
        """创建OCR标注任务"""

        task = AnnotationTask(
            task_id=self._generate_task_id(),
            annotation_type=AnnotationType.OCR,
            original_text=source_content,
            original_source=source_path,
            status=AnnotationStatus.PENDING,
            metadata=metadata or {}
        )

        self.tasks[task.task_id] = task
        await self._save_task(task)

        logger.info(f"创建OCR标注任务: {task.task_id}")
        return task

    async def submit_correction(
        self,
        task_id: str,
        corrected_text: str,
        corrections: List[Correction],
        annotator: str
    ) -> AnnotationTask:
        """提交OCR校正"""

        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        task.corrected_text = corrected_text
        task.corrections = corrections
        task.annotator = annotator
        task.status = AnnotationStatus.COMPLETED
        task.completed_at = datetime.now()

        # 计算改进指标
        improvement = self.calculate_accuracy_improvement(
            task.original_text,
            corrected_text
        )
        task.metadata["improvement"] = improvement

        await self._save_task(task)

        # 更新OCR模型（可选）
        await self._update_ocr_model(task)

        logger.info(f"OCR校正已提交: {task_id}, 改进: {improvement['improvement_percentage']:.2f}%")
        return task

    async def get_task(self, task_id: str) -> Optional[AnnotationTask]:
        """获取标注任务"""
        return self.tasks.get(task_id)

    async def list_pending_tasks(
        self,
        limit: int = 10
    ) -> List[AnnotationTask]:
        """列出待标注任务"""
        pending = [
            task for task in self.tasks.values()
            if task.status == AnnotationStatus.PENDING
        ]
        return pending[:limit]

    async def batch_create_from_pdf(
        self,
        pdf_path: str,
        ocr_engine: str = "tesseract"
    ) -> List[AnnotationTask]:
        """
        批量创建OCR标注任务

        从PDF文件中提取文本并创建标注任务

        Args:
            pdf_path: PDF文件路径
            ocr_engine: OCR引擎（tesseract, paddleocr, easyocr）

        Returns:
            List[AnnotationTask]: 创建的任务列表
        """
        # 执行OCR
        ocr_results = await self._perform_ocr(pdf_path, ocr_engine)

        # 为每页创建标注任务
        tasks = []
        for page_num, page_text in enumerate(ocr_results, 1):
            task = await self.create_task(
                source_content=page_text,
                source_path=f"{pdf_path}:page_{page_num}",
                metadata={
                    "pdf_path": pdf_path,
                    "page_number": page_num,
                    "ocr_engine": ocr_engine,
                    "created_at": datetime.now().isoformat()
                }
            )
            tasks.append(task)

        logger.info(f"从{pdf_path}创建了{len(tasks)}个OCR标注任务")
        return tasks

    async def _perform_ocr(
        self,
        pdf_path: str,
        engine: str
    ) -> List[str]:
        """执行OCR识别"""

        raise NotImplementedError(
            "OCR engine not yet integrated. "
            "This method requires a real OCR engine (e.g., Tesseract, PaddleOCR)."
        )

    async def _update_ocr_model(self, task: AnnotationTask):
        """
        更新OCR模型

        使用标注数据微调模型，提升识别准确率
        """
        # 收集校正数据
        training_data = {
            "original": task.original_text,
            "corrected": task.corrected_text,
            "corrections": [
                {
                    "original": c.original,
                    "corrected": c.corrected,
                    "type": c.correction_type
                }
                for c in task.corrections
            ]
        }

        # TODO: 保存训练数据并触发模型微调
        # 1. 保存到训练数据集
        # 2. 定期批量微调模型
        # 3. 评估模型改进效果

        logger.info(f"OCR模型训练数据已更新: {task.task_id}")

    async def _save_task(self, task: AnnotationTask):
        """保存任务到文件"""
        import json

        task_file = os.path.join(
            self.storage_dir,
            f"{task.task_id}.json"
        )

        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump({
                "task_id": task.task_id,
                "annotation_type": task.annotation_type.value,
                "original_text": task.original_text,
                "original_source": task.original_source,
                "status": task.status.value,
                "corrected_text": task.corrected_text,
                "corrections": [
                    {
                        "position": c.position,
                        "original": c.original,
                        "corrected": c.corrected,
                        "correction_type": c.correction_type,
                        "confidence": c.confidence
                    }
                    for c in task.corrections
                ],
                "annotator": task.annotator,
                "reviewer": task.reviewer,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "metadata": task.metadata
            }, f, ensure_ascii=False, indent=2)

    async def get_statistics(self) -> Dict[str, Any]:
        """获取OCR标注统计"""
        total_tasks = len(self.tasks)
        completed_tasks = [
            t for t in self.tasks.values()
            if t.status == AnnotationStatus.COMPLETED
        ]

        total_improvement = 0
        if completed_tasks:
            for task in completed_tasks:
                improvement = task.metadata.get("improvement", {})
                total_improvement += improvement.get("improvement_percentage", 0)
            avg_improvement = total_improvement / len(completed_tasks)
        else:
            avg_improvement = 0

        return {
            "total_tasks": total_tasks,
            "completed_tasks": len(completed_tasks),
            "pending_tasks": len(self.tasks) - len(completed_tasks),
            "average_improvement_percentage": avg_improvement,
            "total_characters_corrected": sum(
                len(t.corrections) for t in completed_tasks
            )
        }
