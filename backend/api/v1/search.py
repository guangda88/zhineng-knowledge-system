"""搜索API路由"""

import html
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.cache.decorators import cached_api_categories, cached_api_search, cached_api_stats
from backend.common import get_document_stats, rows_to_list, search_documents
from backend.common.typing import JSONResponse
from backend.core.database import init_db_pool
from backend.core.request_stats import get_request_stats
from backend.services.retrieval import HybridRetriever

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


class EmbeddingUpdateRequest(BaseModel):
    """嵌入更新请求模型"""

    doc_ids: Optional[List[int]] = Field(None, description="指定文档ID列表")
    all_docs: bool = Field(False, description="是否更新所有文档")


class ChatRequest(BaseModel):
    """聊天请求模型"""

    question: str = Field(..., min_length=1, max_length=1000, description="用户问题")
    category: Optional[str] = Field(None, pattern="^(气功|中医|儒家)$", description="指定分类")
    session_id: Optional[str] = Field(None, description="会话ID")


class ChatResponse(BaseModel):
    """聊天响应模型"""

    answer: str
    sources: List[Dict[str, Any]]
    session_id: str


# ========== 路由 ==========


@router.get("")
@cached_api_search(ttl=300)  # 5分钟缓存
async def search_endpoint(
    q: str = Query(..., min_length=1, max_length=200),
    category: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
) -> JSONResponse:
    """关键词搜索（缓存5分钟）"""
    try:
        pool = await init_db_pool()
        results = await search_documents(pool, q, category, limit)
        return {"query": q, "total": len(results), "results": results}
    except Exception as e:
        logger.error(f"搜索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


@router.post("/hybrid", response_model=JSONResponse)
async def hybrid_search(request: HybridSearchRequest) -> JSONResponse:
    """
    混合检索API

    结合向量语义检索和BM25关键词检索
    """
    try:
        retriever = await get_hybrid_retriever()

        results = await retriever.search(
            query=request.query,
            category=request.category,
            top_k=request.top_k,
            use_vector=request.use_vector,
            use_bm25=request.use_bm25,
        )

        return {"query": request.query, "total": len(results), "results": results}
    except Exception as e:
        logger.error(f"混合检索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"混合检索失败: {e}")


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


# ========== 兼容API路由（添加到主路由器） ==========

# 创建额外路由器用于非search前缀的路由
extra_router = APIRouter(tags=["search"])


@extra_router.post("/api/v1/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest) -> ChatResponse:
    """智能问答（简单版本）"""
    try:
        pool = await init_db_pool()

        sources = await search_documents(pool, request.question, request.category, 3)

        if sources:
            answer = f"根据知识库找到 {len(sources)} 条相关内容：\n\n"
            for i, s in enumerate(sources[:3], 1):
                safe_title = html.escape(s["title"])
                safe_content = html.escape(s["content"][:150]) + (
                    "..." if len(s["content"]) > 150 else ""
                )
                answer += f"{i}. **{safe_title}**\n{safe_content}\n\n"
        else:
            answer = (
                "抱歉，知识库中没有找到相关内容。请尝试其他关键词，如：气功、八段锦、中医、论语等。"
            )

        session_id = request.session_id or datetime.now().strftime("%Y%m%d%H%M%S")

        return ChatResponse(answer=answer, sources=sources, session_id=session_id)
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
