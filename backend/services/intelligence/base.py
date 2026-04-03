"""情报系统基础模型和抽象类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class IntelligenceItem:
    """情报条目数据模型"""

    source: str  # 'github', 'npm', 'huggingface'
    source_id: str  # 平台唯一ID
    name: str
    description: str = ""
    url: str = ""
    language: str = ""
    tags: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    relevance_score: int = 0
    relevance_category: str = "monitoring"
    relevance_reason: str = ""


@dataclass
class CollectionResult:
    """采集结果"""

    items: List[IntelligenceItem] = field(default_factory=list)
    total_found: int = 0
    new_count: int = 0
    updated_count: int = 0
    errors: List[str] = field(default_factory=list)
    duration_ms: int = 0


class BaseCollector(ABC):
    """情报采集器抽象基类"""

    source: str = ""

    @abstractmethod
    async def collect(self, keywords: Optional[List[str]] = None) -> CollectionResult:
        """执行采集

        Args:
            keywords: 可选的关键词列表，为空时使用默认关键词

        Returns:
            CollectionResult: 采集结果
        """

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """解析ISO格式日期字符串"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
