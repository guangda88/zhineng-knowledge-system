"""
混合检索服务模块
结合向量检索和BM25检索，支持查询扩展、多源融合
"""

import asyncio
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import asyncpg

from .bm25 import BM25Retriever
from .feedback import get_doc_quality_scores
from .gap_tracker import record_search_outcome
from .highlighter import ResultHighlighter
from .query_expansion import expand_query, expand_query_simple
from .reranker import create_reranker
from .vector import VectorRetriever
from ..knowledge_graph.concept_map import get_related_domains, get_concept_info

if TYPE_CHECKING:
    from .reranker import Reranker

logger = logging.getLogger(__name__)


def _build_citation(info: Dict[str, Any], source_table: str) -> str:
    """构建来源引用字符串，便于用户追溯知识出处"""
    title = info.get("title", "")
    category = info.get("category", "")
    parts = []
    if source_table == "documents":
        if title:
            parts.append(title)
        if category:
            parts.append(f"[{category}]")
        return " - ".join(parts) if parts else ""
    elif source_table == "guoxue_content":
        if title:
            parts.append(title)
        parts.append("国学经典")
        return " - ".join(parts)
    elif source_table == "textbook_blocks_v2":
        if title:
            parts.append(title)
        parts.append("智能气功教材")
        return " - ".join(parts)
    elif source_table == "doc_chunks":
        if title:
            parts.append(title)
        if category:
            parts.append(f"[{category}]")
        return " - ".join(parts) if parts else ""
    return ""


async def _empty_coro():
    """空协程，用于跳过检索"""
    return []


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
        use_reranker: bool = True,
        use_highlighter: bool = True,
        search_timeout: float = 20.0,
    ):
        """
        初始化混合检索器

        Args:
            db_pool: 数据库连接池
            vector_weight: 向量检索权重
            bm25_weight: BM25检索权重
            k: RRF参数
            use_reranker: 是否启用 cross-encoder 精排
            use_highlighter: 是否启用结果片段高亮
            search_timeout: 并行检索超时秒数（防止大数据集卡死）
        """
        self.db_pool = db_pool
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.k = k
        self.use_reranker = use_reranker
        self.use_highlighter = use_highlighter
        self.search_timeout = search_timeout

        self.vector_retriever: Optional[VectorRetriever] = None
        self.bm25_retriever: Optional[BM25Retriever] = None
        self.reranker: "Optional[Reranker]" = None
        self.highlighter: Optional[ResultHighlighter] = None

    async def initialize(self) -> None:
        """初始化检索器"""
        self.vector_retriever = VectorRetriever(self.db_pool)
        self.bm25_retriever = BM25Retriever(self.db_pool)
        await self.bm25_retriever.initialize()
        if self.use_reranker:
            self.reranker = create_reranker()
            if self.reranker:
                try:
                    import torch
                    if not torch.cuda.is_available():
                        logger.info("CPU环境检测到，禁用reranker以降低延迟")
                        self.reranker = None
                except ImportError:
                    logger.info("无torch，禁用reranker")
                    self.reranker = None

        if self.use_highlighter:
            self.highlighter = ResultHighlighter(max_length=200, window_size=50)

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
            source_table = info.get("source_table", "")
            citation = _build_citation(info, source_table)
            result = {
                "id": doc_id,
                "title": info.get("title", ""),
                "content": info.get("content", ""),
                "category": info.get("category", ""),
                "score": score,
                "method": "hybrid",
                "source_table": source_table,
            }
            if citation:
                result["source_citation"] = citation
            if info.get("similarity") is not None:
                result["similarity"] = info["similarity"]
            if info.get("doc_id"):
                result["doc_id"] = info["doc_id"]
            if info.get("node_id"):
                result["node_id"] = info["node_id"]
            results.append(result)

        return results

    def _ensure_table_diversity(
        self, results: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        """确保最终结果中每个 source_table 至少占据 min_per_table 个名额。

        策略：按 relevance 排序依次填充，但为每个 table 保留最低保障位。
        """
        if not results or top_k <= 0:
            return results

        tables = set(r.get("source_table", "") for r in results)
        tables.discard("")
        n_tables = len(tables)
        if n_tables <= 1:
            return results

        min_per_table = max(top_k // n_tables, 2)
        quota = {t: min_per_table for t in tables}
        total_quota = min_per_table * n_tables
        if total_quota > top_k:
            scale = top_k / total_quota
            quota = {t: max(1, int(v * scale)) for t, v in quota.items()}

        selected: List[Dict[str, Any]] = []
        table_count: Dict[str, int] = {t: 0 for t in tables}
        remaining: List[Dict[str, Any]] = []

        for r in results:
            tbl = r.get("source_table", "")
            if tbl in quota and table_count.get(tbl, 0) < quota[tbl]:
                selected.append(r)
                table_count[tbl] = table_count.get(tbl, 0) + 1
            elif tbl not in quota:
                selected.append(r)
            else:
                remaining.append(r)

        fill = top_k - len(selected)
        if fill > 0 and remaining:
            selected.extend(remaining[:fill])

        return selected

    def _ensure_category_diversity(
        self, results: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        """确保最终结果中不会由单一 category 垄断。

        策略：每个 category 最多占 top_k 的 60%，为其他域保留名额。
        按原始排序依次填充，超出配额的放入 remaining 最后补位。
        """
        if not results or top_k <= 0:
            return results

        categories = set(r.get("category", "") for r in results)
        categories.discard("")
        n_cats = len(categories)
        if n_cats <= 1:
            return results

        max_per_cat = max(top_k * 6 // 10, 2)  # 60% cap per category
        cat_count: Dict[str, int] = {}
        selected: List[Dict[str, Any]] = []
        remaining: List[Dict[str, Any]] = []

        for r in results:
            cat = r.get("category", "")
            if cat and cat_count.get(cat, 0) < max_per_cat:
                selected.append(r)
                cat_count[cat] = cat_count.get(cat, 0) + 1
            else:
                remaining.append(r)

        fill = top_k - len(selected)
        if fill > 0 and remaining:
            selected.extend(remaining[:fill])

        return selected

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
        use_vector: bool = True,
        use_bm25: bool = True,
        include_audio: bool = True,
        use_query_expansion: bool = True,
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
            use_query_expansion: 是否使用查询扩展

        Returns:
            检索结果列表
        """
        if not self.vector_retriever or not self.bm25_retriever:
            await self.initialize()

        concept_info = get_concept_info(query)
        related_domains = get_related_domains(query)
        if category is None and related_domains:
            category = None
            logger.info(f"跨域概念检测: concepts={[c['concept'] for c in concept_info]}, domains={related_domains}")

        # 查询扩展（限制最多5个词，避免过多并发DB查询）
        expanded_terms = [query]
        if use_query_expansion:
            try:
                expanded_terms = await asyncio.wait_for(expand_query(query), timeout=3.0)
            except asyncio.TimeoutError:
                logger.debug("查询扩展超时(3s)，使用本地扩展")
                try:
                    expanded_terms = await expand_query_simple(query)
                except Exception:
                    expanded_terms = [query]
            except Exception as e:
                logger.debug(f"查询扩展失败，使用本地扩展: {e}")
                try:
                    expanded_terms = await expand_query_simple(query)
                except Exception:
                    expanded_terms = [query]
        expanded_terms = expanded_terms[:3]

        vector_results: List[Dict[str, Any]] = []
        bm25_results: List[Dict[str, Any]] = []
        audio_results: List[Dict[str, Any]] = []

        # 并行执行向量检索、BM25检索和音频搜索
        coros = []
        if use_vector:
            coros.append(self._parallel_vector_search(expanded_terms, category, top_k))
        else:
            coros.append(_empty_coro())
        if use_bm25:
            coros.append(self._parallel_bm25_search(expanded_terms, category, top_k))
        else:
            coros.append(_empty_coro())
        if include_audio:
            coros.append(self._search_audio(query, category, top_k))
        else:
            coros.append(_empty_coro())

        try:
            v_res, b_res, a_res = await asyncio.wait_for(
                asyncio.gather(*coros, return_exceptions=True),
                timeout=self.search_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"混合检索并行搜索超时({self.search_timeout}s)，返回已有结果")
            v_res, b_res, a_res = [], [], []
        if isinstance(v_res, Exception):
            logger.warning(f"向量检索全部失败: {type(v_res).__name__}: {v_res}")
        else:
            vector_results = v_res
        if isinstance(b_res, Exception):
            logger.warning(f"BM25检索全部失败: {type(b_res).__name__}: {b_res}")
        else:
            bm25_results = b_res
        if isinstance(a_res, Exception):
            logger.warning(f"音频搜索失败: {type(a_res).__name__}: {a_res}")
        else:
            audio_results = a_res

        # 合并文本结果
        if use_vector and use_bm25:
            results = self._rrf_merge(vector_results, bm25_results)
        elif use_vector:
            results = vector_results
        else:
            results = bm25_results

        # 追加音频结果
        results.extend(audio_results)

        # 去重（同一 chunk 可能被多个扩展词命中）
        seen_ids = set()
        deduped = []
        for r in results:
            rid = r.get("id")
            if rid not in seen_ids:
                seen_ids.add(rid)
                deduped.append(r)
        results = deduped

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

        # Cross-encoder 精排
        if self.reranker and results:
            try:
                results = await self.reranker.rerank(query, results, top_k=top_k)
            except Exception as re_err:
                logger.warning(f"Reranker 精排失败，使用 RRF 原始排序: {re_err}")

        results.sort(
            key=lambda x: x.get("rerank_score", x.get("score", x.get("similarity", 0))),
            reverse=True,
        )

        # 跨域概念boost：如果query包含跨域概念，提升匹配领域的文档得分
        if related_domains:
            for r in results:
                r_cat = r.get("category", "")
                if r_cat in related_domains:
                    r["score"] = r.get("score", 0) * 1.15
                    r["cross_domain_boost"] = True
            results.sort(
                key=lambda x: x.get("rerank_score", x.get("score", x.get("similarity", 0))),
                reverse=True,
            )

        # 为结果附加概念元数据
        if concept_info:
            for r in results[:top_k]:
                r["matched_concepts"] = [c["concept"] for c in concept_info]
                r["related_domains"] = related_domains

        # 表来源多样性保障：确保每个 source_table 在 top_k 中有最低名额
        results = self._ensure_table_diversity(results, top_k)

        # 域间多样性保障：防止单一域（如气功83%文档）垄断结果
        results = self._ensure_category_diversity(results, top_k)

        # 为分块结果补充上下文窗口
        results = await self._enrich_chunk_context(results)

        logger.info(
            f"混合检索: query='{query}', expanded={expanded_terms}, "
            f"vector={len(vector_results)}, bm25={len(bm25_results)}, "
            f"audio={len(audio_results)}, merged={len(results)}"
        )

        try:
            await record_search_outcome(self.db_pool, query, results, category, source="hybrid")
        except Exception as gap_err:
            logger.debug(f"缺口记录跳过: {gap_err}")

        for r in results[:top_k]:
            if "source_citation" not in r:
                citation = _build_citation(r, r.get("source_table", ""))
                if citation:
                    r["source_citation"] = citation

        # 为每个结果提取片段并高亮
        if self.highlighter:
            for r in results:
                if "snippet" not in r:
                    content = r.get("content", "")
                    if content:
                        try:
                            r["snippet"] = self.highlighter.extract_snippet(content, query)
                        except Exception as e:
                            logger.debug(f"片段提取失败: {e}")
                            r["snippet"] = content[:200] + "..." if len(content) > 200 else content

        return results[:top_k]

    async def _parallel_vector_search(
        self, terms: List[str], category: Optional[str], top_k: int
    ) -> List[Dict[str, Any]]:
        """并行向量检索多个扩展词——批量 embed 一次，再按表并行搜索"""
        if not terms:
            return []

        # Phase 1: batch embed all terms at once
        try:
            vectors = await self.vector_retriever.embed_batch(terms)
        except Exception as e:
            logger.warning(f"批量 embed 失败，降级逐个 embed: {e}")
            vectors = []
            for t in terms:
                try:
                    vectors.append(await self.vector_retriever.embed_text(t))
                except Exception:
                    pass
        if not vectors:
            return []

        vector_strs = ["[" + ",".join(map(str, v)) + "]" for v in vectors]

        # Phase 2: for each vector, search all 4 tables in parallel
        async def _search_all_tables(vec_str: str) -> List[Dict[str, Any]]:
            return await self.vector_retriever.search_by_vector(vec_str, category, top_k * 2)

        batches = await asyncio.gather(
            *[_search_all_tables(vs) for vs in vector_strs],
            return_exceptions=True,
        )
        results = []
        for batch in batches:
            if isinstance(batch, list):
                results.extend(batch)
            elif isinstance(batch, Exception):
                logger.warning(f"向量检索子任务失败: {type(batch).__name__}: {batch}")
        return results

    async def _parallel_bm25_search(
        self, terms: List[str], category: Optional[str], top_k: int
    ) -> List[Dict[str, Any]]:
        """并行BM25检索多个扩展词"""
        tasks = [self.bm25_retriever.search(term, category, top_k * 2) for term in terms]
        batches = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        for batch in batches:
            if isinstance(batch, list):
                results.extend(batch)
            elif isinstance(batch, Exception):
                logger.warning(f"BM25检索子任务失败: {type(batch).__name__}: {batch}")
        return results

    async def _enrich_chunk_context(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """为分块结果补充前后文（批量查询，避免 N+1）"""
        # Separate by source table and collect IDs
        tbv_ids = []
        chunk_ids = []
        tbv_results = []
        chunk_results = []
        other_results = []

        for r in results:
            source = r.get("source_table", "")
            if source == "textbook_blocks_v2":
                block_id = str(r["id"]).replace("tbv_", "")
                tbv_ids.append(int(block_id))
                tbv_results.append(r)
            elif source == "doc_chunks":
                chunk_id = str(r["id"]).replace("chunk_", "")
                chunk_ids.append(int(chunk_id))
                chunk_results.append(r)
            else:
                other_results.append(r)

        # Batch load context for textbook_blocks_v2 and doc_chunks in parallel
        ctx_tbv_map, ctx_chunk_map = {}, {}
        if tbv_ids or chunk_ids:
            try:

                async def _load_tbv():
                    if tbv_ids:
                        return await self._batch_load_tbv_context(tbv_ids)
                    return {}

                async def _load_chunk():
                    if chunk_ids:
                        return await self._batch_load_chunk_context(chunk_ids)
                    return {}

                ctx_tbv_map, ctx_chunk_map = await asyncio.gather(_load_tbv(), _load_chunk())
            except Exception:
                pass

        # Apply context to tbv_results
        if tbv_ids:
            ctx_map = ctx_tbv_map
            for r in tbv_results:
                block_id = int(str(r["id"]).replace("tbv_", ""))
                ctx = ctx_map.get(block_id, ("", ""))
                r["context_before"] = ctx[0]
                r["context_after"] = ctx[1]

        # Apply context to chunk_results
        if chunk_ids:
            ctx_map = ctx_chunk_map
            for r in chunk_results:
                chunk_id = int(str(r["id"]).replace("chunk_", ""))
                ctx = ctx_map.get(chunk_id, ("", ""))
                r["context_before"] = ctx[0]
                r["context_after"] = ctx[1]

        return other_results + tbv_results + chunk_results

    async def _batch_load_tbv_context(self, ids: List[int]) -> Dict[int, tuple]:
        """批量加载 textbook_blocks_v2 前后文"""
        if not ids:
            return {}
        rows = await self.db_pool.fetch(
            """
            SELECT cur.id, prev.content as before, next.content as after
            FROM textbook_blocks_v2 cur
            LEFT JOIN textbook_blocks_v2 prev
                ON prev.node_id = cur.node_id AND prev.block_order = cur.block_order - 1
            LEFT JOIN textbook_blocks_v2 next
                ON next.node_id = cur.node_id AND next.block_order = cur.block_order + 1
            WHERE cur.id = ANY($1::int[])
            """,
            ids,
        )
        return {r["id"]: (r["before"] or "", r["after"] or "") for r in rows}

    async def _batch_load_chunk_context(self, ids: List[int]) -> Dict[int, tuple]:
        """批量加载 doc_chunks 前后文"""
        if not ids:
            return {}
        rows = await self.db_pool.fetch(
            """
            SELECT cur.id, prev.content as before, next.content as after
            FROM doc_chunks cur
            LEFT JOIN doc_chunks prev
                ON prev.doc_id = cur.doc_id AND prev.chunk_index = cur.chunk_index - 1
            LEFT JOIN doc_chunks next
                ON next.doc_id = cur.doc_id AND next.chunk_index = cur.chunk_index + 1
            WHERE cur.id = ANY($1::int[])
            """,
            ids,
        )
        return {r["id"]: (r["before"] or "", r["after"] or "") for r in rows}

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
