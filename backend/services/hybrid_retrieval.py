"""
混合检索服务（Hybrid Retrieval Service）

文字处理工程流A-3的核心组件

功能：
1. 向量检索（语义相似度）
2. 全文检索（关键词匹配）
3. 结果融合（RRF算法）
4. 检索缓存
5. 性能优化
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.services.retrieval.vector import VectorRetriever

logger = logging.getLogger(__name__)


class RetrievalMethod(Enum):
    """检索方法"""

    VECTOR = "vector"  # 向量检索
    FULLTEXT = "fulltext"  # 全文检索
    HYBRID = "hybrid"  # 混合检索


@dataclass
class RetrievalResult:
    """检索结果"""

    id: int
    title: str
    content: str
    category: Optional[str]
    score: float
    method: RetrievalMethod
    rank: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "category": self.category,
            "score": self.score,
            "method": self.method.value,
            "rank": self.rank,
            "metadata": self.metadata,
        }


@dataclass
class HybridSearchResult:
    """混合检索结果"""

    results: List[RetrievalResult]
    query: str
    total_time: float
    vector_count: int
    fulltext_count: int
    fusion_method: str = "rrf"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "count": len(self.results),
            "total_time": self.total_time,
            "vector_count": self.vector_count,
            "fulltext_count": self.fulltext_count,
            "fusion_method": self.fusion_method,
            "results": [r.to_dict() for r in self.results[:10]],  # 只返回前10个
        }


class FullTextRetriever:
    """全文检索器"""

    def __init__(self, db_pool):
        """初始化全文检索器

        Args:
            db_pool: 数据库连接池
        """
        self.db_pool = db_pool

    async def search(
        self, query: str, category: Optional[str] = None, top_k: int = 10, threshold: float = 0.1
    ) -> List[RetrievalResult]:
        """全文检索

        Args:
            query: 查询文本
            category: 分类筛选
            top_k: 返回数量
            threshold: 相关性阈值

        Returns:
            检索结果列表
        """
        import time

        start_time = time.time()

        # 使用PostgreSQL的全文搜索
        if category:
            sql = """
                SELECT id, title, content, category,
                       ts_rank(to_tsvector('chinese', content), to_tsquery('chinese', $1)) as rank
                FROM documents
                WHERE category = $2
                  AND to_tsvector('chinese', content) @@ to_tsquery('chinese', $1)
                ORDER BY rank DESC
                LIMIT $3
            """
            params = [query, category, top_k]
        else:
            sql = """
                SELECT id, title, content, category,
                       ts_rank(to_tsvector('chinese', content), to_tsquery('chinese', $1)) as rank
                FROM documents
                WHERE to_tsvector('chinese', content) @@ to_tsquery('chinese', $1)
                ORDER BY rank DESC
                LIMIT $2
            """
            params = [query, top_k]

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)

            results = []
            for i, row in enumerate(rows):
                if row["rank"] >= threshold:
                    results.append(
                        RetrievalResult(
                            id=row["id"],
                            title=row["title"],
                            content=row["content"],
                            category=row["category"],
                            score=float(row["rank"]),
                            method=RetrievalMethod.FULLTEXT,
                            rank=i + 1,
                        )
                    )

            elapsed = time.time() - start_time
            logger.info(f"全文检索: query='{query}', found={len(results)}, time={elapsed:.3f}s")

            return results

        except Exception as e:
            logger.error(f"全文检索失败: {e}")
            # 如果全文搜索失败（可能是中文分词问题），回退到LIKE搜索
            return await self._search_by_like(query, category, top_k)

    async def _search_by_like(
        self, query: str, category: Optional[str], top_k: int
    ) -> List[RetrievalResult]:
        """使用LIKE搜索（后备方案）"""
        if category:
            sql = """
                SELECT id, title, content, category
                FROM documents
                WHERE category = $1 AND (title LIKE $2 OR content LIKE $2)
                LIMIT $3
            """
            params = [category, f"%{query}%", top_k]
        else:
            sql = """
                SELECT id, title, content, category
                FROM documents
                WHERE title LIKE $1 OR content LIKE $1
                LIMIT $2
            """
            params = [f"%{query}%", top_k]

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        results = []
        for i, row in enumerate(rows):
            results.append(
                RetrievalResult(
                    id=row["id"],
                    title=row["title"],
                    content=row["content"],
                    category=row["category"],
                    score=0.5,  # LIKE搜索没有相关性分数，使用默认值
                    method=RetrievalMethod.FULLTEXT,
                    rank=i + 1,
                )
            )

        return results


class ResultFusion:
    """结果融合器"""

    @staticmethod
    def rrf(
        vector_results: List[RetrievalResult], fulltext_results: List[RetrievalResult], k: int = 60
    ) -> List[RetrievalResult]:
        """使用RRF（Reciprocal Rank Fusion）算法融合结果

        Args:
            vector_results: 向量检索结果
            fulltext_results: 全文检索结果
            k: RRF常数（通常为60）

        Returns:
            融合后的结果列表
        """
        # 计算RRF分数
        score_map = {}
        result_map = {}

        # 处理向量检索结果
        for i, result in enumerate(vector_results):
            doc_id = result.id
            rrf_score = 1.0 / (k + i + 1)

            if doc_id not in score_map:
                score_map[doc_id] = 0.0
                result_map[doc_id] = result

            score_map[doc_id] += rrf_score
            result.metadata["vector_rank"] = i + 1

        # 处理全文检索结果
        for i, result in enumerate(fulltext_results):
            doc_id = result.id
            rrf_score = 1.0 / (k + i + 1)

            if doc_id not in score_map:
                score_map[doc_id] = 0.0
                result_map[doc_id] = result

            score_map[doc_id] += rrf_score
            result_map[doc_id].metadata["fulltext_rank"] = i + 1

        # 按RRF分数排序
        sorted_ids = sorted(score_map.items(), key=lambda x: x[1], reverse=True)

        # 创建最终结果列表
        final_results = []
        for rank, (doc_id, score) in enumerate(sorted_ids):
            result = result_map[doc_id]
            result.score = score
            result.rank = rank + 1
            result.method = RetrievalMethod.HYBRID
            result.metadata["rrf_score"] = score
            final_results.append(result)

        logger.info(
            f"RRF融合: vector={len(vector_results)}, fulltext={len(fulltext_results)}, final={len(final_results)}"
        )

        return final_results

    @staticmethod
    def weighted(
        vector_results: List[RetrievalResult],
        fulltext_results: List[RetrievalResult],
        vector_weight: float = 0.6,
        fulltext_weight: float = 0.4,
    ) -> List[RetrievalResult]:
        """加权融合结果

        Args:
            vector_results: 向量检索结果
            fulltext_results: 全文检索结果
            vector_weight: 向量检索权重
            fulltext_weight: 全文检索权重

        Returns:
            融合后的结果列表
        """
        # 归一化分数
        if vector_results:
            max_vector_score = max(r.score for r in vector_results)
            vector_results = [
                RetrievalResult(
                    id=r.id,
                    title=r.title,
                    content=r.content,
                    category=r.category,
                    score=r.score / max_vector_score,
                    method=r.method,
                    metadata=r.metadata,
                )
                for r in vector_results
            ]

        if fulltext_results:
            max_fulltext_score = max(r.score for r in fulltext_results)
            fulltext_results = [
                RetrievalResult(
                    id=r.id,
                    title=r.title,
                    content=r.content,
                    category=r.category,
                    score=r.score / max_fulltext_score,
                    method=r.method,
                    metadata=r.metadata,
                )
                for r in fulltext_results
            ]

        # 计算加权分数
        score_map = {}
        result_map = {}

        for result in vector_results:
            doc_id = result.id
            score_map[doc_id] = result.score * vector_weight
            result_map[doc_id] = result

        for result in fulltext_results:
            doc_id = result.id
            if doc_id in score_map:
                score_map[doc_id] += result.score * fulltext_weight
            else:
                score_map[doc_id] = result.score * fulltext_weight
                result_map[doc_id] = result

        # 按分数排序
        sorted_ids = sorted(score_map.items(), key=lambda x: x[1], reverse=True)

        final_results = []
        for rank, (doc_id, score) in enumerate(sorted_ids):
            result = result_map[doc_id]
            result.score = score
            result.rank = rank + 1
            result.method = RetrievalMethod.HYBRID
            final_results.append(result)

        return final_results


class RetrievalCache:
    """检索缓存"""

    def __init__(self, ttl: int = 3600):
        """初始化缓存

        Args:
            ttl: 缓存过期时间（秒）
        """
        self.cache: Dict[str, Tuple[List[RetrievalResult], float]] = {}
        self.ttl = ttl

    def _generate_key(self, query: str, method: str, **kwargs) -> str:
        """生成缓存键"""
        key_parts = [query, method]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, query: str, method: str, **kwargs) -> Optional[List[RetrievalResult]]:
        """从缓存获取结果"""
        key = self._generate_key(query, method, **kwargs)

        if key in self.cache:
            results, timestamp = self.cache[key]

            # 检查是否过期
            import time

            if time.time() - timestamp < self.ttl:
                logger.debug(f"缓存命中: {key}")
                return results
            else:
                # 过期，删除
                del self.cache[key]

        return None

    def set(self, query: str, method: str, results: List[RetrievalResult], **kwargs):
        """保存到缓存"""
        key = self._generate_key(query, method, **kwargs)

        import time

        self.cache[key] = (results, time.time())
        logger.debug(f"缓存保存: {key}")

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        logger.info("缓存已清空")


class HybridRetrievalService:
    """混合检索服务（主类）"""

    def __init__(
        self, db_pool, enable_cache: bool = True, cache_ttl: int = 3600, default_k: int = 60
    ):
        """初始化服务

        Args:
            db_pool: 数据库连接池
            enable_cache: 是否启用缓存
            cache_ttl: 缓存过期时间
            default_k: RRF常数
        """
        self.db_pool = db_pool
        self.default_k = default_k

        # 初始化检索器
        self.vector_retriever = VectorRetriever(db_pool)
        self.fulltext_retriever = FullTextRetriever(db_pool)
        self.result_fusion = ResultFusion()

        # 初始化缓存
        self.enable_cache = enable_cache
        self.cache = RetrievalCache(ttl=cache_ttl) if enable_cache else None

    async def search(
        self,
        query: str,
        method: RetrievalMethod = RetrievalMethod.HYBRID,
        category: Optional[str] = None,
        top_k: int = 10,
        threshold: float = 0.0,
        use_cache: bool = True,
    ) -> HybridSearchResult:
        """混合检索

        Args:
            query: 查询文本
            method: 检索方法
            category: 分类筛选
            top_k: 返回数量
            threshold: 相似度阈值
            use_cache: 是否使用缓存

        Returns:
            检索结果
        """
        import time

        start_time = time.time()

        # 检查缓存
        if use_cache and self.enable_cache:
            cached = self.cache.get(
                query=query, method=method.value, category=category, top_k=top_k
            )
            if cached is not None:
                return HybridSearchResult(
                    results=cached,
                    query=query,
                    total_time=time.time() - start_time,
                    vector_count=0,
                    fulltext_count=0,
                    fusion_method="cache",
                )

        # 根据方法选择检索方式
        if method == RetrievalMethod.VECTOR:
            results = await self._vector_search(query, category, top_k, threshold)
            vector_count, fulltext_count = len(results), 0
        elif method == RetrievalMethod.FULLTEXT:
            results = await self._fulltext_search(query, category, top_k, threshold)
            vector_count, fulltext_count = 0, len(results)
        else:  # HYBRID
            results, vector_count, fulltext_count = await self._hybrid_search(
                query, category, top_k, threshold
            )

        total_time = time.time() - start_time

        # 保存到缓存
        if use_cache and self.enable_cache:
            self.cache.set(
                query=query, method=method.value, results=results, category=category, top_k=top_k
            )

        return HybridSearchResult(
            results=results,
            query=query,
            total_time=total_time,
            vector_count=vector_count,
            fulltext_count=fulltext_count,
            fusion_method="rrf" if method == RetrievalMethod.HYBRID else method.value,
        )

    async def _vector_search(
        self, query: str, category: Optional[str], top_k: int, threshold: float
    ) -> List[RetrievalResult]:
        """向量检索"""
        raw_results = await self.vector_retriever.search(
            query=query, category=category, top_k=top_k * 2, threshold=threshold  # 获取更多候选
        )

        # 转换为RetrievalResult
        results = []
        for i, r in enumerate(raw_results):
            results.append(
                RetrievalResult(
                    id=r["id"],
                    title=r["title"],
                    content=r["content"],
                    category=r.get("category"),
                    score=r["similarity"],
                    method=RetrievalMethod.VECTOR,
                    rank=i + 1,
                )
            )

        return results[:top_k]

    async def _fulltext_search(
        self, query: str, category: Optional[str], top_k: int, threshold: float
    ) -> List[RetrievalResult]:
        """全文检索"""
        return await self.fulltext_retriever.search(
            query=query, category=category, top_k=top_k, threshold=threshold
        )

    async def _hybrid_search(
        self, query: str, category: Optional[str], top_k: int, threshold: float
    ) -> Tuple[List[RetrievalResult], int, int]:
        """混合检索"""
        # 并行执行向量检索和全文检索
        vector_task = asyncio.create_task(
            self._vector_search(query, category, top_k * 2, threshold)
        )
        fulltext_task = asyncio.create_task(
            self._fulltext_search(query, category, top_k * 2, threshold)
        )

        vector_results, fulltext_results = await asyncio.gather(vector_task, fulltext_task)

        # 使用RRF融合结果
        fused_results = ResultFusion.rrf(
            vector_results=vector_results, fulltext_results=fulltext_results, k=self.default_k
        )

        # 返回融合后的结果
        return fused_results[:top_k], len(vector_results), len(fulltext_results)

    def clear_cache(self):
        """清空缓存"""
        if self.cache:
            self.cache.clear()


__all__ = [
    "RetrievalMethod",
    "RetrievalResult",
    "HybridSearchResult",
    "HybridRetrievalService",
]
