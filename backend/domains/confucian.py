"""儒家领域实现

提供儒家知识的专业查询和搜索
"""

import logging
from typing import List, Dict, Any, Optional

from .base import BaseDomain, DomainConfig, DomainType, QueryResult

logger = logging.getLogger(__name__)


class ConfucianDomain(BaseDomain):
    """儒家领域

    专注于儒家思想、经典、文化等知识
    """

    KEYWORDS = [
        "儒家", "孔子", "孟子", "荀子", "论语",
        "大学", "中庸", "礼记", "易经", "尚书",
        "诗经", "春秋", "孝经", "仁义", "礼智",
        "忠恕", "中庸之道", "修身", "齐家", "治国",
        "平天下", "君子", "小人", "五伦", "三纲五常",
        "四书五经", "儒家思想", "传统文化", "国学"
    ]

    CATEGORIES = [
        "经典著作", "思想理念", "历史人物",
        "文化传承", "现代意义"
    ]

    def __init__(self, db_pool=None):
        config = DomainConfig(
            name="confucian",
            domain_type=DomainType.CONFUCIAN,
            enabled=True,
            priority=8,
            categories=self.CATEGORIES,
            keywords=self.KEYWORDS
        )
        super().__init__(config)
        self._db_pool = db_pool

    async def initialize(self) -> None:
        """初始化儒家领域"""
        logger.info("初始化儒家领域")

    async def shutdown(self) -> None:
        """关闭儒家领域"""
        logger.info("关闭儒家领域")

    async def query(
        self,
        question: str,
        context: Optional[str] = None,
        **kwargs
    ) -> QueryResult:
        """执行儒家领域查询"""
        self._stats.query_count += 1
        sources = await self.search(question, top_k=3)

        if sources:
            content = f'【儒家知识】关于"{question}"：\n\n'
            for i, source in enumerate(sources[:3], 1):
                content += f"{i}. {source.get('title', '')}\n"
                content += f"   {source.get('content', '')[:150]}...\n\n"
            confidence = 0.8
        else:
            content = f'抱歉，在儒家知识库中没有找到关于"{question}"的相关内容。'
            confidence = 0.2

        return QueryResult(
            content=content,
            sources=sources,
            confidence=confidence,
            domain=self.name,
            metadata={"domain_type": "儒家"}
        )

    async def search(
        self,
        query: str,
        top_k: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """搜索儒家文档"""
        if not self._db_pool:
            return []

        try:
            search_pattern = f"%{query}%"
            rows = await self._db_pool.fetch(
                """SELECT id, title, content, category
                   FROM documents
                   WHERE category = '儒家'
                   AND (title ILIKE $1 OR content ILIKE $1)
                   LIMIT $2""",
                search_pattern, top_k
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"儒家领域搜索失败: {e}")
            return []

    async def get_quote_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """根据关键词获取经典语录"""
        if not self._db_pool:
            return []

        try:
            rows = await self._db_pool.fetch(
                """SELECT title, content
                   FROM documents
                   WHERE category = '儒家'
                   AND content ILIKE $1
                   LIMIT 5""",
                f"%{keyword}%"
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取经典语录失败: {e}")
            return []
