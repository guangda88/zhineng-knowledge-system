"""
LingFlow Agents API - AI agents 工作流接口

提供自主教材处理的RESTful API接口：
- 处理单个教材
- 批量处理教材
- 查询任务状态
- 导出处理结果
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

from backend.services.lingflow_agents import (
    LINGFLOW_AGENTS_AVAILABLE,
    get_agents_service,
    AgentTaskConfig,
    AgentTaskResult
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lingflow", tags=["LingFlow Agents"])


# 请求模型
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
    textbooks: List[Dict[str, str]] = Field(
        ...,
        description="教材列表，每项包含 path, id, title"
    )
    target_toc_depth: int = Field(5, ge=1, le=6, description="目标TOC深度")
    max_block_chars: int = Field(300, ge=100, le=1000, description="最大文本块字符数")
    enable_toc_expansion: bool = Field(True, description="是否启用TOC扩展")
    enable_quality_assessment: bool = Field(True, description="是否启用质量评估")


# 响应模型
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


# ============================================
# 端点
# ============================================

@router.get("/health", response_model=HealthResponse)
async def check_health():
    """检查LingFlow agents服务健康状态"""
    from config import config

    if not LINGFLOW_AGENTS_AVAILABLE:
        return HealthResponse(
            available=False,
            message="LingFlow agents module not available",
            api_key_configured=config.DEEPSEEK_API_KEY is not None
        )

    return HealthResponse(
        available=True,
        message="LingFlow agents service is ready",
        api_key_configured=config.DEEPSEEK_API_KEY is not None
    )


@router.post("/process", response_model=ProcessResponse)
async def process_textbook(request: TextbookProcessRequest, background_tasks: BackgroundTasks):
    """处理单个教材

    使用LingFlow agents自主处理教材，包括TOC提取、文本分割和质量评估。
    """
    if not LINGFLOW_AGENTS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="LingFlow agents service is not available"
        )

    # 验证文件路径
    textbook_path = Path(request.path)
    if not textbook_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Textbook file not found: {request.path}"
        )

    # 创建配置
    config = AgentTaskConfig(
        target_toc_depth=request.target_toc_depth,
        max_block_chars=request.max_block_chars,
        enable_toc_expansion=request.enable_toc_expansion,
        enable_quality_assessment=request.enable_quality_assessment
    )

    # 获取服务并处理
    service = get_agents_service()

    # 在后台执行处理
    async def run_processing():
        try:
            await service.process_textbook(
                textbook_path=request.path,
                config=config,
                textbook_id=request.id,
                textbook_title=request.title
            )
        except Exception as e:
            logger.error(f"Background processing failed: {e}", exc_info=True)

    background_tasks.add_task(run_processing)

    # 生成预任务ID（实际任务ID在处理开始时生成）
    from datetime import datetime
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return ProcessResponse(
        task_id=task_id,
        status="accepted",
        message=f"Processing task started for: {request.title or Path(request.path).stem}",
        data={
            "path": request.path,
            "title": request.title,
            "config": config.to_dict()
        }
    )


@router.post("/process/batch", response_model=ProcessResponse)
async def batch_process_textbooks(request: BatchProcessRequest, background_tasks: BackgroundTasks):
    """批量处理教材

    使用LingFlow agents批量处理多个教材。
    """
    if not LINGFLOW_AGENTS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="LingFlow agents service is not available"
        )

    # 验证教材文件
    for textbook in request.textbooks:
        if "path" not in textbook:
            raise HTTPException(
                status_code=400,
                detail="Each textbook must have a 'path' field"
            )
        textbook_path = Path(textbook["path"])
        if not textbook_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Textbook file not found: {textbook['path']}"
            )

    # 创建配置
    config = AgentTaskConfig(
        target_toc_depth=request.target_toc_depth,
        max_block_chars=request.max_block_chars,
        enable_toc_expansion=request.enable_toc_expansion,
        enable_quality_assessment=request.enable_quality_assessment
    )

    # 获取服务
    service = get_agents_service()

    # 在后台执行批量处理
    async def run_batch_processing():
        try:
            await service.batch_process_textbooks(
                textbooks=request.textbooks,
                config=config
            )
        except Exception as e:
            logger.error(f"Background batch processing failed: {e}", exc_info=True)

    background_tasks.add_task(run_batch_processing)

    from datetime import datetime
    task_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return ProcessResponse(
        task_id=task_id,
        status="accepted",
        message=f"Batch processing started for {len(request.textbooks)} textbooks",
        data={
            "count": len(request.textbooks),
            "config": config.to_dict()
        }
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """查询任务状态

    根据任务ID查询处理任务的当前状态和结果。
    """
    if not LINGFLOW_AGENTS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="LingFlow agents service is not available"
        )

    service = get_agents_service()
    task = service.get_task_status(task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task not found: {task_id}"
        )

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
        error=task.error
    )


@router.get("/tasks", response_model=List[TaskStatusResponse])
async def list_all_tasks():
    """列出所有任务

    获取所有已执行或正在执行的任务列表。
    """
    if not LINGFLOW_AGENTS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="LingFlow agents service is not available"
        )

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
            error=task.error
        )
        for task in tasks
    ]
