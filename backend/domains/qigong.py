"""气功领域实现

提供气功知识的专业查询和搜索
"""

import logging
from typing import List, Dict, Any, Optional

from .base import BaseDomain, DomainConfig, DomainType, QueryResult

logger = logging.getLogger(__name__)


class QigongDomain(BaseDomain):
    """气功领域

    专注于气功、功法、养生等知识
    """

    # 气功领域关键词
    KEYWORDS = [
        "气功", "八段锦", "五禽戏", "太极拳", "六字诀",
        "易筋经", "形意拳", "八卦掌", "站桩", "打坐",
        "吐纳", "导引", "行气", "采气", "发气",
        "丹田", "经络", "气血", "养生", "保健",
        "呼吸", "姿势", "意念", "调身", "调心",
        "功法", "练习", "锻炼", "强身", "健体"
    ]

    # 功法分类
    CATEGORIES = [
        "基础理论", "功法练习", "养生保健", "练习技巧",
        "历史渊源", "注意事项", "功效作用"
    ]

    def __init__(self, db_pool=None):
        """初始化气功领域

        Args:
            db_pool: 数据库连接池
        """
        config = DomainConfig(
            name="qigong",
            domain_type=DomainType.QIGONG,
            enabled=True,
            priority=10,  # 高优先级
            categories=self.CATEGORIES,
            keywords=self.KEYWORDS
        )
        super().__init__(config)
        self._db_pool = db_pool

    async def initialize(self) -> None:
        """初始化气功领域"""
        logger.info("初始化气功领域")
        # 这里可以加载领域特定的资源
        # 如预训练模型、词典等

    async def shutdown(self) -> None:
        """关闭气功领域"""
        logger.info("关闭气功领域")

    async def query(
        self,
        question: str,
        context: Optional[str] = None,
        **kwargs
    ) -> QueryResult:
        """执行气功领域查询

        Args:
            question: 用户问题
            context: 额外上下文
            **kwargs: 其他参数

        Returns:
            查询结果
        """
        self._stats.query_count += 1

        # 这里可以集成专门的气功问答模型
        # 现在使用基础实现
        sources = await self.search(question, top_k=3)

        if sources:
            content = f'关于"{question}"，根据气功知识库找到以下信息：\n\n'
            for i, source in enumerate(sources[:3], 1):
                content += f"{i}. {source.get('title', '')}\n"
                content += f"   {source.get('content', '')[:150]}...\n\n"
            confidence = 0.8
        else:
            content = f'抱歉，在气功知识库中没有找到关于"{question}"的相关内容。'
            confidence = 0.2

        return QueryResult(
            content=content,
            sources=sources,
            confidence=confidence,
            domain=self.name,
            metadata={"domain_type": "气功"}
        )

    async def search(
        self,
        query: str,
        top_k: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """搜索气功文档

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            **kwargs: 其他参数

        Returns:
            搜索结果列表
        """
        if not self._db_pool:
            return []

        try:
            search_pattern = f"%{query}%"
            rows = await self._db_pool.fetch(
                """SELECT id, title, content, category
                   FROM documents
                   WHERE category = '气功'
                   AND (title ILIKE $1 OR content ILIKE $1)
                   LIMIT $2""",
                search_pattern, top_k
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"气功领域搜索失败: {e}")
            return []

    async def get_exercise_by_name(self, exercise_name: str) -> Optional[Dict[str, Any]]:
        """根据功法名称获取详细信息

        Args:
            exercise_name: 功法名称

        Returns:
            功法详情，如果不存在返回None
        """
        if not self._db_pool:
            return None

        try:
            row = await self._db_pool.fetchrow(
                """SELECT id, title, content
                   FROM documents
                   WHERE category = '气功'
                   AND title ILIKE $1
                   LIMIT 1""",
                f"%{exercise_name}%"
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"获取功法详情失败: {e}")
            return None


