"""内容生成器基类

定义所有生成器的通用接口和行为
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class GenerationStatus(Enum):
    """生成状态"""

    PENDING = "pending"  # 等待生成
    IN_PROGRESS = "in_progress"  # 生成中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class OutputFormat(Enum):
    """输出格式"""

    PDF = "pdf"
    MARKDOWN = "md"
    HTML = "html"
    DOCX = "docx"
    TXT = "txt"
    JSON = "json"
    MP3 = "mp3"
    WAV = "wav"
    MP4 = "mp4"


@dataclass
class GenerationRequest:
    """生成请求"""

    task_id: str
    topic: str
    content_type: str  # report, ppt, audio, video, course, analysis
    parameters: Dict[str, Any]
    output_format: OutputFormat
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class GenerationResult:
    """生成结果"""

    task_id: str
    status: GenerationStatus
    output_path: Optional[str] = None
    output_url: Optional[str] = None
    metadata: Dict[str, Any] = None
    error_message: Optional[str] = None
    created_at: datetime = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class BaseGenerator(ABC):
    """内容生成器基类"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        生成内容

        Args:
            request: 生成请求

        Returns:
            GenerationResult: 生成结果
        """

    @abstractmethod
    def validate_request(self, request: GenerationRequest) -> bool:
        """
        验证请求参数

        Args:
            request: 生成请求

        Returns:
            bool: 是否有效
        """

    async def generate_with_progress(
        self, request: GenerationRequest, progress_callback: Optional[callable] = None
    ) -> GenerationResult:
        """
        带进度回调的生成

        Args:
            request: 生成请求
            progress_callback: 进度回调函数

        Returns:
            GenerationResult: 生成结果
        """
        if progress_callback:
            await progress_callback(0, "开始生成...")

        try:
            # 验证请求
            if not self.validate_request(request):
                return GenerationResult(
                    task_id=request.task_id,
                    status=GenerationStatus.FAILED,
                    error_message="请求参数无效",
                )

            if progress_callback:
                await progress_callback(10, "请求验证通过")

            # 执行生成
            result = await self.generate(request)

            if progress_callback:
                await progress_callback(100, "生成完成")

            return result

        except Exception as e:
            self.logger.error(f"生成失败: {e}", exc_info=True)
            return GenerationResult(
                task_id=request.task_id, status=GenerationStatus.FAILED, error_message=str(e)
            )

    def _generate_task_id(self) -> str:
        """生成任务ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import uuid

        unique_id = str(uuid.uuid4())[:8]
        return f"{self.__class__.__name__}_{timestamp}_{unique_id}"
