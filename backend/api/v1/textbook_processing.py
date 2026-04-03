"""
LingFlow Agents API - AI agents 工作流接口

提供自主教材处理的RESTful API接口：
- 处理单个教材
- 批量处理教材
- 查询任务状态
- 导出处理结果
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.core.dependency_injection import require_admin_api_key
from backend.services.textbook_service import (
    LINGFLOW_AGENTS_AVAILABLE,
    AgentTaskConfig,
    get_agents_service,
)
from backend.utils.path_validation import validate_file_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/textbook-processing", tags=["Textbook Processing"])


class TextbookProcessRequest(BaseModel):
    """教材处理请求"""

    path: str = Field(..., description="教材文件路径")
    id: Optional[str] = Field(None, description="教材ID")
    title: Optional[str] = Field(None, description="教材标题")
    target_toc_depth: int = Field(5, ge=1, le=6, description="目标TOC深度")
    max_block_chars: int = Field(300, ge=100, le=1000, description="最大文本块字符数")
    enable_toc_expansion: bool = Field(True, description="是否启用TOC扩展")
    enable_quality_assessment: bool = Field(True, description="是否启用质量评估")


class BatchProcessRequest(BaseModel):
    """批量处理请求"""

    textbooks: List[Dict[str, str]] = Field(..., description="教材列表，每项包含 path, id, title")
    target_toc_depth: int = Field(5, ge=1, le=6, description="目标TOC深度")
    max_block_chars: int = Field(300, ge=100, le=1000, description="最大文本块字符数")
    enable_toc_expansion: bool = Field(True, description="是否启用TOC扩展")
    enable_quality_assessment: bool = Field(True, description="是否启用质量评估")


class ProcessResponse(BaseModel):
    """处理响应"""

    task_id: str
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None


class TaskStatusResponse(BaseModel):
    """任务状态响应"""

    task_id: str
    textbook_id: str
    textbook_title: str
    status: str
    stage: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    toc_items_count: int = 0
    text_blocks_count: int = 0
    quality_score: float = 0.0
    statistics: Dict[str, Any] = {}
    issues: List[str] = []
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应"""

    available: bool
    message: str
    api_key_configured: bool


@router.get("/health", response_model=HealthResponse)
async def check_health():
    """检查LingFlow agents服务健康状态"""
    from config import config

    if not LINGFLOW_AGENTS_AVAILABLE:
        return HealthResponse(
            available=False,
            message="LingFlow agents module not available",
            api_key_configured=config.DEEPSEEK_API_KEY is not None,
        )

    return HealthResponse(
        available=True,
        message="LingFlow agents service is ready",
        api_key_configured=config.DEEPSEEK_API_KEY is not None,
    )


@router.post("/process", response_model=ProcessResponse)
async def process_textbook(
    request: TextbookProcessRequest,
    background_tasks: BackgroundTasks,
    admin: bool = Depends(require_admin_api_key),
):
    """处理单个教材"""
    if not LINGFLOW_AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="LingFlow agents service is not available")

    try:
        safe_path, _ = validate_file_path(request.path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="Requested file not found")

    config = AgentTaskConfig(
        target_toc_depth=request.target_toc_depth,
        max_block_chars=request.max_block_chars,
        enable_toc_expansion=request.enable_toc_expansion,
        enable_quality_assessment=request.enable_quality_assessment,
    )

    service = get_agents_service()

    async def run_processing():
        try:
            await service.process_textbook(
                textbook_path=request.path,
                config=config,
                textbook_id=request.id,
                textbook_title=request.title,
            )
        except Exception as e:
            logger.error(f"Background processing failed: {e}", exc_info=True)

    background_tasks.add_task(run_processing)

    import uuid

    task_id = f"task_{uuid.uuid4().hex[:12]}"

    return ProcessResponse(
        task_id=task_id,
        status="accepted",
        message=f"Processing task started for: {request.title or Path(request.path).stem}",
        data={"path": request.path, "title": request.title, "config": config.to_dict()},
    )


@router.post("/process/batch", response_model=ProcessResponse)
async def batch_process_textbooks(
    request: BatchProcessRequest,
    background_tasks: BackgroundTasks,
    admin: bool = Depends(require_admin_api_key),
):
    """批量处理教材"""
    if not LINGFLOW_AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="LingFlow agents service is not available")

    safe_paths = []
    for textbook in request.textbooks:
        if "path" not in textbook:
            raise HTTPException(status_code=400, detail="Each textbook must have a 'path' field")
        try:
            safe_path, _ = validate_file_path(textbook["path"])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not safe_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Textbook file not found: {textbook['path']}"
            )
        safe_paths.append(safe_path)

    config = AgentTaskConfig(
        target_toc_depth=request.target_toc_depth,
        max_block_chars=request.max_block_chars,
        enable_toc_expansion=request.enable_toc_expansion,
        enable_quality_assessment=request.enable_quality_assessment,
    )

    service = get_agents_service()

    async def run_batch_processing():
        try:
            await service.batch_process_textbooks(textbooks=request.textbooks, config=config)
        except Exception as e:
            logger.error(f"Background batch processing failed: {e}", exc_info=True)

    background_tasks.add_task(run_batch_processing)

    import uuid

    task_id = f"batch_{uuid.uuid4().hex[:12]}"

    return ProcessResponse(
        task_id=task_id,
        status="accepted",
        message=f"Batch processing started for {len(request.textbooks)} textbooks",
        data={"count": len(request.textbooks), "config": config.to_dict()},
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """查询任务状态"""
    if not LINGFLOW_AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="LingFlow agents service is not available")

    service = get_agents_service()
    task = service.get_task_status(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return TaskStatusResponse(
        task_id=task.task_id,
        textbook_id=task.textbook_id,
        textbook_title=task.textbook_title,
        status=task.status,
        stage=task.stage,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        toc_items_count=task.toc_items_count,
        text_blocks_count=task.text_blocks_count,
        quality_score=task.quality_score,
        statistics=task.statistics,
        issues=task.issues,
        error=task.error,
    )


@router.get("/tasks", response_model=List[TaskStatusResponse])
async def list_all_tasks():
    """列出所有任务"""
    if not LINGFLOW_AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="LingFlow agents service is not available")

    service = get_agents_service()
    tasks = service.get_all_tasks()

    return [
        TaskStatusResponse(
            task_id=task.task_id,
            textbook_id=task.textbook_id,
            textbook_title=task.textbook_title,
            status=task.status,
            stage=task.stage,
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            toc_items_count=task.toc_items_count,
            text_blocks_count=task.text_blocks_count,
            quality_score=task.quality_score,
            statistics=task.statistics,
            issues=task.issues,
            error=task.error,
        )
        for task in tasks
    ]
