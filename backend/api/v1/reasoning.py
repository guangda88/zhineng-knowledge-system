"""推理API路由"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.v1.search import get_hybrid_retriever
from backend.common import rows_to_list
from backend.common.typing import JSONResponse
from backend.config import get_config
from backend.core.database import init_db_pool
from backend.services.reasoning import CoTReasoner, GraphRAGReasoner, ReActReasoner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["reasoning"])

# 推理器实例（延迟初始化）
_cot_reasoner: Optional[CoTReasoner] = None
_react_reasoner: Optional[ReActReasoner] = None
_graph_rag_reasoner: Optional[GraphRAGReasoner] = None


# ========== 数据模型 ==========


class ReasoningRequest(BaseModel):
    """推理请求模型"""

    question: str = Field(..., min_length=1, max_length=500, description="用户问题")
    mode: str = Field("cot", pattern="^(cot|react|graph_rag|auto)$", description="推理模式")
    category: Optional[str] = Field(
        None,
        pattern="^(气功|中医|儒家|佛家|道家|武术|哲学|科学|心理学)$",
        description="指定分类",
    )
    session_id: Optional[str] = Field(None, description="会话ID")
    use_rag: bool = Field(True, description="是否使用RAG检索上下文")


class GraphQueryRequest(BaseModel):
    """图谱查询请求模型"""

    entity1: str = Field(..., description="起始实体")
    entity2: str = Field(..., description="目标实体")
    max_depth: int = Field(3, ge=1, le=5, description="最大深度")


# ========== 辅助函数 ==========


async def get_cot_reasoner() -> CoTReasoner:
    """获取CoT推理器实例"""
    global _cot_reasoner
    if _cot_reasoner is None:
        _cfg = get_config()
        api_key = _cfg.DEEPSEEK_API_KEY
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for reasoning service")
        _cot_reasoner = CoTReasoner(api_key=api_key, api_url=_cfg.DEEPSEEK_API_URL or "")
    return _cot_reasoner


async def get_react_reasoner() -> ReActReasoner:
    """获取ReAct推理器实例"""
    global _react_reasoner
    if _react_reasoner is None:
        _cfg = get_config()
        api_key = _cfg.DEEPSEEK_API_KEY
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for reasoning service")
        _react_reasoner = ReActReasoner(api_key=api_key, api_url=_cfg.DEEPSEEK_API_URL or "")
    return _react_reasoner


async def get_graph_rag_reasoner() -> GraphRAGReasoner:
    """获取GraphRAG推理器实例"""
    global _graph_rag_reasoner
    if _graph_rag_reasoner is None:
        _cfg = get_config()
        api_key = _cfg.DEEPSEEK_API_KEY
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for reasoning service")
        _graph_rag_reasoner = GraphRAGReasoner(api_key=api_key, api_url=_cfg.DEEPSEEK_API_URL or "")
    return _graph_rag_reasoner


async def retrieve_context(question: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """检索相关上下文

    Args:
        question: 用户问题
        category: 分类筛选

    Returns:
        相关文档列表
    """
    try:
        retriever = await get_hybrid_retriever()
        results = await retriever.search(
            query=question, category=category, top_k=5, use_vector=True, use_bm25=True
        )
        return results
    except Exception as e:
        logger.error(f"Context retrieval failed: {e}")
        return []


# ========== 路由 ==========


@router.post("/reason", response_model=JSONResponse)
async def reasoning_answer(request: ReasoningRequest) -> JSONResponse:
    """推理问答API — 支持多种推理模式：CoT、ReAct、GraphRAG"""
    try:
        # 自动选择模式
        mode = request.mode
        if mode == "auto":
            if "关系" in request.question or "区别" in request.question:
                mode = "graph_rag"
            elif "如何" in request.question or "步骤" in request.question:
                mode = "react"
            else:
                mode = "cot"

        # 检索上下文
        context = []
        if request.use_rag:
            context = await retrieve_context(request.question, request.category)

        # 根据模式执行推理
        if mode == "cot":
            reasoner = await get_cot_reasoner()
            result = await reasoner.reason(question=request.question, context=context)
        elif mode == "react":
            reasoner = await get_react_reasoner()
            result = await reasoner.reason(question=request.question, context=context)
        elif mode == "graph_rag":
            reasoner = await get_graph_rag_reasoner()
            result = await reasoner.reason(question=request.question, context=context)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的推理模式: {mode}")
    except HTTPException:
        raise
    except (RuntimeError, ValueError) as e:
        error_msg = str(e).lower()
        if "rate limit" in error_msg or "429" in error_msg:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": "LLM API调用过于频繁，请稍后重试",
                },
            ) from e
        if "api_key" in error_msg or "not initialized" in error_msg:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "service_unavailable",
                    "message": "推理服务未配置，请设置DEEPSEEK_API_KEY",
                },
            ) from e
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        logger.error(f"reasoning_answer failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="推理服务失败")

    session_id = request.session_id or datetime.now().strftime("%Y%m%d%H%M%S")

    return {
        "question": request.question,
        "mode": mode,
        "session_id": session_id,
        **result.to_dict(),
    }


@router.post("/graph/query", response_model=JSONResponse)
async def graph_query(request: GraphQueryRequest) -> JSONResponse:
    """知识图谱查询API — 查找两个实体间的关系路径"""
    try:
        reasoner = await get_graph_rag_reasoner()

        path = reasoner.kg.find_path(
            start=request.entity1, end=request.entity2, max_depth=request.max_depth
        )

        if path:
            path_details = []
            for i in range(len(path) - 1):
                for rel in reasoner.kg.relations:
                    if rel.source == path[i] and rel.target == path[i + 1]:
                        path_details.append(
                            {"from": path[i], "relation": rel.relation_type, "to": path[i + 1]}
                        )
                        break

            return {
                "entity1": request.entity1,
                "entity2": request.entity2,
                "found": True,
                "path": path,
                "path_details": path_details,
            }
        else:
            return {
                "entity1": request.entity1,
                "entity2": request.entity2,
                "found": False,
                "message": "未找到关联路径",
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"graph_query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="知识图谱查询失败")


@router.get("/graph/data", response_model=JSONResponse)
async def get_graph_data() -> JSONResponse:
    """获取知识图谱数据（用于前端可视化）"""
    try:
        reasoner = await get_graph_rag_reasoner()
        return reasoner.get_graph_data()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_graph_data failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取图谱数据失败")


@router.post("/graph/build", response_model=JSONResponse)
async def build_graph(category: Optional[str] = None) -> JSONResponse:
    """从现有文档构建知识图谱"""
    try:
        pool = await init_db_pool()
        reasoner = await get_graph_rag_reasoner()

        if category:
            rows = await pool.fetch(
                "SELECT id, title, content FROM documents WHERE category = $1 LIMIT 50", category
            )
        else:
            rows = await pool.fetch("SELECT id, title, content FROM documents LIMIT 100")

        contexts = rows_to_list(rows)

        await reasoner._build_kg_from_context(contexts)

        entity_count = len(reasoner.kg.entities)
        relation_count = len(reasoner.kg.relations)

        return {
            "status": "success",
            "message": "知识图谱构建完成",
            "entity_count": entity_count,
            "relation_count": relation_count,
            "document_count": len(contexts),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"build_graph failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="构建知识图谱失败")


@router.get("/reasoning/status", response_model=JSONResponse)
async def reasoning_status() -> JSONResponse:
    """获取推理服务状态"""
    try:
        reasoner = await get_graph_rag_reasoner()

        return {
            "cot_enabled": True,
            "react_enabled": True,
            "graph_rag_enabled": True,
            "graph_entity_count": len(reasoner.kg.entities),
            "graph_relation_count": len(reasoner.kg.relations),
            "api_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reasoning_status failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取推理服务状态失败")
