"""音频处理API路由

提供音频文件上传、转写、查询、标注等接口。
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audio", tags=["音频处理"])


# ==================== 请求/响应模型 ====================


class AnnotationCreate(BaseModel):
    audio_file_id: int
    segment_id: Optional[int] = None
    annotation_type: str = Field(
        ...,
        description="标注类型: correction, segment_label, highlight, "
        "knowledge_link, teaching_point, timestamp_note",
    )
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    content: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_by: str = "system"


class AnnotationUpdate(BaseModel):
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class ImportRequest(BaseModel):
    audio_path: str = Field(..., description="音频文件绝对路径")
    transcript_text: str = Field(..., description="转写文本内容")
    original_name: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    transcript_format: str = Field(default="auto", description="转录格式: auto/txt/srt")


# ==================== 文件上传 ====================


@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    created_by: str = Form("system"),
):
    """上传音频文件"""
    from backend.services.audio import AudioService

    service = AudioService()

    tag_list = tags.split(",") if tags else None

    try:
        content = await file.read()
        result = await service.upload_file(
            file_content=content,
            original_name=file.filename or "unknown",
            category=category,
            tags=tag_list,
            created_by=created_by,
        )
        return {"status": "ok", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")


# ==================== 转写 ====================


@router.post("/transcribe/{file_id}")
async def start_transcription(file_id: int):
    """提交音频转写任务（听悟云端）"""
    from backend.services.audio import AudioService

    service = AudioService()

    try:
        result = await service.start_transcription(file_id)
        return {"status": "ok", "data": result}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Transcription start failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"转写启动失败: {e}")


@router.post("/transcribe-local/{file_id}")
async def transcribe_local(
    file_id: int,
    language: str = Query(default="zh", description="语言代码: zh/en/ja/ko等"),
    engine: str = Query(
        default="whisper",
        description="ASR 引擎: whisper(本地), cohere(本地, 需HF Token)",
    ),
):
    """本地 ASR 转写（Whisper / Cohere Transcribe）"""
    from backend.services.audio import AudioService

    service = AudioService()

    try:
        result = await service.transcribe_local(file_id, language=language, engine=engine)
        return {"status": "ok", "data": result}
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Local transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"本地转写失败: {e}")


@router.get("/transcribe/{file_id}/status")
async def check_transcription_status(file_id: int):
    """查询转写状态"""
    from backend.services.audio import AudioService

    service = AudioService()

    try:
        result = await service.check_transcription_status(file_id)
        return {"status": "ok", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 文件查询 ====================


@router.get("/files")
async def list_audio_files(
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """列出音频文件"""
    from backend.services.audio import AudioService

    service = AudioService()

    try:
        result = await service.list_files(
            status=status, category=category, limit=limit, offset=offset
        )
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.error(f"List files failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{file_id}")
async def get_audio_file(file_id: int):
    """获取音频文件详情"""
    from backend.services.audio import AudioService

    service = AudioService()

    result = await service.get_file(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="音频文件不存在")
    return {"status": "ok", "data": result}


@router.get("/files/{file_id}/segments")
async def get_audio_segments(file_id: int):
    """获取音频分段列表"""
    from backend.services.audio import AudioService

    service = AudioService()
    segments = await service.get_segments(file_id)
    return {"status": "ok", "data": segments}


@router.delete("/files/{file_id}")
async def delete_audio_file(file_id: int):
    """删除音频文件"""
    from backend.services.audio import AudioService

    service = AudioService()

    deleted = await service.delete_file(file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="音频文件不存在")
    return {"status": "ok", "data": {"deleted": True}}


# ==================== 导入 ====================


@router.post("/import")
async def import_with_transcript(request: ImportRequest):
    """导入带转写文本的音频文件（从听悟导出的数据）"""
    from backend.services.audio import AudioService

    service = AudioService()

    try:
        result = await service.import_with_transcript(
            audio_path=request.audio_path,
            transcript_text=request.transcript_text,
            original_name=request.original_name,
            category=request.category,
            tags=request.tags,
            transcript_format=request.transcript_format,
        )
        return {"status": "ok", "data": result}
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {e}")


# ==================== 标注 ====================


@router.post("/annotations")
async def create_annotation(request: AnnotationCreate):
    """创建标注"""
    from backend.core.database import init_db_pool

    valid_types = {
        "correction",
        "segment_label",
        "highlight",
        "knowledge_link",
        "teaching_point",
        "timestamp_note",
    }
    if request.annotation_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"无效的标注类型: {request.annotation_type}. " f"支持: {', '.join(valid_types)}",
        )

    pool = await init_db_pool()

    file_exists = await pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM audio_files WHERE id = $1)",
        request.audio_file_id,
    )
    if not file_exists:
        raise HTTPException(status_code=404, detail="音频文件不存在")

    row = await pool.fetchrow(
        """
        INSERT INTO audio_annotations
            (audio_file_id, segment_id, annotation_type, start_time, end_time,
             content, metadata, created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id, annotation_type, content, created_at
        """,
        request.audio_file_id,
        request.segment_id,
        request.annotation_type,
        request.start_time,
        request.end_time,
        request.content,
        request.metadata,
        request.created_by,
    )

    await pool.execute(
        """
        INSERT INTO annotation_history
            (annotation_id, action, new_value, changed_by)
        VALUES ($1, 'created', $2, $3)
        """,
        row["id"],
        {"annotation_type": request.annotation_type, "content": request.content},
        request.created_by,
    )

    return {"status": "ok", "data": dict(row)}


@router.get("/annotations/audio/{file_id}")
async def get_annotations(
    file_id: int,
    annotation_type: Optional[str] = None,
    status: Optional[str] = None,
):
    """获取文件的标注列表"""
    from backend.core.database import init_db_pool

    pool = await init_db_pool()

    conditions = ["audio_file_id = $1"]
    params: list = [file_id]
    idx = 2

    if annotation_type:
        conditions.append(f"annotation_type = ${idx}")
        params.append(annotation_type)
        idx += 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1

    where = " AND ".join(conditions)

    rows = await pool.fetch(
        f"""
        SELECT id, audio_file_id, segment_id, annotation_type,
               start_time, end_time, content, metadata, status,
               verified, created_by, created_at, updated_at, version
        FROM audio_annotations
        WHERE {where}
        ORDER BY created_at DESC
        """,
        *params,
    )

    return {"status": "ok", "data": [dict(r) for r in rows]}


@router.put("/annotations/{annotation_id}")
async def update_annotation(annotation_id: int, request: AnnotationUpdate):
    """更新标注"""
    from backend.core.database import init_db_pool

    pool = await init_db_pool()

    old_row = await pool.fetchrow(
        "SELECT content, metadata, status FROM audio_annotations WHERE id = $1",
        annotation_id,
    )
    if not old_row:
        raise HTTPException(status_code=404, detail="标注不存在")

    updates = []
    params: list = []
    idx = 1

    if request.content is not None:
        updates.append(f"content = ${idx}")
        params.append(request.content)
        idx += 1

    if request.metadata is not None:
        updates.append(f"metadata = ${idx}")
        params.append(request.metadata)
        idx += 1

    if request.status is not None:
        updates.append(f"status = ${idx}")
        params.append(request.status)
        idx += 1

    if not updates:
        return {"status": "ok", "data": {"updated": False}}

    updates.append("version = version + 1")
    updates.append("updated_at = NOW()")

    params.append(annotation_id)

    await pool.execute(
        f"""
        UPDATE audio_annotations
        SET {', '.join(updates)}
        WHERE id = ${idx}
        """,
        *params,
    )

    await pool.execute(
        """
        INSERT INTO annotation_history
            (annotation_id, action, old_value, new_value, changed_by)
        VALUES ($1, 'updated', $2, $3, 'system')
        """,
        annotation_id,
        {"content": old_row["content"], "metadata": old_row["metadata"]},
        {"content": request.content, "metadata": request.metadata},
    )

    return {"status": "ok", "data": {"updated": True}}


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(annotation_id: int):
    """软删除标注"""
    from backend.core.database import init_db_pool

    pool = await init_db_pool()

    exists = await pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM audio_annotations WHERE id = $1)",
        annotation_id,
    )
    if not exists:
        raise HTTPException(status_code=404, detail="标注不存在")

    await pool.execute(
        """
        UPDATE audio_annotations
        SET status = 'deleted', updated_at = NOW()
        WHERE id = $1
        """,
        annotation_id,
    )

    await pool.execute(
        """
        INSERT INTO annotation_history
            (annotation_id, action, changed_by)
        VALUES ($1, 'deleted', 'system')
        """,
        annotation_id,
    )

    return {"status": "ok", "data": {"deleted": True}}


# ==================== 导出 ====================


@router.get("/annotations/audio/{file_id}/export")
async def export_annotations(
    file_id: int,
    format: str = Query(default="json", description="导出格式: json/srt/csv"),
):
    """导出标注数据"""
    from backend.core.database import init_db_pool

    pool = await init_db_pool()

    annotations = await pool.fetch(
        """
        SELECT id, annotation_type, start_time, end_time,
               content, metadata, created_by, created_at
        FROM audio_annotations
        WHERE audio_file_id = $1 AND status = 'active'
        ORDER BY start_time NULLS LAST, created_at
        """,
        file_id,
    )

    segments = await pool.fetch(
        """
        SELECT segment_index, start_time, end_time, text, speaker
        FROM audio_segments
        WHERE audio_file_id = $1
        ORDER BY segment_index
        """,
        file_id,
    )

    if format == "srt":
        lines = []
        for i, seg in enumerate(segments, 1):
            start = _format_srt_time(seg["start_time"])
            end = _format_srt_time(seg["end_time"])
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(seg["text"])
            lines.append("")
        return {
            "status": "ok",
            "data": {"format": "srt", "content": "\n".join(lines)},
        }

    elif format == "csv":
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "type", "start_time", "end_time", "content", "created_by"])
        for ann in annotations:
            writer.writerow(
                [
                    ann["id"],
                    ann["annotation_type"],
                    ann["start_time"],
                    ann["end_time"],
                    ann["content"],
                    ann["created_by"],
                ]
            )
        return {
            "status": "ok",
            "data": {"format": "csv", "content": output.getvalue()},
        }

    else:
        return {
            "status": "ok",
            "data": {
                "format": "json",
                "annotations": [dict(a) for a in annotations],
                "segments": [dict(s) for s in segments],
            },
        }


def _format_srt_time(seconds: float) -> str:
    """格式化秒数为SRT时间 (00:01:23,456)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# ==================== 向量化 ====================


@router.post("/vectorize/{file_id}")
async def vectorize_audio_segments(file_id: int):
    """对指定音频文件的分段进行向量化"""
    from backend.services.audio import AudioService

    service = AudioService()

    try:
        result = await service.vectorize_segments(file_id)
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.error(f"Vectorize failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"向量化失败: {e}")


@router.post("/vectorize")
async def vectorize_all_unembedded():
    """向量化所有缺少embedding的音频分段"""
    from backend.services.audio import AudioService

    service = AudioService()

    try:
        result = await service.vectorize_all_unembedded()
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.error(f"Vectorize all failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"向量化失败: {e}")


# ==================== 语义搜索 ====================


@router.get("/search")
async def search_audio(
    q: str = Query(..., description="搜索查询"),
    category: Optional[str] = Query(None),
    top_k: int = Query(default=10, ge=1, le=50),
    threshold: float = Query(default=0.5, ge=0.0, le=1.0),
):
    """语义搜索音频分段"""
    from backend.services.audio import AudioService

    service = AudioService()

    try:
        results = await service.search_segments(
            query=q, category=category, top_k=top_k, threshold=threshold
        )
        return {"status": "ok", "data": results}
    except Exception as e:
        logger.error(f"Audio search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")
