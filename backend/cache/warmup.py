"""
缓存预热模块

在应用启动时预热热门查询和数据，提升首次访问性能。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from backend.core.database import init_db_pool
from backend.services.retrieval import HybridRetriever

logger = logging.getLogger(__name__)


class CacheWarmer:
    """缓存预热器"""

    def __init__(self, db_pool, retriever: Optional[HybridRetriever] = None, cache_manager=None):
        """
        初始化缓存预热器

        Args:
            db_pool: 数据库连接池
            retriever: 混合检索器实例（可选）
            cache_manager: 缓存管理器实例（可选）
        """
        self.db_pool = db_pool
        self.retriever = retriever
        self.cache_manager = cache_manager

    async def warmup_popular_queries(self, limit: int = 100, days: int = 7) -> Dict[str, Any]:
        """
        预热热门查询

        Args:
            limit: 预热的查询数量
            days: 统计最近N天的热门查询

        Returns:
            预热结果统计
        """
        stats = {"total_queries": 0, "successful": 0, "failed": 0, "skipped": 0, "queries": []}

        try:
            # 1. 从搜索历史获取热门查询
            popular_queries = await self._get_popular_queries(limit, days)
            stats["total_queries"] = len(popular_queries)

            logger.info(f"开始预热 {len(popular_queries)} 个热门查询")

            # 2. 初始化检索器（如果未提供）
            if not self.retriever:
                self.retriever = HybridRetriever(self.db_pool)
                await self.retriever.initialize()

            # 3. 对每个热门查询执行搜索并缓存
            for idx, row in enumerate(popular_queries):
                query = row["query"]
                frequency = row["frequency"]

                try:
                    # 执行搜索（会自动缓存）
                    results = await self.retriever.search(query, top_k=10)

                    stats["successful"] += 1
                    stats["queries"].append(
                        {
                            "query": query,
                            "frequency": frequency,
                            "results_count": len(results),
                            "status": "success",
                        }
                    )

                    logger.info(
                        f"[{idx + 1}/{len(popular_queries)}] 预热查询: {query} ({len(results)} 个结果)"
                    )

                    # 避免短时间内大量请求
                    await asyncio.sleep(0.1)

                except Exception as e:
                    stats["failed"] += 1
                    stats["queries"].append(
                        {
                            "query": query,
                            "frequency": frequency,
                            "error": str(e),
                            "status": "failed",
                        }
                    )
                    logger.warning(f"预热查询失败 {query}: {e}")

        except Exception as e:
            logger.error(f"预热热门查询失败: {e}", exc_info=True)

        return stats

    async def warmup_categories(self) -> Dict[str, Any]:
        """
        预热分类数据

        Returns:
            预热结果统计
        """
        stats = {"categories": [], "total": 0}

        try:
            # 查询所有分类
            sql = """
                SELECT DISTINCT category
                FROM documents
                WHERE category IS NOT NULL
                ORDER BY category
            """

            rows = await self.db_pool.fetch(sql)

            for row in rows:
                category = row["category"]
                stats["categories"].append(category)
                stats["total"] += 1

                # 触发分类查询（会自动缓存）
                try:
                    await self._query_category(category)
                    logger.info(f"预热分类: {category}")
                except Exception as e:
                    logger.warning(f"预热分类失败 {category}: {e}")

        except Exception as e:
            logger.error(f"预热分类数据失败: {e}", exc_info=True)

        return stats

    async def warmup_stats(self) -> Dict[str, Any]:
        """
        预热统计数据

        Returns:
            预热结果统计
        """
        stats = {"total_documents": 0, "vector_enabled": 0, "categories": 0}

        try:
            # 触发统计查询（会自动缓存）
            total_docs = await self.db_pool.fetchval("SELECT COUNT(*) FROM documents")
            stats["total_documents"] = total_docs

            vector_enabled = await self.db_pool.fetchval(
                "SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL"
            )
            stats["vector_enabled"] = vector_enabled

            categories = await self.db_pool.fetchval(
                "SELECT COUNT(DISTINCT category) FROM documents WHERE category IS NOT NULL"
            )
            stats["categories"] = categories

            logger.info(f"预热统计数据: {stats}")

        except Exception as e:
            logger.error(f"预热统计数据失败: {e}", exc_info=True)

        return stats

    async def warmup_recent_documents(self, limit: int = 50, days: int = 1) -> Dict[str, Any]:
        """
        预热最近访问的文档

        Args:
            limit: 预热的文档数量
            days: 统计最近N天的文档

        Returns:
            预热结果统计
        """
        stats = {"total": 0, "successful": 0, "failed": 0, "documents": []}

        try:
            # 查询最近访问的文档ID
            sql = """
                SELECT DISTINCT doc_id
                FROM search_logs
                WHERE created_at > NOW() - INTERVAL $1 days
                AND doc_id IS NOT NULL
                ORDER BY MAX(created_at) DESC
                LIMIT $2
            """

            rows = await self.db_pool.fetch(sql, days, limit)

            for row in rows:
                doc_id = row["doc_id"]
                stats["total"] += 1

                try:
                    # 触发文档查询（会自动缓存）
                    await self._get_document_by_id(doc_id)

                    stats["successful"] += 1
                    stats["documents"].append(doc_id)

                    logger.debug(f"预热文档: {doc_id}")

                except Exception as e:
                    stats["failed"] += 1
                    logger.warning(f"预热文档失败 {doc_id}: {e}")

        except Exception as e:
            logger.error(f"预热最近文档失败: {e}", exc_info=True)

        return stats

    async def warmup_all(self) -> Dict[str, Any]:
        """
        执行所有预热任务

        Returns:
            所有预热任务的结果统计
        """
        logger.info("开始执行缓存预热...")

        results = {}

        # 1. 预热统计数据
        logger.info("预热统计数据...")
        results["stats"] = await self.warmup_stats()

        # 2. 预热分类数据
        logger.info("预热分类数据...")
        results["categories"] = await self.warmup_categories()

        # 3. 预热热门查询
        logger.info("预热热门查询...")
        results["popular_queries"] = await self.warmup_popular_queries(limit=50)

        # 4. 预热最近文档（可选）
        logger.info("预热最近文档...")
        results["recent_documents"] = await self.warmup_recent_documents(limit=20)

        logger.info("缓存预热完成")

        return results

    async def _get_popular_queries(self, limit: int, days: int) -> List[Dict[str, Any]]:
        """
        获取热门查询列表

        Args:
            limit: 返回数量限制
            days: 统计最近N天

        Returns:
            热门查询列表
        """
        # 尝试从搜索日志表获取
        try:
            sql = """
                SELECT
                    query,
                    COUNT(*) as frequency
                FROM search_logs
                WHERE created_at > NOW() - INTERVAL $1 days
                AND query IS NOT NULL
                GROUP BY query
                ORDER BY frequency DESC
                LIMIT $2
            """

            rows = await self.db_pool.fetch(sql, days, limit)
            return [dict(r) for r in rows]

        except Exception as e:
            logger.warning(f"从搜索日志获取热门查询失败: {e}")

            # 备选方案：使用预设的热门查询
            return self._get_default_popular_queries(limit)

    def _get_default_popular_queries(self, limit: int) -> List[Dict[str, Any]]:
        """
        获取默认热门查询（备选方案）

        Args:
            limit: 返回数量限制

        Returns:
            默认热门查询列表
        """
        # 预设的热门查询
        queries = [
            "气功",
            "中医",
            "儒家",
            "佛家",
            "道家",
            "武术",
            "哲学",
            "科学",
            "心理学",
            "气功的原理",
            "中医的治疗方法",
            "儒家的核心思想",
            "佛家的禅修",
            "道家的养生",
            "武术的基础",
            "哲学的问题",
            "科学的本质",
            "心理学的应用",
        ]

        return [{"query": q, "frequency": 1} for q in queries[:limit]]

    async def _query_category(self, category: str) -> List[Dict[str, Any]]:
        """
        查询特定分类的文档

        Args:
            category: 分类名称

        Returns:
            文档列表
        """
        sql = """
            SELECT id, title, category
            FROM documents
            WHERE category = $1
            LIMIT 10
        """

        return await self.db_pool.fetch(sql, category)

    async def _get_document_by_id(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取文档

        Args:
            doc_id: 文档ID

        Returns:
            文档信息
        """
        sql = """
            SELECT id, title, content, category
            FROM documents
            WHERE id = $1
        """

        return await self.db_pool.fetchrow(sql, doc_id)


async def warmup_cache_on_startup():
    """
    应用启动时执行缓存预热

    作为启动脚本调用
    """
    logger.info("开始应用启动缓存预热...")

    try:
        db_pool = await init_db_pool()
        warmer = CacheWarmer(db_pool)

        results = await warmer.warmup_all()

        # 输出预热结果摘要
        logger.info("缓存预热结果:")
        logger.info(f"  - 统计数据: {results['stats']}")
        logger.info(f"  - 分类数量: {results['categories']['total']}")
        logger.info(
            f"  - 热门查询: {results['popular_queries']['successful']}/{results['popular_queries']['total_queries']} 成功"
        )
        logger.info(
            f"  - 最近文档: {results['recent_documents']['successful']}/{results['recent_documents']['total']} 成功"
        )

        return results

    except Exception as e:
        logger.error(f"应用启动缓存预热失败: {e}", exc_info=True)
        raise
