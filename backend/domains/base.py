"""领域基类模块

定义所有领域必须实现的统一接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DomainType(Enum):
    """领域类型枚举"""

    QIGONG = "气功"
    TCM = "中医"
    CONFUCIAN = "儒家"
    BUDDHIST = "佛家"
    DAOIST = "道家"
    MARTIAL = "武术"
    PHILOSOPHY = "哲学"
    SCIENCE = "科学"
    PSYCHOLOGY = "心理学"
    GENERAL = "通用"


@dataclass
class DomainConfig:
    """领域配置"""

    name: str
    domain_type: DomainType
    enabled: bool = True
    priority: int = 0  # 优先级，数字越大优先级越高
    categories: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)  # 领域关键词


@dataclass
class QueryResult:
    """查询结果"""

    content: str  # 答案内容
    sources: List[Dict[str, Any]] = field(default_factory=list)  # 来源文档
    confidence: float = 0.0  # 置信度
    domain: str = ""  # 来源领域
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "sources": self.sources,
            "confidence": self.confidence,
            "domain": self.domain,
            "metadata": self.metadata,
        }


@dataclass
class DomainStats:
    """领域统计"""

    domain: str
    document_count: int = 0
    query_count: int = 0
    avg_response_time: float = 0.0
    cache_hit_rate: float = 0.0


class BaseDomain(ABC):
    """领域基类

    所有领域必须实现此接口
    """

    def __init__(self, config: DomainConfig):
        """初始化领域

        Args:
            config: 领域配置
        """
        self.config = config
        self._stats = DomainStats(domain=config.name)

    @property
    def name(self) -> str:
        """获取领域名称"""
        return self.config.name

    @property
    def domain_type(self) -> DomainType:
        """获取领域类型"""
        return self.config.domain_type

    @property
    def enabled(self) -> bool:
        """是否启用"""
        return self.config.enabled

    @property
    def priority(self) -> int:
        """获取优先级"""
        return self.config.priority

    @abstractmethod
    async def initialize(self) -> None:
        """初始化领域资源

        在系统启动时调用
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """关闭领域资源

        在系统关闭时调用
        """

    @abstractmethod
    async def query(self, question: str, context: Optional[str] = None, **kwargs) -> QueryResult:
        """执行领域查询

        Args:
            question: 用户问题
            context: 额外上下文
            **kwargs: 其他参数

        Returns:
            查询结果
        """

    @abstractmethod
    async def search(self, query: str, top_k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """搜索领域文档

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            **kwargs: 其他参数

        Returns:
            搜索结果列表
        """

    async def health_check(self) -> Dict[str, Any]:
        """健康检查

        Returns:
            健康状态信息
        """
        return {
            "domain": self.name,
            "status": "healthy" if self.enabled else "disabled",
            "type": self.domain_type.value,
            "priority": self.priority,
        }

    def get_stats(self) -> DomainStats:
        """获取领域统计"""
        return self._stats

    def matches_question(self, question: str) -> float:
        """判断问题是否匹配该领域

        Args:
            question: 用户问题

        Returns:
            匹配分数 (0-1)
        """
        if not self.enabled:
            return 0.0

        question_lower = question.lower()
        score = 0.0

        # 关键词匹配
        for keyword in self.config.keywords:
            if keyword.lower() in question_lower:
                score += 0.3

        # 分类匹配
        for category in self.config.categories:
            if category.lower() in question_lower:
                score += 0.2

        return min(score, 1.0)

    async def batch_query(self, questions: List[str], **kwargs) -> List[QueryResult]:
        """批量查询

        Args:
            questions: 问题列表
            **kwargs: 其他参数

        Returns:
            结果列表
        """
        results = []
        for question in questions:
            result = await self.query(question, **kwargs)
            results.append(result)
        return results
