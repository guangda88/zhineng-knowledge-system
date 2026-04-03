"""上下文管理服务 - 基于 LingFlow 的上下文管理 API 封装

此服务封装了 LingFlow 的上下文管理功能，提供:
1. Token 估算
2. 消息评分
3. 上下文压缩
4. 会话状态管理
5. 持久化存储
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ===== 数据模型 =====


class MessageRecord(BaseModel):
    """消息记录"""

    role: str = Field(..., description="消息角色: user/assistant/system")
    content: str = Field(..., description="消息内容")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_important: bool = Field(default=False, description="是否为重要消息")


class TaskRecord(BaseModel):
    """任务记录"""

    task: str = Field(..., description="任务描述")
    completed: bool = Field(default=False, description="是否已完成")


class TokenEstimate(BaseModel):
    """Token 估算结果"""

    token_count: int = Field(..., description="Token 数量")
    model: str = Field(default="claude-opus-4", description="使用的模型")
    encoding: str = Field(default="cl100k_base", description="编码方式")
    estimated: bool = Field(default=True, description="是否为估算值")


class MessageScore(BaseModel):
    """消息评分结果"""

    role: str
    content_preview: str
    importance_score: float = Field(..., ge=0, le=1, description="重要性评分 0-1")
    relevance_score: float = Field(..., ge=0, le=1, description="相关性评分 0-1")
    time_score: float = Field(..., ge=0, le=1, description="时间评分 0-1")
    quality_score: float = Field(..., ge=0, le=1, description="质量评分 0-1")
    reasoning: str = Field(default="", description="评分理由")


class ContextCompression(BaseModel):
    """上下文压缩结果"""

    original_tokens: int
    compressed_tokens: int
    reduction_ratio: float
    messages_removed: int
    compression_level: str
    strategy: str
    compressed_messages: List[Dict]


class ContextStatus(BaseModel):
    """上下文状态"""

    session_id: str
    message_count: int
    estimated_tokens: int
    token_limit: int = 180000
    token_usage_ratio: float
    health_status: str  # healthy, warning, critical
    tasks_completed: int
    tasks_pending: int
    needs_compression: bool


class ContextSnapshot(BaseModel):
    """上下文快照"""

    timestamp: str
    session_id: str
    tasks_completed: List[str] = []
    tasks_pending: List[str] = []
    key_decisions: List[str] = []
    important_files: Dict[str, str] = {}
    context_summary: str = ""
    next_steps: List[str] = []


# ===== 服务实现 =====


class ContextService:
    """上下文管理服务

    封装 LingFlow 的上下文管理功能，提供统一的 API 接口。
    """

    # 默认配置
    DEFAULT_TOKEN_LIMIT = 180000
    WARNING_THRESHOLD = 0.85
    COMPRESS_THRESHOLD = 0.90

    def __init__(self, storage_dir: Optional[str] = None, token_limit: int = DEFAULT_TOKEN_LIMIT):
        """初始化上下文服务

        Args:
            storage_dir: 上下文存储目录
            token_limit: Token 限制
        """
        if storage_dir is None:
            # 使用项目的 data/context 目录
            self.storage_dir = Path.cwd() / "data" / "context"
        else:
            self.storage_dir = Path(storage_dir)

        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.token_limit = token_limit
        self.session_id = self._generate_session_id()
        self.message_count = 0
        self.estimated_tokens = 0

        # 上下文快照
        self.snapshot = ContextSnapshot(
            timestamp=datetime.now().isoformat(),
            session_id=self.session_id,
        )

        # 尝试加载 LingFlow 组件
        self._load_lingflow_components()

        # 加载上次上下文
        self._load_last_context()

        logger.info(f"ContextService initialized: session={self.session_id}")

    def _generate_session_id(self) -> str:
        """生成会话 ID"""
        import secrets

        return secrets.token_urlsafe(12)

    def _load_lingflow_components(self):
        """加载 LingFlow 组件（可选）"""
        self.lingflow_available = False
        self.token_estimator = None
        self.message_scorer = None

        try:
            # 尝试导入 LingFlow 的核心组件
            from lingflow_core.core.message_scorer import get_message_scorer
            from lingflow_core.core.token_estimator import get_token_estimator

            self.token_estimator = get_token_estimator("claude-opus-4")
            self.message_scorer = get_message_scorer()
            self.lingflow_available = True

            logger.info("LingFlow components loaded successfully")
        except ImportError as e:
            logger.warning(f"LingFlow components not available: {e}")
            logger.info("Using fallback token estimation")

    def _load_last_context(self):
        """加载上次的上下文"""
        last_file = self.storage_dir / "last_context.json"
        if last_file.exists():
            try:
                with open(last_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.last_context = ContextSnapshot(**data)
                    logger.info(f"Loaded last context: {self.last_context.session_id}")
            except Exception as e:
                logger.warning(f"Failed to load last context: {e}")
                self.last_context = None
        else:
            self.last_context = None

    def estimate_tokens(self, text: str, model: str = "claude-opus-4") -> TokenEstimate:
        """估算 Token 数量

        Args:
            text: 输入文本
            model: 模型名称

        Returns:
            Token 估算结果
        """
        if self.lingflow_available and self.token_estimator:
            try:
                estimate = self.token_estimator.estimate(text)
                return TokenEstimate(
                    token_count=estimate.token_count,
                    model=estimate.model,
                    encoding=estimate.encoding,
                    estimated=estimate.estimated,
                )
            except Exception as e:
                logger.warning(f"LingFlow token estimation failed: {e}")

        # 回退到简单估算 (约 4 字符 = 1 token)
        token_count = len(text) // 4
        return TokenEstimate(
            token_count=token_count, model=model, encoding="fallback", estimated=True
        )

    def score_messages(self, messages: List[Dict]) -> List[MessageScore]:
        """评分消息列表

        Args:
            messages: 消息列表

        Returns:
            评分结果列表
        """
        if self.lingflow_available and self.message_scorer:
            try:
                scores = self.message_scorer.batch_score(messages)
                return [
                    MessageScore(
                        role=msg.get("role", "unknown"),
                        content_preview=msg.get("content", "")[:100] + "...",
                        importance_score=score.importance_score,
                        relevance_score=score.relevance_score,
                        time_score=score.time_score,
                        quality_score=score.quality_score,
                        reasoning=score.reasoning,
                    )
                    for msg, score in zip(messages, scores)
                ]
            except Exception as e:
                logger.warning(f"LingFlow message scoring failed: {e}")

        # 回退到简单评分
        results = []
        for msg in messages:
            content = msg.get("content", "")
            importance = self._simple_importance_score(content)
            results.append(
                MessageScore(
                    role=msg.get("role", "unknown"),
                    content_preview=content[:100] + "...",
                    importance_score=importance,
                    relevance_score=0.5,
                    time_score=0.5,
                    quality_score=0.5,
                    reasoning="Simple fallback scoring",
                )
            )
        return results

    def _simple_importance_score(self, content: str) -> float:
        """简单重要性评分（回退方案）"""
        important_keywords = {
            "fix",
            "bug",
            "implement",
            "create",
            "refactor",
            "critical",
            "important",
            "must",
            "should",
            "error",
            "warning",
            "task",
            "完成",
            "修复",
            "实现",
        }
        content_lower = content.lower()
        matches = sum(1 for kw in important_keywords if kw in content_lower)
        return min(0.3 + matches * 0.1, 1.0)

    def record_message(self, role: str, content: str, is_important: bool = False) -> None:
        """记录一条消息

        Args:
            role: 角色 (user/assistant/system)
            content: 消息内容
            is_important: 是否为重要消息
        """
        self.message_count += 1
        self.estimated_tokens += len(content) // 4

        # 自动检测重要内容
        if not is_important:
            is_important = self._is_important_message(content)

        if is_important:
            self._extract_important_info(content)

        # 检查是否需要压缩
        self._check_and_warn()

    def _is_important_message(self, content: str) -> bool:
        """检测是否为重要消息"""
        return self._simple_importance_score(content) > 0.5

    def _extract_important_info(self, content: str) -> None:
        """从消息中提取重要信息"""
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            # 提取任务
            if line.startswith("◻") or line.startswith("- [ ]"):
                task = line.lstrip("◻- [ ]").strip()
                if task and task not in self.snapshot.tasks_pending:
                    self.snapshot.tasks_pending.append(task)
            elif line.startswith("◼") or line.startswith("- [x]"):
                task = line.lstrip("◼- [x]").strip()
                if task and task not in self.snapshot.tasks_completed:
                    self.snapshot.tasks_completed.append(task)

    def add_task(self, task: str, completed: bool = False) -> None:
        """添加任务"""
        task_list = self.snapshot.tasks_completed if completed else self.snapshot.tasks_pending
        if task not in task_list:
            task_list.append(task)
            self._save_snapshot()

    def complete_task(self, task: str) -> None:
        """标记任务完成"""
        if task in self.snapshot.tasks_pending:
            self.snapshot.tasks_pending.remove(task)
        if task not in self.snapshot.tasks_completed:
            self.snapshot.tasks_completed.append(task)
        self._save_snapshot()

    def add_decision(self, decision: str) -> None:
        """记录关键决策"""
        if decision not in self.snapshot.key_decisions:
            self.snapshot.key_decisions.append(decision)
            self._save_snapshot()

    def _check_and_warn(self) -> None:
        """检查 token 使用情况并警告"""
        ratio = self.estimated_tokens / self.token_limit

        if ratio >= self.COMPRESS_THRESHOLD:
            logger.warning(f"Token usage {ratio:.1%}, recommend compression")
            self.compress_now()
        elif ratio >= self.WARNING_THRESHOLD:
            logger.warning(f"Token usage {ratio:.1%}, approaching limit")

    def _save_snapshot(self) -> None:
        """保存当前快照"""
        self.snapshot.timestamp = datetime.now().isoformat()

        snapshot_file = self.storage_dir / f"{self.session_id}.json"
        last_file = self.storage_dir / "last_context.json"

        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(self.snapshot.model_dump(), f, ensure_ascii=False, indent=2)

        with open(last_file, "w", encoding="utf-8") as f:
            json.dump(self.snapshot.model_dump(), f, ensure_ascii=False, indent=2)

    def compress_now(self) -> str:
        """立即压缩当前上下文

        Returns:
            压缩后的上下文摘要
        """
        summary_parts = [
            "# 上下文摘要",
            "",
            f"**会话 ID**: {self.session_id}",
            f"**时间**: {self.snapshot.timestamp}",
            f"**消息数**: {self.message_count}",
            f"**估计 Token**: {self.estimated_tokens}",
            "",
        ]

        if self.snapshot.tasks_completed:
            summary_parts.extend([f"## 已完成任务 ({len(self.snapshot.tasks_completed)})", ""])
            for task in self.snapshot.tasks_completed:
                summary_parts.append(f"- ✅ {task}")
            summary_parts.append("")

        if self.snapshot.tasks_pending:
            summary_parts.extend([f"## 待完成任务 ({len(self.snapshot.tasks_pending)})", ""])
            for task in self.snapshot.tasks_pending:
                summary_parts.append(f"- ◻ {task}")
            summary_parts.append("")

        if self.snapshot.key_decisions:
            summary_parts.extend(["## 关键决策", ""])
            for decision in self.snapshot.key_decisions:
                summary_parts.append(f"- {decision}")
            summary_parts.append("")

        if self.snapshot.next_steps:
            summary_parts.extend(["## 下一步计划", ""])
            for i, step in enumerate(self.snapshot.next_steps, 1):
                summary_parts.append(f"{i}. {step}")
            summary_parts.append("")

        summary = "\n".join(summary_parts)
        self.snapshot.context_summary = summary
        self._save_snapshot()

        # 保存恢复文件
        recovery_file = self.storage_dir / "RECOVERY_CONTEXT.md"
        recovery_file.write_text(summary, encoding="utf-8")

        logger.info(f"Context compressed to: {recovery_file}")
        return summary

    def get_status(self) -> ContextStatus:
        """获取当前状态"""
        ratio = self.estimated_tokens / self.token_limit

        if ratio < 0.7:
            health = "healthy"
        elif ratio < 0.9:
            health = "warning"
        else:
            health = "critical"

        return ContextStatus(
            session_id=self.session_id,
            message_count=self.message_count,
            estimated_tokens=self.estimated_tokens,
            token_limit=self.token_limit,
            token_usage_ratio=ratio,
            health_status=health,
            tasks_completed=len(self.snapshot.tasks_completed),
            tasks_pending=len(self.snapshot.tasks_pending),
            needs_compression=ratio >= self.COMPRESS_THRESHOLD,
        )

    def get_snapshot(self) -> ContextSnapshot:
        """获取当前快照"""
        return self.snapshot

    def get_recovery_summary(self) -> str:
        """获取恢复摘要"""
        recovery_file = self.storage_dir / "RECOVERY_CONTEXT.md"
        if recovery_file.exists():
            return recovery_file.read_text(encoding="utf-8")
        return self.compress_now()


# ===== 全局单例 =====

_context_service: Optional[ContextService] = None


def get_context_service() -> ContextService:
    """获取上下文服务实例（单例）"""
    global _context_service
    if _context_service is None:
        _context_service = ContextService()
    return _context_service
