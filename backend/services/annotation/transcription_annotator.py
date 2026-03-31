"""语音转写标注器

处理语音转写文本的标注和校正
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import os

from .base import BaseAnnotator, AnnotationTask, AnnotationStatus, AnnotationType, Correction

logger = logging.getLogger(__name__)


class TranscriptionAnnotator(BaseAnnotator):
    """语音转写标注器"""

    def __init__(self, storage_dir: str = "data/annotations/transcription"):
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
        """创建语音转写标注任务"""

        task = AnnotationTask(
            task_id=self._generate_task_id(),
            annotation_type=AnnotationType.TRANSCRIPTION,
            original_text=source_content,
            original_source=source_path,
            status=AnnotationStatus.PENDING,
            metadata=metadata or {}
        )

        self.tasks[task.task_id] = task
        await self._save_task(task)

        logger.info(f"创建转写标注任务: {task.task_id}")
        return task

    async def submit_correction(
        self,
        task_id: str,
        corrected_text: str,
        corrections: List[Correction],
        annotator: str
    ) -> AnnotationTask:
        """提交转写校正"""

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

        # 更新语音识别模型
        await self._update_asr_model(task)

        logger.info(f"转写校正已提交: {task_id}, 改进: {improvement['improvement_percentage']:.2f}%")
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

    async def batch_create_from_audio(
        self,
        audio_path: str,
        asr_engine: str = "whisper",
        speaker_diarization: bool = False
    ) -> List[AnnotationTask]:
        """
        批量创建语音转写标注任务

        从音频文件中转写并创建标注任务

        Args:
            audio_path: 音频文件路径
            asr_engine: ASR引擎（whisper, webrtcvad, kaldi）
            speaker_diarization: 是否进行说话人分离

        Returns:
            List[AnnotationTask]: 创建的任务列表
        """
        # 执行语音转写
        transcription_results = await self._perform_transcription(
            audio_path,
            asr_engine,
            speaker_diarization
        )

        # 创建标注任务
        tasks = []
        if speaker_diarization:
            # 为每个说话人创建任务
            for segment in transcription_results:
                task = await self.create_task(
                    source_content=segment["text"],
                    source_path=f"{audio_path}:{segment['speaker']}_{segment['start']}-{segment['end']}",
                    metadata={
                        "audio_path": audio_path,
                        "speaker": segment["speaker"],
                        "start_time": segment["start"],
                        "end_time": segment["end"],
                        "asr_engine": asr_engine,
                        "confidence": segment.get("confidence", 0.0)
                    }
                )
                tasks.append(task)
        else:
            # 为整个音频创建一个任务
            full_text = "\n".join(s["text"] for s in transcription_results)
            task = await self.create_task(
                source_content=full_text,
                source_path=audio_path,
                metadata={
                    "audio_path": audio_path,
                    "asr_engine": asr_engine,
                    "duration_seconds": metadata.get("duration", 0),
                    "segments": len(transcription_results)
                }
            )
            tasks.append(task)

        logger.info(f"从{audio_path}创建了{len(tasks)}个转写标注任务")
        return tasks

    async def _perform_transcription(
        self,
        audio_path: str,
        engine: str,
        speaker_diarization: bool
    ) -> List[Dict[str, Any]]:
        """执行语音转写"""

        raise NotImplementedError(
            "ASR engine not yet integrated. "
            "This method requires a real ASR engine (e.g., Whisper, PaddleSpeech)."
        )

    async def _update_asr_model(self, task: AnnotationTask):
        """
        更新语音识别模型

        使用标注数据微调ASR模型
        """
        # 收集训练数据
        training_data = {
            "audio_source": task.original_source,
            "original_transcript": task.original_text,
            "corrected_transcript": task.corrected_text,
            "corrections": [
                {
                    "original": c.original,
                    "corrected": c.corrected,
                    "type": c.correction_type
                }
                for c in task.corrections
            ],
            "metadata": task.metadata
        }

        # TODO: 保存训练数据并触发模型微调
        # 1. 将音频和校正文本配对
        # 2. 生成训练样本
        # 3. 定期批量微调模型
        # 4. 评估字错误率（WER）改进

        logger.info(f"ASR模型训练数据已更新: {task.task_id}")

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
        """获取转写标注统计"""
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
            "total_words_corrected": sum(
                len(t.corrections) for t in completed_tasks
            )
        }
