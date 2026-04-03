"""人机交互标注API路由

提供OCR和语音转写的标注功能
"""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from backend.services.annotation import OCRAnnotator, TranscriptionAnnotator
from backend.services.annotation.base import Correction

router = APIRouter(prefix="/annotation", tags=["标注系统"])


# ==================== 请求/响应模型 ====================


class OCRAnnotationRequest(BaseModel):
    """OCR标注请求"""

    text: str = Field(..., description="OCR识别的文本")
    source: str = Field(..., description="文本来源（文件路径）")
    metadata: dict = Field(default_factory=dict, description="额外元数据")


class TranscriptionAnnotationRequest(BaseModel):
    """转写标注请求"""

    text: str = Field(..., description="语音转写的文本")
    audio_source: str = Field(..., description="音频文件路径")
    speaker: Optional[str] = Field(None, description="说话人")
    timestamp_start: Optional[float] = Field(None, description="开始时间（秒）")
    timestamp_end: Optional[float] = Field(None, description="结束时间（秒）")
    confidence: Optional[float] = Field(None, description="识别置信度")


class CorrectionRequest(BaseModel):
    """校正请求"""

    task_id: str = Field(..., description="任务ID")
    corrected_text: str = Field(..., description="校正后的文本")
    corrections: List[dict] = Field(..., description="校正详情列表")
    annotator: str = Field(..., description="标注人")


class BatchOCRRequest(BaseModel):
    """批量OCR标注请求"""

    pdf_path: str = Field(..., description="PDF文件路径")
    ocr_engine: str = Field("tesseract", description="OCR引擎")


class BatchTranscriptionRequest(BaseModel):
    """批量转写标注请求"""

    audio_path: str = Field(..., description="音频文件路径")
    asr_engine: str = Field("whisper", description="ASR引擎")
    speaker_diarization: bool = Field(False, description="是否进行说话人分离")


# ==================== API端点 ====================


@router.post("/ocr/create")
async def create_ocr_annotation_task(request: OCRAnnotationRequest) -> dict:
    """
    创建OCR标注任务

    当OCR识别结果需要人工校正时使用

    参数：
    - **text**: OCR识别的原始文本
    - **source**: 文本来源（如PDF文件路径）
    - **metadata**: 额外元数据（页码、OCR引擎等）

    返回：任务ID和任务详情
    """
    try:
        annotator = OCRAnnotator()

        task = await annotator.create_task(
            source_content=request.text, source_path=request.source, metadata=request.metadata
        )

        return {
            "success": True,
            "task_id": task.task_id,
            "status": task.status.value,
            "message": "OCR标注任务已创建",
            "task": {
                "task_id": task.task_id,
                "original_text": task.original_text[:200],
                "source": task.original_source,
                "created_at": task.created_at.isoformat(),
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ocr/correct")
async def submit_ocr_correction(request: CorrectionRequest) -> dict:
    """
    提交OCR校正

    提交人工校正后的文本和校正详情

    参数：
    - **task_id**: 任务ID
    - **corrected_text**: 校正后的完整文本
    - **corrections**: 校正详情列表
    - **annotator**: 标注人标识

    返回：更新后的任务信息和改进指标
    """
    try:
        annotator = OCRAnnotator()

        # 转换校正数据
        corrections = [
            Correction(
                position=c.get("position", 0),
                original=c.get("original", ""),
                corrected=c.get("corrected", ""),
                correction_type=c.get("correction_type", "substitution"),
                confidence=c.get("confidence", 1.0),
            )
            for c in request.corrections
        ]

        task = await annotator.submit_correction(
            task_id=request.task_id,
            corrected_text=request.corrected_text,
            corrections=corrections,
            annotator=request.annotator,
        )

        improvement = task.metadata.get("improvement", {})

        return {
            "success": True,
            "task_id": task.task_id,
            "status": task.status.value,
            "message": "OCR校正已提交",
            "improvement": improvement,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ocr/batch")
async def batch_create_ocr_tasks(
    request: BatchOCRRequest, background_tasks: BackgroundTasks
) -> dict:
    """
    批量创建OCR标注任务

    从PDF文件自动执行OCR并创建标注任务

    参数：
    - **pdf_path**: PDF文件路径
    - **ocr_engine**: OCR引擎（tesseract, paddleocr, easyocr）

    返回：创建的任务列表
    """
    try:
        annotator = OCRAnnotator()

        async def run_batch_ocr():
            return await annotator.batch_create_from_pdf(
                pdf_path=request.pdf_path, ocr_engine=request.ocr_engine
            )

        background_tasks.add_task(run_batch_ocr)

        return {
            "success": True,
            "message": f"批量OCR任务已启动: {request.pdf_path}",
            "ocr_engine": request.ocr_engine,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ocr/tasks/pending")
async def list_pending_ocr_tasks(limit: int = 10) -> dict:
    """
    列出待标注的OCR任务

    参数：
    - **limit**: 返回数量限制

    返回：待标注任务列表
    """
    try:
        annotator = OCRAnnotator()

        tasks = await annotator.list_pending_tasks(limit=limit)

        return {
            "success": True,
            "total": len(tasks),
            "tasks": [
                {
                    "task_id": t.task_id,
                    "original_text": t.original_text[:200],
                    "source": t.original_source,
                    "created_at": t.created_at.isoformat(),
                }
                for t in tasks
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ocr/task/{task_id}")
async def get_ocr_task(task_id: str) -> dict:
    """
    获取OCR标注任务详情

    返回完整的任务信息，包括原始文本和校正状态
    """
    try:
        annotator = OCRAnnotator()

        task = await annotator.get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        return {
            "success": True,
            "task": {
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
                        "confidence": c.confidence,
                    }
                    for c in task.corrections
                ],
                "annotator": task.annotator,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "metadata": task.metadata,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ocr/stats")
async def get_ocr_statistics() -> dict:
    """
    获取OCR标注统计

    返回OCR标注的整体统计信息
    """
    try:
        annotator = OCRAnnotator()

        stats = await annotator.get_statistics()

        return {"success": True, "statistics": stats}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 语音转写标注 ====================


@router.post("/transcription/create")
async def create_transcription_annotation_task(request: TranscriptionAnnotationRequest) -> dict:
    """
    创建语音转写标注任务

    当语音转写结果需要人工校正时使用

    参数：
    - **text**: 转写的原始文本
    - **audio_source**: 音频文件路径
    - **speaker**: 说话人标识（可选）
    - **timestamp_start**: 开始时间（可选）
    - **timestamp_end**: 结束时间（可选）
    - **confidence**: 识别置信度（可选）

    返回：任务ID和任务详情
    """
    try:
        annotator = TranscriptionAnnotator()

        metadata = {
            "speaker": request.speaker,
            "timestamp_start": request.timestamp_start,
            "timestamp_end": request.timestamp_end,
            "confidence": request.confidence,
        }

        task = await annotator.create_task(
            source_content=request.text, source_path=request.audio_source, metadata=metadata
        )

        return {
            "success": True,
            "task_id": task.task_id,
            "status": task.status.value,
            "message": "转写标注任务已创建",
            "task": {
                "task_id": task.task_id,
                "original_text": task.original_text[:200],
                "source": task.original_source,
                "created_at": task.created_at.isoformat(),
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcription/correct")
async def submit_transcription_correction(request: CorrectionRequest) -> dict:
    """
    提交转写校正

    提交人工校正后的转写文本

    参数：
    - **task_id**: 任务ID
    - **corrected_text**: 校正后的完整文本
    - **corrections**: 校正详情列表
    - **annotator**: 标注人标识

    返回：更新后的任务信息和改进指标
    """
    try:
        annotator = TranscriptionAnnotator()

        # 转换校正数据
        corrections = [
            Correction(
                position=c.get("position", 0),
                original=c.get("original", ""),
                corrected=c.get("corrected", ""),
                correction_type=c.get("correction_type", "substitution"),
                confidence=c.get("confidence", 1.0),
            )
            for c in request.corrections
        ]

        task = await annotator.submit_correction(
            task_id=request.task_id,
            corrected_text=request.corrected_text,
            corrections=corrections,
            annotator=request.annotator,
        )

        improvement = task.metadata.get("improvement", {})

        return {
            "success": True,
            "task_id": task.task_id,
            "status": task.status.value,
            "message": "转写校正已提交",
            "improvement": improvement,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcription/batch")
async def batch_create_transcription_tasks(
    request: BatchTranscriptionRequest, background_tasks: BackgroundTasks
) -> dict:
    """
    批量创建转写标注任务

    从音频文件自动转写并创建标注任务

    参数：
    - **audio_path**: 音频文件路径
    - **asr_engine**: ASR引擎（whisper, webrtcvad, kaldi）
    - **speaker_diarization**: 是否进行说话人分离

    返回：创建的任务列表
    """
    try:
        annotator = TranscriptionAnnotator()

        async def run_batch_transcription():
            return await annotator.batch_create_from_audio(
                audio_path=request.audio_path,
                asr_engine=request.asr_engine,
                speaker_diarization=request.speaker_diarization,
            )

        background_tasks.add_task(run_batch_transcription)

        return {
            "success": True,
            "message": f"批量转写任务已启动: {request.audio_path}",
            "asr_engine": request.asr_engine,
            "speaker_diarization": request.speaker_diarization,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transcription/tasks/pending")
async def list_pending_transcription_tasks(limit: int = 10) -> dict:
    """
    列出待标注的转写任务

    参数：
    - **limit**: 返回数量限制

    返回：待标注任务列表
    """
    try:
        annotator = TranscriptionAnnotator()

        tasks = await annotator.list_pending_tasks(limit=limit)

        return {
            "success": True,
            "total": len(tasks),
            "tasks": [
                {
                    "task_id": t.task_id,
                    "original_text": t.original_text[:200],
                    "source": t.original_source,
                    "created_at": t.created_at.isoformat(),
                }
                for t in tasks
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transcription/task/{task_id}")
async def get_transcription_task(task_id: str) -> dict:
    """
    获取转写标注任务详情

    返回完整的任务信息，包括原始文本和校正状态
    """
    try:
        annotator = TranscriptionAnnotator()

        task = await annotator.get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        return {
            "success": True,
            "task": {
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
                        "confidence": c.confidence,
                    }
                    for c in task.corrections
                ],
                "annotator": task.annotator,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "metadata": task.metadata,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transcription/stats")
async def get_transcription_statistics() -> dict:
    """
    获取转写标注统计

    返回语音转写标注的整体统计信息
    """
    try:
        annotator = TranscriptionAnnotator()

        stats = await annotator.get_statistics()

        return {"success": True, "statistics": stats}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_overall_statistics() -> dict:
    """
    获取标注系统整体统计

    返回OCR和转写标注的综合统计
    """
    try:
        ocr_annotator = OCRAnnotator()
        transcription_annotator = TranscriptionAnnotator()

        ocr_stats, transcription_stats = await asyncio.gather(
            ocr_annotator.get_statistics(), transcription_annotator.get_statistics()
        )

        return {
            "success": True,
            "statistics": {
                "ocr": ocr_stats,
                "transcription": transcription_stats,
                "total_tasks": ocr_stats["total_tasks"] + transcription_stats["total_tasks"],
                "total_completed": ocr_stats["completed_tasks"]
                + transcription_stats["completed_tasks"],
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
