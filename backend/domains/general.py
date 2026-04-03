"""通用领域实现

提供通用知识的查询和搜索，作为其他领域的补充
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseDomain, DomainConfig, DomainType, QueryResult

logger = logging.getLogger(__name__)


class GeneralDomain(BaseDomain):
    """通用领域

    作为默认领域，处理不匹配特定领域的问题
    """

    KEYWORDS = [
        "什么",
        "怎么",
        "如何",
        "为什么",
        "哪",
        "谁",
        "解释",
        "说明",
        "介绍",
        "定义",
        "意思",
        "特点",
        "区别",
        "相同",
        "不同",
        "比较",
    ]

    CATEGORIES = ["百科", "常识", "科普", "综合"]

    def __init__(self, db_pool=None):
        config = DomainConfig(
            name="general",
            domain_type=DomainType.GENERAL,
            enabled=True,
            priority=0,  # 最低优先级，作为兜底
            categories=self.CATEGORIES,
            keywords=self.KEYWORDS,
        )
        super().__init__(config)
        self._db_pool = db_pool

    async def initialize(self) -> None:
        """初始化通用领域"""
        logger.info("初始化通用领域")

    async def shutdown(self) -> None:
        """关闭通用领域"""
        logger.info("关闭通用领域")

    async def query(self, question: str, context: Optional[str] = None, **kwargs) -> QueryResult:
        """执行通用领域查询"""
        self._stats.query_count += 1
        sources = await self.search(question, top_k=5)

        if sources:
            content = "根据知识库找到以下相关内容：\n\n"
            for i, source in enumerate(sources[:3], 1):
                content += f"{i}. **{source.get('title', '')}**\n"
                content += f"   {source.get('content', '')[:150]}...\n\n"
            confidence = 0.6
        else:
            content = f'抱歉，没有找到关于"{question}"的相关内容。建议您：\n'
            content += "1. 尝试使用其他关键词\n"
            content += "2. 指定具体的知识领域（气功/中医/儒家/佛家/道家/武术/哲学/科学/心理学）"
            confidence = 0.1

        return QueryResult(
            content=content,
            sources=sources,
            confidence=confidence,
            domain=self.name,
            metadata={"domain_type": "通用"},
        )

    async def search(self, query: str, top_k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """搜索所有文档"""
        if not self._db_pool:
            return []

        try:
            search_pattern = f"%{query}%"
            rows = await self._db_pool.fetch(
                """SELECT id, title, content, category
                   FROM documents
                   WHERE title ILIKE $1 OR content ILIKE $1
                   LIMIT $2""",
                search_pattern,
                top_k,
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"通用领域搜索失败: {e}")
            return []

    async def get_categories_summary(self) -> Dict[str, int]:
        """获取各分类文档数量"""
        if not self._db_pool:
            return {}

        try:
            rows = await self._db_pool.fetch("""SELECT category, COUNT(*) as count
                   FROM documents
                   GROUP BY category""")
            return {row["category"]: row["count"] for row in rows}
        except Exception as e:
            logger.error(f"获取分类摘要失败: {e}")
            return {}
