"""内容生成API路由

提供多种内容生成功能的API接口
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from backend.core.database import get_db_pool
from backend.services.generation import (
    AudioGenerator,
    CourseGenerator,
    DataAnalyzer,
    PPTGenerator,
    ReportGenerator,
    VideoGenerator,
)
from backend.services.generation.base import GenerationRequest, OutputFormat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generation", tags=["内容生成"])


# ==================== 请求/响应模型 ====================


class ReportRequest(BaseModel):
    """报告生成请求"""

    topic: str
    report_type: str = "academic"  # academic, review, notes, practice, analysis
    sections: Optional[List[str]] = None
    include_references: bool = True
    language: str = "zh"
    output_format: str = "md"  # md, pdf, html, docx


class PPTRequest(BaseModel):
    """PPT生成请求"""

    topic: str
    slide_count: int = 10
    style: str = "academic"  # academic, teaching, presentation
    theme: str = "default"
    language: str = "zh"


class AudioRequest(BaseModel):
    """音频生成请求"""

    text: str
    voice: str = "default"
    speed: float = 1.0
    output_format: str = "mp3"


class VideoRequest(BaseModel):
    """视频生成请求"""

    topic: str
    duration: int = 300  # 秒
    style: str = "educational"
    include_subtitles: bool = True


class CourseRequest(BaseModel):
    """课程生成请求"""

    title: str
    target_audience: str
    duration_weeks: int = 8
    chapters: Optional[List[str]] = None
    include_exercises: bool = True


class AnalysisRequest(BaseModel):
    """数据分析请求"""

    analysis_type: str  # knowledge_graph, learning_progress, content_distribution
    parameters: dict = {}


class GenerationTaskResponse(BaseModel):
    """生成任务响应"""

    task_id: str
    status: str
    message: str


# ==================== API端点 ====================


async def _track_task(
    task_id: str, content_type: str, topic: str, gen_request: GenerationRequest, generator
):
    """Run generation and track status in DB."""
    pool = await get_db_pool()
    try:
        await pool.execute(
            """UPDATE generation_tasks SET status = 'running', started_at = NOW()
               WHERE task_id = $1""",
            task_id,
        )
        result = await generator.generate(gen_request)
        output_path = (
            result.output_path if hasattr(result, "output_path") and result.output_path else None
        )
        await pool.execute(
            """UPDATE generation_tasks SET status = 'completed', progress = 100,
               completed_at = NOW(), output_path = $2 WHERE task_id = $1""",
            task_id,
            output_path,
        )
    except Exception as e:
        logger.error(f"Generation task {task_id} failed: {e}", exc_info=True)
        await pool.execute(
            """UPDATE generation_tasks SET status = 'failed', error_message = $2
               WHERE task_id = $1""",
            task_id,
            str(e),
        )


async def _create_task_record(
    task_id: str, content_type: str, topic: str, parameters: dict, output_format: str
):
    """Insert initial task record into generation_tasks."""
    import json

    pool = await get_db_pool()
    await pool.execute(
        """INSERT INTO generation_tasks (task_id, content_type, topic, parameters, output_format, status)
           VALUES ($1, $2, $3, $4, $5, 'pending')""",
        task_id,
        content_type,
        topic,
        json.dumps(parameters),
        output_format,
    )


@router.post("/report", response_model=GenerationTaskResponse)
async def generate_report(request: ReportRequest, background_tasks: BackgroundTasks):
    """
    生成报告

    支持的报告类型：
    - **academic**: 学术报告
    - **review**: 研究综述
    - **notes**: 课程笔记
    - **practice**: 实践总结
    - **analysis**: 专题分析

    返回任务ID，可以通过 /generation/status/{task_id} 查询进度
    """
    try:
        generator = ReportGenerator()

        gen_request = GenerationRequest(
            task_id=generator._generate_task_id(),
            topic=request.topic,
            content_type="report",
            parameters={
                "report_type": request.report_type,
                "sections": request.sections or [],
                "include_references": request.include_references,
                "language": request.language,
            },
            output_format=OutputFormat(request.output_format),
        )

        background_tasks.add_task(
            _create_task_record,
            gen_request.task_id,
            "report",
            request.topic,
            gen_request.parameters,
            request.output_format,
        )
        background_tasks.add_task(
            _track_task, gen_request.task_id, "report", request.topic, gen_request, generator
        )

        return GenerationTaskResponse(
            task_id=gen_request.task_id,
            status="started",
            message=f"报告生成任务已启动: {request.topic}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ppt", response_model=GenerationTaskResponse)
async def generate_ppt(
    request: PPTRequest, background_tasks: BackgroundTasks
) -> GenerationTaskResponse:
    """
    生成PPT演示文稿

    参数：
    - **topic**: 演示主题
    - **slide_count**: 幻灯片数量（1-100）
    - **style**: 风格（academic, teaching, presentation）
    - **theme**: 主题（default, minimal, colorful）

    返回任务ID
    """
    try:
        generator = PPTGenerator()

        gen_request = GenerationRequest(
            task_id=generator._generate_task_id(),
            topic=request.topic,
            content_type="ppt",
            parameters={
                "slide_count": request.slide_count,
                "style": request.style,
                "theme": request.theme,
                "language": request.language,
            },
            output_format=OutputFormat.JSON,
        )

        background_tasks.add_task(
            _create_task_record,
            gen_request.task_id,
            "ppt",
            request.topic,
            gen_request.parameters,
            "json",
        )
        background_tasks.add_task(
            _track_task, gen_request.task_id, "ppt", request.topic, gen_request, generator
        )

        return GenerationTaskResponse(
            task_id=gen_request.task_id,
            status="started",
            message=f"PPT生成任务已启动: {request.topic}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audio", response_model=GenerationTaskResponse)
async def generate_audio(
    request: AudioRequest, background_tasks: BackgroundTasks
) -> GenerationTaskResponse:
    """
    生成音频（TTS文字转语音）

    将文本转换为语音音频文件

    参数：
    - **text**: 要转换的文本
    - **voice**: 音色（default, female, male）
    - **speed**: 语速（0.5-2.0）
    - **output_format**: 输出格式（mp3, wav, ogg）
    """
    try:
        generator = AudioGenerator()

        gen_request = GenerationRequest(
            task_id=generator._generate_task_id(),
            topic=request.text[:50],  # 使用前50个字符作为标题
            content_type="audio",
            parameters={"text": request.text, "voice": request.voice, "speed": request.speed},
            output_format=OutputFormat(request.output_format),
        )

        background_tasks.add_task(
            _create_task_record,
            gen_request.task_id,
            "audio",
            request.text[:50],
            gen_request.parameters,
            request.output_format,
        )
        background_tasks.add_task(
            _track_task, gen_request.task_id, "audio", request.text[:50], gen_request, generator
        )

        return GenerationTaskResponse(
            task_id=gen_request.task_id, status="started", message="音频生成任务已启动"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/video", response_model=GenerationTaskResponse)
async def generate_video(
    request: VideoRequest, background_tasks: BackgroundTasks
) -> GenerationTaskResponse:
    """
    生成视频

    根据主题生成教学视频

    参数：
    - **topic**: 视频主题
    - **duration**: 视频时长（秒）
    - **style**: 视频风格（educational, documentary, tutorial）
    - **include_subtitles**: 是否包含字幕
    """
    try:
        generator = VideoGenerator()

        gen_request = GenerationRequest(
            task_id=generator._generate_task_id(),
            topic=request.topic,
            content_type="video",
            parameters={
                "duration": request.duration,
                "style": request.style,
                "include_subtitles": request.include_subtitles,
            },
            output_format=OutputFormat.MP4,
        )

        background_tasks.add_task(
            _create_task_record,
            gen_request.task_id,
            "video",
            request.topic,
            gen_request.parameters,
            "mp4",
        )
        background_tasks.add_task(
            _track_task, gen_request.task_id, "video", request.topic, gen_request, generator
        )

        return GenerationTaskResponse(
            task_id=gen_request.task_id,
            status="started",
            message=f"视频生成任务已启动: {request.topic}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/course", response_model=GenerationTaskResponse)
async def generate_course(
    request: CourseRequest, background_tasks: BackgroundTasks
) -> GenerationTaskResponse:
    """
    生成课程

    自动生成完整课程结构，包括：
    - 课程大纲
    - 章节内容
    - 练习题
    - 参考资料

    参数：
    - **title**: 课程标题
    - **target_audience**: 目标受众
    - **duration_weeks**: 课程周数
    - **chapters**: 自定义章节（可选）
    - **include_exercises**: 是否包含练习
    """
    try:
        generator = CourseGenerator()

        gen_request = GenerationRequest(
            task_id=generator._generate_task_id(),
            topic=request.title,
            content_type="course",
            parameters={
                "target_audience": request.target_audience,
                "duration_weeks": request.duration_weeks,
                "chapters": request.chapters,
                "include_exercises": request.include_exercises,
            },
            output_format=OutputFormat.MARKDOWN,
        )

        background_tasks.add_task(
            _create_task_record,
            gen_request.task_id,
            "course",
            request.title,
            gen_request.parameters,
            "markdown",
        )
        background_tasks.add_task(
            _track_task, gen_request.task_id, "course", request.title, gen_request, generator
        )

        return GenerationTaskResponse(
            task_id=gen_request.task_id,
            status="started",
            message=f"课程生成任务已启动: {request.title}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_data(request: AnalysisRequest) -> dict:
    """
    数据分析

    对知识库进行数据分析，返回分析结果

    支持的分析类型：
    - **knowledge_graph**: 知识图谱分析
    - **learning_progress**: 学习进度分析
    - **content_distribution**: 内容分布分析
    - **user_behavior**: 用户行为分析
    """
    try:
        analyzer = DataAnalyzer()

        if request.analysis_type == "knowledge_graph":
            result = await analyzer.analyze_knowledge_graph()
        elif request.analysis_type == "learning_progress":
            result = await analyzer.analyze_learning_progress(request.parameters)
        elif request.analysis_type == "content_distribution":
            result = await analyzer.analyze_content_distribution()
        elif request.analysis_type == "user_behavior":
            result = await analyzer.analyze_user_behavior(request.parameters)
        else:
            raise HTTPException(status_code=400, detail=f"未知的分析类型: {request.analysis_type}")

        return {
            "analysis_type": request.analysis_type,
            "result": result,
            "generated_at": result.get("generated_at"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}")
async def get_generation_status(task_id: str) -> dict:
    """
    查询生成任务状态

    返回任务的当前状态、进度和结果
    """
    pool = await get_db_pool()
    row = await pool.fetchrow(
        """SELECT task_id, content_type, topic, status, progress,
                  output_path, output_format, error_message,
                  created_at, started_at, completed_at
           FROM generation_tasks WHERE task_id = $1""",
        task_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    result = dict(row)
    for key in ("created_at", "started_at", "completed_at"):
        if result[key]:
            result[key] = result[key].isoformat()
    return result


@router.get("/templates")
async def list_templates() -> dict:
    """
    列出可用的模板

    返回各类内容生成器的可用模板
    """
    return {
        "report_templates": [
            {"id": "academic", "name": "学术报告"},
            {"id": "review", "name": "研究综述"},
            {"id": "notes", "name": "课程笔记"},
            {"id": "practice", "name": "实践总结"},
            {"id": "analysis", "name": "专题分析"},
        ],
        "ppt_styles": [
            {"id": "academic", "name": "学术风格"},
            {"id": "teaching", "name": "教学风格"},
            {"id": "presentation", "name": "演示风格"},
        ],
        "audio_voices": [
            {"id": "default", "name": "默认音色"},
            {"id": "female", "name": "女声"},
            {"id": "male", "name": "男声"},
        ],
        "video_styles": [
            {"id": "educational", "name": "教育视频"},
            {"id": "documentary", "name": "纪录片风格"},
            {"id": "tutorial", "name": "教程风格"},
        ],
    }


@router.get("/outputs")
async def list_outputs(content_type: Optional[str] = None, limit: int = 20) -> dict:
    """
    列出生成的内容

    参数：
    - **content_type**: 内容类型（report, ppt, audio, video, course）
    - **limit**: 返回数量限制
    """
    pool = await get_db_pool()

    if content_type:
        rows = await pool.fetch(
            """SELECT task_id, content_type, topic, status, output_path, output_format,
                      created_at, completed_at
               FROM generation_tasks
               WHERE content_type = $1
               ORDER BY created_at DESC LIMIT $2""",
            content_type,
            limit,
        )
        total = await pool.fetchval(
            "SELECT COUNT(*) FROM generation_tasks WHERE content_type = $1", content_type
        )
    else:
        rows = await pool.fetch(
            """SELECT task_id, content_type, topic, status, output_path, output_format,
                      created_at, completed_at
               FROM generation_tasks
               ORDER BY created_at DESC LIMIT $1""",
            limit,
        )
        total = await pool.fetchval("SELECT COUNT(*) FROM generation_tasks")

    outputs = []
    for r in rows:
        item = dict(r)
        for key in ("created_at", "completed_at"):
            if item[key]:
                item[key] = item[key].isoformat()
        outputs.append(item)

    return {"outputs": outputs, "total": total}
