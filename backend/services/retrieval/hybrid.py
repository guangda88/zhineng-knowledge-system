"""
混合检索服务模块
结合向量检索和BM25检索
"""
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
import asyncpg

from .vector import VectorRetriever
from .bm25 import BM25Retriever

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
        k: int = 60
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
        scores = [r.get('similarity', r.get('score', 0)) for r in results]
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            return {r['id']: 1.0 for r in results}
        
        # 归一化
        normalized = {}
        for r in results:
            score = r.get('similarity', r.get('score', 0))
            normalized[r['id']] = (score - min_score) / (max_score - min_score)
        
        return normalized
    
    def _rrf_merge(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]]
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
        vector_ranks = {r['id']: i for i, r in enumerate(vector_results)}
        bm25_ranks = {r['id']: i for i, r in enumerate(bm25_results)}
        
        # 计算RRF得分
        scores: Dict[int, float] = defaultdict(float)
        doc_info: Dict[int, Dict[str, Any]] = {}
        
        # 向量检索贡献
        for doc_id, rank in vector_ranks.items():
            scores[doc_id] += self.vector_weight / (self.k + rank)
            # 找到文档信息
            for r in vector_results:
                if r['id'] == doc_id:
                    doc_info[doc_id] = r
                    break
        
        # BM25检索贡献
        for doc_id, rank in bm25_ranks.items():
            scores[doc_id] += self.bm25_weight / (self.k + rank)
            if doc_id not in doc_info:
                for r in bm25_results:
                    if r['id'] == doc_id:
                        doc_info[doc_id] = r
                        break
        
        # 排序
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # 构建结果
        results = []
        for doc_id, score in sorted_docs:
            info = doc_info.get(doc_id, {})
            results.append({
                'id': doc_id,
                'title': info.get('title', ''),
                'content': info.get('content', ''),
                'category': info.get('category', ''),
                'score': score,
                'method': 'hybrid'
            })
        
        return results
    
    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
        use_vector: bool = True,
        use_bm25: bool = True
    ) -> List[Dict[str, Any]]:
        """
        混合检索
        
        Args:
            query: 查询文本
            category: 分类筛选
            top_k: 返回数量
            use_vector: 是否使用向量检索
            use_bm25: 是否使用BM25检索
        
        Returns:
            检索结果列表
        """
        if not self.vector_retriever or not self.bm25_retriever:
            await self.initialize()
        
        vector_results = []
        bm25_results = []
        
        # 并行执行两种检索
        if use_vector:
            vector_results = await self.vector_retriever.search(
                query, category, top_k * 2
            )
        
        if use_bm25:
            bm25_results = await self.bm25_retriever.search(
                query, category, top_k * 2
            )
        
        # 合并结果
        if use_vector and use_bm25:
            results = self._rrf_merge(vector_results, bm25_results)
        elif use_vector:
            results = vector_results
        else:
            results = bm25_results
        
        logger.info(f"混合检索: query='{query}', vector={len(vector_results)}, bm25={len(bm25_results)}, merged={len(results)}")
        
        return results[:top_k]
    
    async def update_embeddings(self) -> Dict[str, int]:
        """更新所有文档的嵌入向量"""
        if not self.vector_retriever:
            await self.initialize()
        return await self.vector_retriever.update_all_embeddings()
