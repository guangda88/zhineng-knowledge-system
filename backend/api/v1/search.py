"""搜索API路由"""

import html
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.cache.decorators import (
    cached,
    cached_api_categories,
    cached_api_search,
    cached_api_stats,
)
from backend.common import get_document_stats, rows_to_list, search_documents
from backend.common.typing import JSONResponse
from backend.core.database import init_db_pool
from backend.core.request_stats import get_request_stats
from backend.services.retrieval import HybridRetriever
from backend.services.retrieval.gap_tracker import record_search_outcome
from backend.services.retrieval.regex_searcher import RegexSearcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["search"])

# 检索器实例（延迟初始化）
_hybrid_retriever: Optional[HybridRetriever] = None


async def get_hybrid_retriever() -> HybridRetriever:
    """获取混合检索器实例"""
    global _hybrid_retriever
    if _hybrid_retriever is None:
        pool = await init_db_pool()
        _hybrid_retriever = HybridRetriever(pool)
        await _hybrid_retriever.initialize()
    return _hybrid_retriever


# ========== 数据模型 ==========


class HybridSearchRequest(BaseModel):
    """混合搜索请求模型"""

    query: str = Field(..., min_length=1, max_length=200, description="搜索查询")
    category: Optional[str] = Field(
        None,
        pattern="^(气功|中医|儒家|佛家|道家|武术|哲学|科学|心理学)$",
        description="分类筛选",
    )
    top_k: int = Field(10, ge=1, le=50, description="返回数量")
    use_vector: bool = Field(True, description="是否使用向量检索")
    use_bm25: bool = Field(True, description="是否使用BM25检索")
    use_query_expansion: bool = Field(True, description="是否使用查询扩展")


class EmbeddingUpdateRequest(BaseModel):
    """嵌入更新请求模型"""

    doc_ids: Optional[List[int]] = Field(None, description="指定文档ID列表")
    all_docs: bool = Field(False, description="是否更新所有文档")


class ChatRequest(BaseModel):
    """聊天请求模型"""

    question: str = Field(..., min_length=1, max_length=1000, description="用户问题")
    category: Optional[str] = Field(None, pattern="^(气功|中医|儒家)$", description="指定分类")
    session_id: Optional[str] = Field(None, description="会话ID")


class RegexSearchRequest(BaseModel):
    """正则搜索请求模型"""

    pattern: str = Field(..., min_length=1, max_length=500, description="正则表达式模式")
    tables: Optional[List[str]] = Field(None, description="搜索的表列表，默认所有表")
    category: Optional[str] = Field(
        None, pattern="^(气功|中医|儒家|佛家|道家|武术|哲学|科学|心理学)$", description="分类筛选"
    )
    limit: int = Field(50, ge=1, le=200, description="返回数量限制")
    case_sensitive: bool = Field(False, description="是否区分大小写")
    with_context: bool = Field(True, description="是否返回匹配上下文片段")


class ChatResponse(BaseModel):
    """聊天响应模型"""

    answer: str
    sources: List[Dict[str, Any]]
    session_id: str
    citations: List[Dict[str, str]] = []
    confidence: str = "unverified"


def _observe_search_latency(latency_ms: float) -> None:
    try:
        from backend.monitoring.anomaly_detector import get_anomaly_detector
        get_anomaly_detector().observe("search_latency_ms", latency_ms)
    except Exception:
        pass


def _get_related_domains(query: str) -> list:
    try:
        from backend.services.knowledge_graph.concept_map import get_related_domains
        return get_related_domains(query)
    except Exception:
        return []


def _get_concept_info(query: str) -> list:
    try:
        from backend.services.knowledge_graph.concept_map import get_concept_info
        return get_concept_info(query)
    except Exception:
        return []


# ========== 路由 ==========


@router.get("")
@cached_api_search(ttl=300)  # 5分钟缓存
async def search_endpoint(
    q: str = Query(..., min_length=1, max_length=200),
    category: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
) -> JSONResponse:
    """混合检索（向量+BM25，缓存5分钟）"""
    import time as _time
    t0 = _time.time()
    try:
        try:
            retriever = await get_hybrid_retriever()
            results = await retriever.search(
                query=q, category=category, top_k=limit,
                use_vector=True, use_bm25=True,
            )
        except Exception:
            logger.warning("混合检索回退到ILIKE搜索", exc_info=True)
            pool = await init_db_pool()
            results = await search_documents(pool, q, category, limit)
            for r in results:
                r.setdefault("similarity", 0.0)
        _observe_search_latency((_time.time() - t0) * 1000)
        return {
            "query": q,
            "total": len(results),
            "results": results,
            "related_domains": _get_related_domains(q),
            "concepts": _get_concept_info(q),
        }
    except Exception as e:
        logger.error(f"搜索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


@router.post("/hybrid", response_model=JSONResponse)
@cached(namespace="api_hybrid_search", ttl=600, key_prefix="hybrid", skip_cache_param="skip_cache")
async def hybrid_search(request: HybridSearchRequest, skip_cache: bool = False) -> JSONResponse:
    """
    混合检索API

    结合向量语义检索和BM25关键词检索
    """
    import time as _time
    t0 = _time.time()
    try:
        retriever = await get_hybrid_retriever()

        results = await retriever.search(
            query=request.query,
            category=request.category,
            top_k=request.top_k,
            use_vector=request.use_vector,
            use_bm25=request.use_bm25,
            use_query_expansion=request.use_query_expansion,
        )

        _observe_search_latency((_time.time() - t0) * 1000)
        return {
            "query": request.query,
            "total": len(results),
            "results": results,
            "related_domains": _get_related_domains(request.query),
            "concepts": _get_concept_info(request.query),
        }
    except Exception as e:
        logger.error(f"混合检索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"混合检索失败: {e}")


@router.post("/regex", response_model=JSONResponse)
async def regex_search(request: RegexSearchRequest) -> JSONResponse:
    """
    正则表达式搜索

    支持 PCRE 正则表达式语法，提供多表搜索和匹配位置信息。
    """
    try:
        # 验证正则表达式
        pool = await init_db_pool()
        searcher = RegexSearcher(pool)

        # 验证模式有效性
        is_valid = await searcher.validate_pattern(request.pattern)
        if not is_valid:
            raise HTTPException(status_code=400, detail="无效的正则表达式模式")

        # 执行搜索
        if request.with_context:
            results = await searcher.search_with_context(
                pattern=request.pattern,
                tables=request.tables,
                category=request.category,
                limit=request.limit,
                case_sensitive=request.case_sensitive,
            )
        else:
            results = await searcher.search(
                pattern=request.pattern,
                tables=request.tables,
                category=request.category,
                limit=request.limit,
                case_sensitive=request.case_sensitive,
            )

        # 统计各表匹配数量
        counts = await searcher.count_matches(
            pattern=request.pattern, tables=request.tables, case_sensitive=request.case_sensitive
        )

        return {
            "pattern": request.pattern,
            "total": len(results),
            "table_counts": counts,
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"正则搜索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"正则搜索失败: {e}")


@router.post("/embeddings/update", response_model=JSONResponse)
async def update_embeddings(request: EmbeddingUpdateRequest) -> JSONResponse:
    """更新文档嵌入向量"""
    try:
        retriever = await get_hybrid_retriever()

        if request.all_docs:
            stats = await retriever.update_embeddings()
            return {
                "status": "success",
                "message": f"已更新 {stats['updated']} 个文档的嵌入向量",
                "stats": stats,
            }
        else:
            updated = 0
            if request.doc_ids:
                for doc_id in request.doc_ids:
                    if await retriever.vector_retriever.update_embedding(doc_id):
                        updated += 1
            return {
                "status": "success",
                "message": f"已更新 {updated} 个文档的嵌入向量",
                "updated": updated,
            }
    except Exception as e:
        logger.error(f"更新嵌入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新嵌入失败: {e}")


@router.get("/retrieval/status", response_model=JSONResponse)
async def retrieval_status() -> JSONResponse:
    """获取检索服务状态"""
    try:
        pool = await init_db_pool()

        with_vector = await pool.fetchval(
            "SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL"
        )
        total_docs = await pool.fetchval("SELECT COUNT(*) FROM documents")

        total_audio = await pool.fetchval("SELECT COUNT(*) FROM audio_files") or 0
        transcribed_audio = (
            await pool.fetchval("SELECT COUNT(*) FROM audio_files WHERE status = 'transcribed'")
            or 0
        )
        audio_segments = await pool.fetchval("SELECT COUNT(*) FROM audio_segments") or 0
        audio_vectorized = (
            await pool.fetchval("SELECT COUNT(*) FROM audio_segments WHERE embedding IS NOT NULL")
            or 0
        )

        return {
            "vector_enabled": True,
            "bm25_enabled": True,
            "hybrid_enabled": True,
            "documents_with_vector": with_vector,
            "total_documents": total_docs,
            "embedding_coverage": round(with_vector / total_docs * 100, 2) if total_docs > 0 else 0,
            "audio": {
                "total_files": total_audio,
                "transcribed_files": transcribed_audio,
                "total_segments": audio_segments,
                "vectorized_segments": audio_vectorized,
            },
        }
    except Exception as e:
        logger.error(f"获取检索状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取检索状态失败: {e}")


@router.get("/cross-domain")
async def cross_domain_endpoint(
    q: str = Query(..., min_length=1, max_length=200),
    top_k: int = Query(3, ge=1, le=10, description="每个领域最多返回数"),
    limit: int = Query(20, ge=1, le=50, description="总结果上限"),
) -> JSONResponse:
    """跨域联合检索：按领域分组返回搜索结果"""
    from backend.services.retrieval.cross_domain import cross_domain_search

    pool = await init_db_pool()
    result = await cross_domain_search(pool, q, top_k_per_domain=top_k, limit=limit)
    return result


# ========== 兼容API路由（添加到主路由器） ==========

# 创建额外路由器用于非search前缀的路由
extra_router = APIRouter(tags=["search"])


@extra_router.post("/api/v1/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest) -> ChatResponse:
    """智能问答（混合检索版本）"""
    try:
        pool = await init_db_pool()

        try:
            retriever = await get_hybrid_retriever()
            sources = await retriever.search(
                query=request.question, category=request.category, top_k=3,
                use_vector=True, use_bm25=True,
            )
        except Exception:
            sources = await search_documents(pool, request.question, request.category, 3)
            for s in sources:
                s.setdefault("similarity", 0.0)

        try:
            await record_search_outcome(
                pool, request.question, sources, request.category, source="ask"
            )
        except Exception:
            pass

        citations = []
        confidence = "unverified"

        if sources:
            answer = f"根据知识库找到 {len(sources)} 条相关内容：\n\n"
            for i, s in enumerate(sources[:3], 1):
                safe_title = html.escape(s["title"])
                safe_content = html.escape(s["content"][:150]) + (
                    "..." if len(s["content"]) > 150 else ""
                )
                answer += f"{i}. **{safe_title}**\n{safe_content}\n\n"
                citations.append({
                    "title": s.get("title", ""),
                    "source_table": s.get("source_table", "documents"),
                    "doc_id": str(s.get("id", "")),
                    "category": s.get("category", ""),
                    "snippet": s.get("content", "")[:200],
                    "similarity": s.get("similarity"),
                })
            confidence = "sourced"
        else:
            answer = (
                "抱歉，知识库中没有找到相关内容。请尝试其他关键词，如：气功、八段锦、中医、论语等。"
            )

        session_id = request.session_id or datetime.now().strftime("%Y%m%d%H%M%S")

        # 自动保存到 chat_history + 上下文元数据
        try:
            async with pool.acquire() as conn:
                # 确保会话存在，首次创建 message_count=2
                await conn.execute(
                    """
                    INSERT INTO sessions (id, title, status, message_count, last_message_at)
                    VALUES ($1, $2, 'active', 2, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        message_count = sessions.message_count + 2,
                        last_message_at = CURRENT_TIMESTAMP,
                        status = 'active'
                    """,
                    session_id,
                    f"会话 {session_id[:10]}",
                )
                # 保存用户消息
                await conn.execute(
                    """
                    INSERT INTO chat_history (session_id, role, content)
                    VALUES ($1, 'user', $2)
                    """,
                    session_id,
                    request.question,
                )
                # 保存助手回复
                await conn.execute(
                    """
                    INSERT INTO chat_history (session_id, role, content, metadata)
                    VALUES ($1, 'assistant', $2, $3)
                    """,
                    session_id,
                    answer,
                    json.dumps({"sources_count": len(sources)}),
                )
                # 更新上下文元数据到 sessions.metadata
                context_meta = {
                    "last_question": request.question[:200],
                    "last_sources_count": len(sources),
                    "last_activity": datetime.now().isoformat(),
                }
                # 合并已有 metadata，保留 tasks/decisions 等字段
                await conn.execute(
                    """
                    UPDATE sessions SET metadata = COALESCE(metadata, '{}') || $1::jsonb
                    WHERE id = $2
                    """,
                    json.dumps({"context": context_meta}),
                    session_id,
                )
        except Exception as save_err:
            logger.warning(f"保存聊天历史失败（不影响回复）: {save_err}")

        return ChatResponse(
            answer=answer,
            sources=sources,
            session_id=session_id,
            citations=citations,
            confidence=confidence,
        )
    except Exception as e:
        logger.error(f"智能问答失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"智能问答失败: {e}")


@extra_router.get("/api/v1/categories", response_model=JSONResponse)
@cached_api_categories(ttl=1800)  # 30分钟缓存
async def get_categories() -> JSONResponse:
    """获取所有分类（缓存30分钟）"""
    try:
        pool = await init_db_pool()
        rows = await pool.fetch(
            """SELECT category, COUNT(*) as count
               FROM documents GROUP BY category ORDER BY count DESC"""
        )

        return {"categories": rows_to_list(rows)}
    except Exception as e:
        logger.error(f"获取分类失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取分类失败: {e}")


@extra_router.get("/api/v1/stats", response_model=JSONResponse)
@cached_api_stats(ttl=300)  # 5分钟缓存
async def get_stats() -> JSONResponse:
    """系统统计"""
    try:
        pool = await init_db_pool()
        request_stats = get_request_stats()

        stats = await get_document_stats(pool)
        stats["request_stats"] = request_stats

        return stats
    except Exception as e:
        logger.error(f"获取统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取统计失败: {e}")
