"""
混合检索服务模块
结合向量检索和BM25检索
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

import asyncpg

from .bm25 import BM25Retriever
from .feedback import get_doc_quality_scores
from .gap_tracker import record_search_outcome
from .vector import VectorRetriever

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    混合检索服务

    结合向量语义检索和BM25关键词检索，使用倒数排名融合(RRF)算法合并结果
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
        k: int = 60,
    ):
        """
        初始化混合检索器

        Args:
            db_pool: 数据库连接池
            vector_weight: 向量检索权重
            bm25_weight: BM25检索权重
            k: RRF参数
        """
        self.db_pool = db_pool
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.k = k

        self.vector_retriever: Optional[VectorRetriever] = None
        self.bm25_retriever: Optional[BM25Retriever] = None

    async def initialize(self) -> None:
        """初始化检索器"""
        self.vector_retriever = VectorRetriever(self.db_pool)
        self.bm25_retriever = BM25Retriever(self.db_pool)
        await self.bm25_retriever.initialize()
        logger.info("混合检索器初始化完成")

    async def close(self) -> None:
        """关闭连接"""
        if self.vector_retriever:
            await self.vector_retriever.close()

    def _normalize_scores(self, results: List[Dict[str, Any]]) -> Dict[int, float]:
        """
        归一化得分到0-1范围

        Args:
            results: 检索结果列表

        Returns:
            {文档ID: 归一化得分} 的字典
        """
        if not results:
            return {}

        # 获取得分范围
        scores = [r.get("similarity", r.get("score", 0)) for r in results]
        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return {r["id"]: 1.0 for r in results}

        # 归一化
        normalized = {}
        for r in results:
            score = r.get("similarity", r.get("score", 0))
            normalized[r["id"]] = (score - min_score) / (max_score - min_score)

        return normalized

    def _rrf_merge(
        self, vector_results: List[Dict[str, Any]], bm25_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        使用倒数排名融合(RRF)合并结果

        Args:
            vector_results: 向量检索结果
            bm25_results: BM25检索结果

        Returns:
            合并后的结果
        """
        # 构建排名字典
        vector_ranks = {r["id"]: i for i, r in enumerate(vector_results)}
        bm25_ranks = {r["id"]: i for i, r in enumerate(bm25_results)}

        # 计算RRF得分
        scores: Dict[int, float] = defaultdict(float)
        doc_info: Dict[int, Dict[str, Any]] = {}

        # 向量检索贡献
        for doc_id, rank in vector_ranks.items():
            scores[doc_id] += self.vector_weight / (self.k + rank)
            # 找到文档信息
            for r in vector_results:
                if r["id"] == doc_id:
                    doc_info[doc_id] = r
                    break

        # BM25检索贡献
        for doc_id, rank in bm25_ranks.items():
            scores[doc_id] += self.bm25_weight / (self.k + rank)
            if doc_id not in doc_info:
                for r in bm25_results:
                    if r["id"] == doc_id:
                        doc_info[doc_id] = r
                        break

        # 排序
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # 构建结果
        results = []
        for doc_id, score in sorted_docs:
            info = doc_info.get(doc_id, {})
            results.append(
                {
                    "id": doc_id,
                    "title": info.get("title", ""),
                    "content": info.get("content", ""),
                    "category": info.get("category", ""),
                    "score": score,
                    "method": "hybrid",
                }
            )

        return results

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
        use_vector: bool = True,
        use_bm25: bool = True,
        include_audio: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        混合检索

        Args:
            query: 查询文本
            category: 分类筛选
            top_k: 返回数量
            use_vector: 是否使用向量检索
            use_bm25: 是否使用BM25检索
            include_audio: 是否包含音频分段结果

        Returns:
            检索结果列表
        """
        if not self.vector_retriever or not self.bm25_retriever:
            await self.initialize()

        vector_results = []
        bm25_results = []
        audio_results = []

        # 并行执行检索
        if use_vector:
            vector_results = await self.vector_retriever.search(query, category, top_k * 2)

        if use_bm25:
            bm25_results = await self.bm25_retriever.search(query, category, top_k * 2)

        if include_audio:
            try:
                audio_results = await self._search_audio(query, category, top_k)
            except Exception as e:
                logger.warning(f"音频搜索失败，跳过: {e}")

        # 合并文本结果
        if use_vector and use_bm25:
            results = self._rrf_merge(vector_results, bm25_results)
        elif use_vector:
            results = vector_results
        else:
            results = bm25_results

        # 追加音频结果
        results.extend(audio_results)

        # 反馈质量提升：有正面反馈的文档排序靠前
        try:
            doc_ids = [r["id"] for r in results if isinstance(r.get("id"), int)]
            if doc_ids:
                quality = await get_doc_quality_scores(self.db_pool, doc_ids)
                for r in results:
                    if isinstance(r.get("id"), int) and r["id"] in quality:
                        q = quality[r["id"]]
                        if q["helpful_ratio"] > 0.5:
                            r["score"] = r.get("score", 0) * (1 + 0.1 * q["helpful_ratio"])
                        r["feedback_quality"] = q
        except Exception as fb_err:
            logger.debug(f"反馈质量评估跳过: {fb_err}")

        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(
            f"混合检索: query='{query}', vector={len(vector_results)}, "
            f"bm25={len(bm25_results)}, audio={len(audio_results)}, "
            f"merged={len(results)}"
        )

        try:
            await record_search_outcome(self.db_pool, query, results, category, source="hybrid")
        except Exception as gap_err:
            logger.debug(f"缺口记录跳过: {gap_err}")

        return results[:top_k]

    async def update_embeddings(self) -> Dict[str, int]:
        """更新所有文档的嵌入向量"""
        if not self.vector_retriever:
            await self.initialize()
        return await self.vector_retriever.update_all_embeddings()

    async def _search_audio(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """搜索音频分段"""
        if not self.vector_retriever:
            await self.initialize()

        query_vec = await self.vector_retriever.embed_text(query)

        category_filter = ""
        params: list = [str(query_vec), top_k]
        if category:
            category_filter = "AND af.category = $3"
            params.append(category)

        rows = await self.db_pool.fetch(
            f"""
            SELECT
                s.id, s.audio_file_id, s.segment_index,
                s.start_time, s.end_time, s.text, s.speaker,
                af.original_name, af.category,
                1 - (s.embedding <=> $1::vector) AS similarity
            FROM audio_segments s
            JOIN audio_files af ON af.id = s.audio_file_id
            WHERE s.embedding IS NOT NULL
                AND af.status = 'transcribed'
                {category_filter}
            ORDER BY s.embedding <=> $1::vector
            LIMIT $2
            """,
            *params,
        )

        results = []
        for r in rows:
            results.append(
                {
                    "id": f"audio_{r['id']}",
                    "title": r["original_name"],
                    "content": r["text"],
                    "category": r["category"],
                    "score": float(r["similarity"]),
                    "method": "audio_vector",
                    "source_type": "audio",
                    "audio_file_id": r["audio_file_id"],
                    "segment_index": r["segment_index"],
                    "start_time": r["start_time"],
                    "end_time": r["end_time"],
                    "speaker": r["speaker"],
                }
            )

        return results
