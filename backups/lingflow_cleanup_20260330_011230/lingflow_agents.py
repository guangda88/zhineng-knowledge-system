"""
LingFlow Agents Flow Service

提供自主教材处理的AI agents工作流服务，包括：
- 自主TOC提取和扩展
- 智能文本分割
- 质量评估和优化
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 尝试导入自主处理器
try:
    from backend.lingflow.autonomous_processor import (
        AutonomousTextbookProcessor,
        ProcessingResult,
        ProcessingStage,
        TextBlock,
        TocItem,
    )

    LINGFLOW_AGENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LingFlow agents module not available: {e}")
    LINGFLOW_AGENTS_AVAILABLE = False
    AutonomousTextbookProcessor = None
    ProcessingResult = None
    TocItem = None
    TextBlock = None
    ProcessingStage = None


@dataclass
class AgentTaskConfig:
    """Agent任务配置"""

    target_toc_depth: int = 5
    max_block_chars: int = 300
    enable_toc_expansion: bool = True
    enable_quality_assessment: bool = True
    max_retries: int = 3

    def to_dict(self) -> Dict:
        return {
            "target_toc_depth": self.target_toc_depth,
            "max_block_chars": self.max_block_chars,
            "enable_toc_expansion": self.enable_toc_expansion,
            "enable_quality_assessment": self.enable_quality_assessment,
            "max_retries": self.max_retries,
        }


@dataclass
class AgentTaskResult:
    """Agent任务结果"""

    task_id: str
    textbook_id: str
    textbook_title: str
    status: str  # "pending", "running", "completed", "failed"
    stage: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    toc_items_count: int = 0
    text_blocks_count: int = 0
    quality_score: float = 0.0
    statistics: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "textbook_id": self.textbook_id,
            "textbook_title": self.textbook_title,
            "status": self.status,
            "stage": self.stage,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "toc_items_count": self.toc_items_count,
            "text_blocks_count": self.text_blocks_count,
            "quality_score": self.quality_score,
            "statistics": self.statistics,
            "issues": self.issues,
            "error": self.error,
        }


class LingFlowAgentsService:
    """LingFlow Agents 工作流服务"""

    def __init__(self, api_key: Optional[str] = None):
        """初始化服务

        Args:
            api_key: DeepSeek API密钥，用于TOC扩展
        """
        self.api_key = api_key
        self.tasks: Dict[str, AgentTaskResult] = {}

    def is_available(self) -> bool:
        """检查服务是否可用"""
        return LINGFLOW_AGENTS_AVAILABLE

    async def process_textbook(
        self,
        textbook_path: str,
        config: Optional[AgentTaskConfig] = None,
        textbook_id: Optional[str] = None,
        textbook_title: Optional[str] = None,
    ) -> AgentTaskResult:
        """处理教材

        Args:
            textbook_path: 教材文件路径
            config: 处理配置
            textbook_id: 教材ID
            textbook_title: 教材标题

        Returns:
            任务结果
        """
        if not self.is_available():
            raise RuntimeError("LingFlow agents service is not available")

        if config is None:
            config = AgentTaskConfig()

        # 生成任务ID
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 获取教材标题
        if not textbook_title:
            textbook_title = Path(textbook_path).stem

        # 创建任务结果
        task_result = AgentTaskResult(
            task_id=task_id,
            textbook_id=textbook_id or "",
            textbook_title=textbook_title,
            status="running",
            stage="initialization",
            started_at=datetime.now(),
        )
        self.tasks[task_id] = task_result

        try:
            logger.info(f"开始处理教材: {textbook_title} (任务: {task_id})")

            # 创建处理器
            processor = AutonomousTextbookProcessor(api_key=self.api_key)

            # 配置处理器
            processor.max_block_chars = config.max_block_chars
            processor.target_toc_depth = config.target_toc_depth

            # 读取教材文件
            textbook_file_path = Path(textbook_path)
            if not textbook_file_path.exists():
                raise FileNotFoundError(f"教材文件不存在: {textbook_path}")

            content = self._read_text_file(textbook_file_path)

            # 处理教材
            result: ProcessingResult = await processor.process(
                content=content,
                title=textbook_title,
                enable_toc_expansion=config.enable_toc_expansion,
            )

            # 更新任务结果
            task_result.stage = result.stage.value
            task_result.toc_items_count = len(result.toc_items)
            task_result.text_blocks_count = len(result.text_blocks)
            task_result.quality_score = result.quality_metrics.get("overall", 0.0)
            task_result.statistics = result.statistics
            task_result.issues = result.issues
            task_result.status = "completed"
            task_result.completed_at = datetime.now()

            logger.info(
                f"处理完成: {textbook_title}, TOC: {len(result.toc_items)}, 块: {len(result.text_blocks)}"
            )

        except Exception as e:
            logger.error(f"处理教材失败: {e}", exc_info=True)
            task_result.status = "failed"
            task_result.error = str(e)
            task_result.completed_at = datetime.now()

        return task_result

    async def batch_process_textbooks(
        self, textbooks: List[Dict[str, str]], config: Optional[AgentTaskConfig] = None
    ) -> List[AgentTaskResult]:
        """批量处理教材

        Args:
            textbooks: 教材列表，每项包含 path, id, title
            config: 处理配置

        Returns:
            任务结果列表
        """
        if not self.is_available():
            raise RuntimeError("LingFlow agents service is not available")

        results = []
        for textbook in textbooks:
            try:
                result = await self.process_textbook(
                    textbook_path=textbook.get("path", ""),
                    config=config,
                    textbook_id=textbook.get("id"),
                    textbook_title=textbook.get("title"),
                )
                results.append(result)
            except Exception as e:
                logger.error(f"批量处理失败 {textbook.get('title')}: {e}")
                results.append(
                    AgentTaskResult(
                        task_id=f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        textbook_id=textbook.get("id", ""),
                        textbook_title=textbook.get("title", ""),
                        status="failed",
                        stage="initialization",
                        error=str(e),
                        started_at=datetime.now(),
                        completed_at=datetime.now(),
                    )
                )

        return results

    def get_task_status(self, task_id: str) -> Optional[AgentTaskResult]:
        """获取任务状态"""
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[AgentTaskResult]:
        """获取所有任务"""
        return list(self.tasks.values())

    def _read_text_file(self, file_path: Path) -> str:
        """读取文本文件，自动检测编码"""
        encodings = ["utf-8", "gbk", "gb2312", "gb18030"]

        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue

        # 如果所有编码都失败，使用错误处理
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


# 全局服务实例
_service_instance: Optional[LingFlowAgentsService] = None


def get_agents_service() -> LingFlowAgentsService:
    """获取LingFlow agents服务实例"""
    global _service_instance
    if _service_instance is None:
        from config import config

        _service_instance = LingFlowAgentsService(api_key=config.DEEPSEEK_API_KEY)
    return _service_instance


def reset_agents_service():
    """重置服务实例"""
    global _service_instance
    _service_instance = None


__all__ = [
    "LINGFLOW_AGENTS_AVAILABLE",
    "AgentTaskConfig",
    "AgentTaskResult",
    "LingFlowAgentsService",
    "get_agents_service",
    "reset_agents_service",
]
