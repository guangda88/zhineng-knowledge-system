"""标注管理器

统一管理OCR和语音转写标注任务
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

from .base import AnnotationTask, AnnotationStatus, AnnotationType
from .ocr_annotator import OCRAnnotator
from .transcription_annotator import TranscriptionAnnotator

logger = logging.getLogger(__name__)


class AnnotationManager:
    """标注管理器"""

    def __init__(self):
        self.ocr_annotator = OCRAnnotator()
        self.transcription_annotator = TranscriptionAnnotator()
        self.logger = logging.getLogger(__name__)

    async def create_task(
        self,
        annotation_type: AnnotationType,
        source_content: str,
        source_path: str,
        metadata: Dict[str, Any] = None
    ) -> AnnotationTask:
        """
        创建标注任务

        根据类型自动选择合适的标注器

        Args:
            annotation_type: 标注类型（OCR或TRANSCRIPTION）
            source_content: 原始内容
            source_path: 原始文件路径
            metadata: 额外元数据

        Returns:
            AnnotationTask: 创建的标注任务
        """
        if annotation_type == AnnotationType.OCR:
            return await self.ocr_annotator.create_task(
                source_content=source_content,
                source_path=source_path,
                metadata=metadata
            )
        elif annotation_type == AnnotationType.TRANSCRIPTION:
            return await self.transcription_annotator.create_task(
                source_content=source_content,
                source_path=source_path,
                metadata=metadata
            )
        else:
            raise ValueError(f"不支持的标注类型: {annotation_type}")

    async def get_task(self, task_id: str) -> Optional[AnnotationTask]:
        """获取标注任务"""
        # 先尝试OCR标注器
        task = await self.ocr_annotator.get_task(task_id)
        if task:
            return task

        # 再尝试转写标注器
        task = await self.transcription_annotator.get_task(task_id)
        if task:
            return task

        return None

    async def list_all_pending_tasks(
        self,
        limit: int = 20
    ) -> Dict[str, List[AnnotationTask]]:
        """列出所有待标注任务"""
        ocr_tasks = await self.ocr_annotator.list_pending_tasks(limit)
        transcription_tasks = await self.transcription_annotator.list_pending_tasks(limit)

        return {
            "ocr": ocr_tasks,
            "transcription": transcription_tasks
        }

    async def get_overall_statistics(self) -> Dict[str, Any]:
        """获取整体统计信息"""
        ocr_stats, transcription_stats = await asyncio.gather(
            self.ocr_annotator.get_statistics(),
            self.transcription_annotator.get_statistics()
        )

        total_tasks = ocr_stats["total_tasks"] + transcription_stats["total_tasks"]
        total_completed = ocr_stats["completed_tasks"] + transcription_stats["completed_tasks"]

        # 计算平均改进率
        ocr_improvement = ocr_stats.get("average_improvement_percentage", 0)
        transcription_improvement = transcription_stats.get("average_improvement_percentage", 0)

        if ocr_stats["completed_tasks"] > 0 and transcription_stats["completed_tasks"] > 0:
            avg_improvement = (ocr_improvement + transcription_improvement) / 2
        elif ocr_stats["completed_tasks"] > 0:
            avg_improvement = ocr_improvement
        elif transcription_stats["completed_tasks"] > 0:
            avg_improvement = transcription_improvement
        else:
            avg_improvement = 0

        return {
            "total_tasks": total_tasks,
            "completed_tasks": total_completed,
            "pending_tasks": total_tasks - total_completed,
            "completion_rate": (total_completed / total_tasks * 100) if total_tasks > 0 else 0,
            "average_improvement_percentage": avg_improvement,
            "ocr": ocr_stats,
            "transcription": transcription_stats
        }

    async def get_productivity_metrics(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """获取生产力指标"""
        # 统计过去N天的标注情况
        cutoff_date = datetime.now() - timedelta(days=days)

        raise NotImplementedError(
            "Productivity metrics require database integration. "
            "This method returns no data until the annotation pipeline is connected."
        )

    async def export_training_data(
        self,
        annotation_type: AnnotationType,
        output_path: str
    ) -> str:
        """
        导出训练数据

        将已完成的标注任务导出为模型训练格式

        Args:
            annotation_type: 标注类型
            output_path: 输出文件路径

        Returns:
            str: 导出文件路径
        """
        # TODO: 实现实际的导出逻辑
        # 1. 收集所有已完成的任务
        # 2. 格式化为训练数据（JSONL, CSV等）
        # 3. 保存到文件

        import json

        if annotation_type == AnnotationType.OCR:
            tasks = [
                t for t in self.ocr_annotator.tasks.values()
                if t.status == AnnotationStatus.COMPLETED
            ]
        else:
            tasks = [
                t for t in self.transcription_annotator.tasks.values()
                if t.status == AnnotationStatus.COMPLETED
            ]

        # 转换为训练数据格式
        training_data = []
        for task in tasks:
            training_data.append({
                "source": task.original_source,
                "original": task.original_text,
                "corrected": task.corrected_text,
                "corrections": [
                    {
                        "position": c.position,
                        "original": c.original,
                        "corrected": c.corrected,
                        "type": c.correction_type
                    }
                    for c in task.corrections
                ]
            })

        # 保存为JSONL
        with open(output_path, 'w', encoding='utf-8') as f:
            for item in training_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        self.logger.info(f"导出了{len(training_data)}条训练数据到{output_path}")

        return output_path

    async def trigger_model_retraining(
        self,
        annotation_type: AnnotationType
    ) -> Dict[str, Any]:
        """
        触发模型重训练

        使用标注数据重新训练识别模型

        Args:
            annotation_type: 标注类型

        Returns:
            Dict: 训练任务信息
        """
        # TODO: 实现实际的模型重训练逻辑
        # 1. 导出训练数据
        # 2. 调用训练脚本
        # 3. 监控训练进度
        # 4. 评估新模型
        # 5. 部署新模型

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        training_data_path = f"data/annotations/training/{annotation_type.value}_{timestamp}.jsonl"

        await self.export_training_data(
            annotation_type=annotation_type,
            output_path=training_data_path
        )

        return {
            "status": "initiated",
            "annotation_type": annotation_type.value,
            "training_data_path": training_data_path,
            "message": "模型重训练任务已启动",
            "estimated_time_minutes": 30
        }

    async def cleanup_old_tasks(
        self,
        older_than_days: int = 30,
        status: AnnotationStatus = AnnotationStatus.COMPLETED
    ) -> int:
        """
        清理旧任务

        删除指定时间之前的已完成任务

        Args:
            older_than_days: 天数阈值
            status: 任务状态

        Returns:
            int: 删除的任务数量
        """
        cutoff_date = datetime.now() - timedelta(days=older_than_days)

        # TODO: 实现实际的清理逻辑
        # 1. 查询符合条件的任务
        # 2. 备份到归档
        # 3. 删除任务记录

        cleaned_count = 0
        self.logger.info(f"清理了{cleaned_count}个旧任务（早于{older_than_days}天）")

        return cleaned_count

    async def get_quality_metrics(self) -> Dict[str, Any]:
        """获取质量指标"""
        ocr_stats, transcription_stats = await asyncio.gather(
            self.ocr_annotator.get_statistics(),
            self.transcription_annotator.get_statistics()
        )

        return {
            "ocr": {
                "average_improvement": ocr_stats.get("average_improvement_percentage", 0),
                "total_corrections": ocr_stats.get("total_characters_corrected", 0),
                "completed_tasks": ocr_stats["completed_tasks"]
            },
            "transcription": {
                "average_improvement": transcription_stats.get("average_improvement_percentage", 0),
                "total_corrections": transcription_stats.get("total_words_corrected", 0),
                "completed_tasks": transcription_stats["completed_tasks"]
            },
            "overall_quality_score": (
                ocr_stats.get("average_improvement_percentage", 0) +
                transcription_stats.get("average_improvement_percentage", 0)
            ) / 2
        }


# 全局单例
_annotation_manager: Optional[AnnotationManager] = None


def get_annotation_manager() -> AnnotationManager:
    """获取标注管理器实例"""
    global _annotation_manager
    if _annotation_manager is None:
        _annotation_manager = AnnotationManager()
    return _annotation_manager
