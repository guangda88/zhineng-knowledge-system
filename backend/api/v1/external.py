"""外部API接口

提供标准化的REST API供外部程序访问灵知系统知识库
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import jieba
import jieba.analyse
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from backend.core.database import init_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/external/v1", tags=["外部API"])


# ==================== 认证系统 ====================

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKey:
    """API密钥管理"""

    def __init__(self):
        self.valid_keys = self._load_keys()

    def _load_keys(self) -> Dict[str, Dict]:
        keys_json = os.getenv("EXTERNAL_API_KEYS", "")
        if keys_json:
            try:
                return json.loads(keys_json)
            except json.JSONDecodeError:
                logger.error("EXTERNAL_API_KEYS 环境变量 JSON 格式错误")
                return {}
        if os.getenv("ENVIRONMENT") == "development":
            logger.warning("开发模式使用默认 API 密钥，生产环境请设置 EXTERNAL_API_KEYS")
            return {
                "dev-key-for-testing-only": {
                    "name": "开发测试",
                    "rate_limit": 1000,
                    "permissions": ["search", "retrieve", "analyze"],
                    "active": True,
                },
            }
        return {}

    def validate(self, api_key: str) -> Optional[Dict]:
        """验证API密钥"""
        key_data = self.valid_keys.get(api_key)
        if key_data and key_data.get("active"):
            return key_data
        return None


api_key_manager = APIKey()


async def verify_api_key(api_key: Optional[str] = Depends(api_key_header)) -> Dict:
    """验证API密钥依赖项"""
    if not api_key:
        raise HTTPException(status_code=401, detail="缺少 API 密钥 (X-API-Key)")
    key_data = api_key_manager.validate(api_key)
    if not key_data:
        raise HTTPException(status_code=403, detail="无效的API密钥或密钥已过期")
    return key_data


# ==================== 请求/响应模型 ====================


class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索查询", min_length=1, max_length=500)
    category: Optional[str] = Field(None, description="知识分类")
    limit: int = Field(10, ge=1, le=100, description="返回结果数量")
    threshold: float = Field(0.5, ge=0.0, le=1.0, description="相似度阈值")


class RetrieveRequest(BaseModel):
    query: str = Field(..., description="检索内容", min_length=1, max_length=500)
    top_k: int = Field(5, ge=1, le=50, description="返回最相关的K个结果")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件")


class AnalyzeRequest(BaseModel):
    text: str = Field(..., description="待分析的文本")
    analysis_type: str = Field("sentiment", description="分析类型")


class APIResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SearchResult(BaseModel):
    content: str
    source: str
    category: str
    score: float
    metadata: Dict[str, Any]


# ==================== API端点 ====================


@router.post("/search", response_model=APIResponse)
async def search_knowledge(
    request: SearchRequest,
    api_key_data: Dict = Depends(verify_api_key),
) -> APIResponse:
    """搜索知识库"""
    try:
        if "search" not in api_key_data["permissions"]:
            raise HTTPException(status_code=403, detail="权限不足")

        pool = await init_db_pool()

        category_filter = ""
        params: list = [request.query]
        if request.category:
            category_filter = "AND category = $2"
            params.append(request.category)

        rows = await pool.fetch(
            f"""
            SELECT content, metadata, category,
                   similarity as score
            FROM (
                SELECT content, metadata, category,
                       1 - (embedding <=> (
                           SELECT embedding FROM documents
                           WHERE content ILIKE '%' || $1 || '%'
                           LIMIT 1
                       )) as similarity
                FROM documents
                WHERE 1=1 {category_filter}
                ORDER BY similarity DESC
                LIMIT ${len(params) + 1}
            ) sub
            """,
            *params,
            request.limit,
        )

        results = [
            {
                "content": r["content"][:500] if r["content"] else "",
                "source": (r.get("metadata") or {}).get("source", "未知"),
                "category": r.get("category", "未分类"),
                "score": float(r.get("score", 0.0)),
                "metadata": dict(r.get("metadata") or {}),
            }
            for r in rows
        ]

        return APIResponse(
            success=True,
            message=f"找到{len(results)}条结果",
            data={"query": request.query, "total": len(results), "results": results},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return APIResponse(success=False, error=str(e))


@router.post("/retrieve", response_model=APIResponse)
async def retrieve_knowledge(
    request: RetrieveRequest,
    api_key_data: Dict = Depends(verify_api_key),
) -> APIResponse:
    """检索知识"""
    try:
        if "retrieve" not in api_key_data["permissions"]:
            raise HTTPException(status_code=403, detail="权限不足")

        pool = await init_db_pool()
        rows = await pool.fetch(
            """
            SELECT id, content, category, metadata
            FROM documents
            WHERE content ILIKE '%' || $1 || '%'
            ORDER BY created_at DESC
            LIMIT $2
            """,
            request.query,
            request.top_k,
        )

        results = [dict(r) for r in rows]
        if request.filters:
            results = _apply_filters(results, request.filters)

        return APIResponse(
            success=True,
            message=f"检索到{len(results)}条相关内容",
            data={"query": request.query, "top_k": request.top_k, "results": results},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retrieve failed: {e}", exc_info=True)
        return APIResponse(success=False, error=str(e))


@router.get("/categories", response_model=APIResponse)
async def list_categories(
    api_key_data: Dict = Depends(verify_api_key),
) -> APIResponse:
    """列出知识分类"""
    try:
        pool = await init_db_pool()
        rows = await pool.fetch(
            """
            SELECT category, COUNT(*) as count
            FROM documents
            GROUP BY category
            ORDER BY count DESC
            """
        )
        categories = {r["category"]: {"count": r["count"]} for r in rows}

        return APIResponse(
            success=True,
            data={"categories": categories, "total": len(categories)},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Categories failed: {e}", exc_info=True)
        return APIResponse(success=False, error=str(e))


@router.get("/stats", response_model=APIResponse)
async def get_statistics(
    api_key_data: Dict = Depends(verify_api_key),
) -> APIResponse:
    """获取系统统计"""
    try:
        if "analyze" not in api_key_data["permissions"]:
            raise HTTPException(status_code=403, detail="权限不足")

        pool = await init_db_pool()
        total = await pool.fetchval("SELECT COUNT(*) FROM documents")

        return APIResponse(
            success=True,
            data={
                "total_documents": total,
                "last_updated": datetime.now().isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stats failed: {e}", exc_info=True)
        return APIResponse(success=False, error=str(e))


@router.post("/analyze", response_model=APIResponse)
async def analyze_text(
    request: AnalyzeRequest,
    api_key_data: Dict = Depends(verify_api_key),
) -> APIResponse:
    """分析文本"""
    try:
        if "analyze" not in api_key_data["permissions"]:
            raise HTTPException(status_code=403, detail="权限不足")

        result: Dict[str, Any] = {}
        if request.analysis_type == "sentiment":
            result = _analyze_sentiment(request.text)
        elif request.analysis_type == "keywords":
            result = _analyze_keywords(request.text)
        elif request.analysis_type == "summary":
            result = _analyze_summary(request.text)
        elif request.analysis_type == "category":
            pool = await init_db_pool()
            result = await _analyze_category(request.text, pool)
        else:
            raise HTTPException(
                status_code=400, detail=f"不支持的分析类型: {request.analysis_type}"
            )

        return APIResponse(success=True, data=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analyze failed: {e}", exc_info=True)
        return APIResponse(success=False, error=str(e))


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查（无需认证）"""
    return {
        "status": "healthy",
        "service": "Lingzhi External API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }


# ==================== 辅助函数 ====================


def _apply_filters(results: List[Dict], filters: Dict) -> List[Dict]:
    """应用过滤条件"""
    filtered = results
    if "category" in filters:
        filtered = [r for r in filtered if r.get("category") == filters["category"]]
    if "min_score" in filters:
        filtered = [r for r in filtered if r.get("score", 0) >= filters["min_score"]]
    return filtered


def _analyze_keywords(text: str) -> Dict[str, Any]:
    """Extract keywords using jieba TF-IDF"""
    keywords = jieba.analyse.extract_tags(text, topK=10, withWeight=True)
    return {
        "keywords": [kw for kw, _ in keywords],
        "keyword_weights": {kw: round(w, 4) for kw, w in keywords},
    }


def _analyze_summary(text: str) -> Dict[str, Any]:
    """Generate extractive summary from text"""
    sentences = re.split(r"[。！？\n]", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if not sentences:
        return {"summary": text[:200], "method": "truncation"}
    scored = []
    for sent in sentences:
        kw = jieba.analyse.extract_tags(sent, topK=5)
        scored.append((len(kw), len(sent), sent))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    top = [s for _, _, s in scored[:3]]
    summary = "。".join(top) + "。"
    if len(summary) > 500:
        summary = text[:200]
        method = "truncation"
    else:
        method = "extractive"
    return {"summary": summary, "method": method}


def _analyze_sentiment(text: str) -> Dict[str, Any]:
    """Rule-based Chinese sentiment analysis"""
    positive_words = [
        "好",
        "优秀",
        "喜欢",
        "棒",
        "赞",
        "健康",
        "进步",
        "和谐",
        "舒适",
        "愉悦",
        "提升",
        "改善",
        "积极",
        "正面",
        "美好",
        "成功",
        "温暖",
        "平静",
        "舒适",
    ]
    negative_words = [
        "差",
        "坏",
        "讨厌",
        "痛",
        "紧张",
        "焦虑",
        "困难",
        "问题",
        "负面",
        "失败",
        "不适",
        "担心",
        "烦躁",
        "消极",
        "痛苦",
        "疲劳",
        "困扰",
        "障碍",
    ]
    pos_count = sum(1 for w in positive_words if w in text)
    neg_count = sum(1 for w in negative_words if w in text)
    total = pos_count + neg_count
    if total == 0:
        sentiment, confidence = "neutral", 0.5
    elif pos_count > neg_count:
        sentiment, confidence = "positive", pos_count / total
    elif neg_count > pos_count:
        sentiment, confidence = "negative", neg_count / total
    else:
        sentiment, confidence = "neutral", 0.5
    return {
        "sentiment": sentiment,
        "confidence": round(confidence, 2),
        "positive_signals": pos_count,
        "negative_signals": neg_count,
    }


async def _analyze_category(text: str, pool) -> Dict[str, Any]:
    """Classify text by matching against document categories in DB"""
    categories = ["气功", "中医", "儒家"]
    best_cat, best_score = "通用", 0.0
    keywords = jieba.analyse.extract_tags(text, topK=20)
    for cat in categories:
        rows = await pool.fetch("SELECT title FROM documents WHERE category = $1 LIMIT 50", cat)
        cat_text = " ".join(r["title"] or "" for r in rows)
        cat_kws = set(jieba.analyse.extract_tags(cat_text, topK=50))
        overlap = len(set(keywords) & cat_kws)
        score = overlap / max(len(keywords), 1)
        if score > best_score:
            best_score, best_cat = score, cat
    return {"category": best_cat, "confidence": round(best_score, 2)}
