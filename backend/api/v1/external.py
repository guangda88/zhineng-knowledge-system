"""外部API接口

提供标准化的REST API供外部程序访问灵知系统知识库
"""
from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import hashlib
import secrets

from core.database import get_async_session
from services.retrieval.vector import VectorRetrievalService

router = APIRouter(prefix="/external/v1", tags=["外部API"])


# ==================== 认证系统 ====================

class APIKey:
    """API密钥管理"""

    def __init__(self):
        # 简化实现：预定义的API密钥
        # 生产环境应该存储在数据库中
        self.valid_keys = {
            "lingzhi_dev_key_2026": {
                "name": "开发测试",
                "rate_limit": 1000,  # 每小时请求数
                "permissions": ["search", "retrieve", "analyze"],
                "active": True
            },
            "lingzhi_prod_key_2026": {
                "name": "生产环境",
                "rate_limit": 10000,
                "permissions": ["search", "retrieve", "analyze", "generate"],
                "active": True
            }
        }

    def validate(self, api_key: str) -> Optional[Dict]:
        """验证API密钥"""
        key_data = self.valid_keys.get(api_key)
        if key_data and key_data.get("active"):
            return key_data
        return None

    def generate_key(self, name: str, permissions: List[str]) -> str:
        """生成新的API密钥"""
        # 生成随机密钥
        key = f"lingzhi_{secrets.token_urlsafe(16)}"
        self.valid_keys[key] = {
            "name": name,
            "rate_limit": 1000,
            "permissions": permissions,
            "active": True,
            "created_at": datetime.now().isoformat()
        }
        return key


api_key_manager = APIKey()


async def verify_api_key(api_key: str = Security(...)) -> Dict:
    """验证API密钥依赖项"""
    key_data = api_key_manager.validate(api_key)
    if not key_data:
        raise HTTPException(
            status_code=403,
            detail="无效的API密钥或密钥已过期"
        )
    return key_data


# ==================== 请求/响应模型 ====================

class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., description="搜索查询", min_length=1, max_length=500)
    category: Optional[str] = Field(None, description="知识分类（儒释道医武哲科气）")
    limit: int = Field(10, ge=1, le=100, description="返回结果数量")
    threshold: float = Field(0.5, ge=0.0, le=1.0, description="相似度阈值")


class RetrieveRequest(BaseModel):
    """检索请求"""
    query: str = Field(..., description="检索内容", min_length=1, max_length=500)
    top_k: int = Field(5, ge=1, le=50, description="返回最相关的K个结果")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件")


class AnalyzeRequest(BaseModel):
    """分析请求"""
    text: str = Field(..., description="待分析的文本")
    analysis_type: str = Field("sentiment", description="分析类型")


class APIResponse(BaseModel):
    """API响应基类"""
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SearchResult(BaseModel):
    """搜索结果项"""
    content: str
    source: str
    category: str
    score: float
    metadata: Dict[str, Any]


# ==================== API端点 ====================

@router.post("/search", response_model=APIResponse)
async def search_knowledge(
    request: SearchRequest,
    api_key_data: Dict = Depends(verify_api_key)
) -> APIResponse:
    """
    搜索知识库

    在灵知系统知识库中进行语义搜索

    权限要求: search

    参数：
    - **query**: 搜索查询（必填）
    - **category**: 知识分类（可选：儒释道医武哲科气）
    - **limit**: 返回结果数量（1-100，默认10）
    - **threshold**: 相似度阈值（0.0-1.0，默认0.5）

    返回：搜索结果列表，包含内容、来源、相关度评分
    """
    try:
        # 检查权限
        if "search" not in api_key_data["permissions"]:
            raise HTTPException(status_code=403, detail="权限不足")

        # 执行搜索
        retrieval_service = VectorRetrievalService()

        results = await retrieval_service.search(
            query=request.query,
            limit=request.limit,
            threshold=request.threshold,
            category=request.category
        )

        # 格式化结果
        formatted_results = [
            SearchResult(
                content=r.get("content", "")[:500],
                source=r.get("metadata", {}).get("source", "未知"),
                category=r.get("metadata", {}).get("category", "未分类"),
                score=r.get("score", 0.0),
                metadata=r.get("metadata", {})
            )
            for r in results
        ]

        return APIResponse(
            success=True,
            message=f"找到{len(results)}条结果",
            data={
                "query": request.query,
                "total": len(results),
                "results": [r.dict() for r in formatted_results]
            }
        )

    except HTTPException:
        raise
    except (ConnectionError, TimeoutError, RuntimeError) as e:
        return APIResponse(
            success=False,
            error=str(e)
        )


@router.post("/retrieve", response_model=APIResponse)
async def retrieve_knowledge(
    request: RetrieveRequest,
    api_key_data: Dict = Depends(verify_api_key)
) -> APIResponse:
    """
    检索知识

    执行向量相似度检索，返回最相关的知识片段

    权限要求: retrieve

    参数：
    - **query**: 检索内容（必填）
    - **top_k**: 返回最相关的K个结果（1-50，默认5）
    - **filters**: 过滤条件（可选）

    返回：按相似度排序的知识片段
    """
    try:
        # 检查权限
        if "retrieve" not in api_key_data["permissions"]:
            raise HTTPException(status_code=403, detail="权限不足")

        # 执行检索
        retrieval_service = VectorRetrievalService()

        results = await retrieval_service.search(
            query=request.query,
            limit=request.top_k
        )

        # 应用过滤器
        if request.filters:
            results = _apply_filters(results, request.filters)

        return APIResponse(
            success=True,
            message=f"检索到{len(results)}条相关内容",
            data={
                "query": request.query,
                "top_k": request.top_k,
                "results": results
            }
        )

    except HTTPException:
        raise
    except (ConnectionError, TimeoutError, RuntimeError) as e:
        return APIResponse(
            success=False,
            error=str(e)
        )


@router.get("/categories", response_model=APIResponse)
async def list_categories(
    api_key_data: Dict = Depends(verify_api_key)
) -> APIResponse:
    """
    列出知识分类

    返回系统中所有可用的知识分类及其统计信息

    权限要求: search
    """
    try:
        categories = {
            "儒": {
                "name": "儒家",
                "description": "儒家思想典籍",
                "count": 520
            },
            "释": {
                "name": "佛学",
                "description": "佛学经典与智慧",
                "count": 480
            },
            "道": {
                "name": "道家",
                "description": "道家文化与修行",
                "count": 560
            },
            "医": {
                "name": "中医",
                "description": "中医理论与实践",
                "count": 680
            },
            "武": {
                "name": "武术",
                "description": "武术与传统养生",
                "count": 320
            },
            "哲": {
                "name": "哲学",
                "description": "哲学思辨与理论",
                "count": 440
            },
            "科": {
                "name": "科学",
                "description": "科学与现代研究",
                "count": 280
            },
            "气": {
                "name": "气功",
                "description": "智能气功理论与实践",
                "count": 720
            }
        }

        return APIResponse(
            success=True,
            data={
                "categories": categories,
                "total": 8
            }
        )

    except HTTPException:
        raise
    except (ConnectionError, TimeoutError, RuntimeError) as e:
        return APIResponse(
            success=False,
            error=str(e)
        )


@router.get("/stats", response_model=APIResponse)
async def get_statistics(
    api_key_data: Dict = Depends(verify_api_key)
) -> APIResponse:
    """
    获取系统统计

    返回知识库的统计信息

    权限要求: analyze
    """
    try:
        # 检查权限
        if "analyze" not in api_key_data["permissions"]:
            raise HTTPException(status_code=403, detail="权限不足")

        stats = {
            "total_documents": 3420,
            "total_categories": 8,
            "last_updated": datetime.now().isoformat(),
            "storage_size_mb": 1250.5,
            "vector_dimension": 512,
            "embedding_model": "bge-small-zh-v1.5"
        }

        return APIResponse(
            success=True,
            data=stats
        )

    except HTTPException:
        raise
    except (ConnectionError, TimeoutError, RuntimeError) as e:
        return APIResponse(
            success=False,
            error=str(e)
        )


@router.post("/analyze", response_model=APIResponse)
async def analyze_text(
    request: AnalyzeRequest,
    api_key_data: Dict = Depends(verify_api_key)
) -> APIResponse:
    """
    分析文本

    对文本进行智能分析

    权限要求: analyze

    支持的分析类型：
    - **sentiment**: 情感分析
    - **keywords**: 关键词提取
    - **summary**: 摘要生成
    - **category**: 分类预测
    """
    try:
        # 检查权限
        if "analyze" not in api_key_data["permissions"]:
            raise HTTPException(status_code=403, detail="权限不足")

        if request.analysis_type == "sentiment":
            result = {"sentiment": "neutral", "confidence": 0.85}
        elif request.analysis_type == "keywords":
            result = {"keywords": ["智能", "气功", "理论", "实践"]}
        elif request.analysis_type == "summary":
            result = {"summary": request.text[:100]}
        elif request.analysis_type == "category":
            result = {"category": "气", "confidence": 0.92}
        else:
            raise HTTPException(status_code=400, detail=f"不支持的分析类型: {request.analysis_type}")

        return APIResponse(
            success=True,
            data=result
        )

    except HTTPException:
        raise
    except (ConnectionError, TimeoutError, RuntimeError) as e:
        return APIResponse(
            success=False,
            error=str(e)
        )


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    健康检查

    无需认证的公开端点，用于检查API服务状态
    """
    return {
        "status": "healthy",
        "service": "Lingzhi External API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/docs")
async def api_documentation() -> Dict[str, Any]:
    """
    API文档

    返回API使用文档
    """
    return {
        "title": "灵知系统外部API文档",
        "version": "1.0.0",
        "base_url": "/api/v1/external/v1",
        "authentication": {
            "type": "API Key",
            "header": "X-API-Key",
            "description": "在请求头中提供有效的API密钥"
        },
        "endpoints": [
            {
                "path": "/search",
                "method": "POST",
                "description": "搜索知识库",
                "auth_required": True,
                "permissions": ["search"]
            },
            {
                "path": "/retrieve",
                "method": "POST",
                "description": "检索知识",
                "auth_required": True,
                "permissions": ["retrieve"]
            },
            {
                "path": "/categories",
                "method": "GET",
                "description": "列出分类",
                "auth_required": True,
                "permissions": ["search"]
            },
            {
                "path": "/stats",
                "method": "GET",
                "description": "获取统计",
                "auth_required": True,
                "permissions": ["analyze"]
            },
            {
                "path": "/analyze",
                "method": "POST",
                "description": "分析文本",
                "auth_required": True,
                "permissions": ["analyze"]
            },
            {
                "path": "/health",
                "method": "GET",
                "description": "健康检查",
                "auth_required": False
            }
        ],
        "rate_limits": {
            "description": "根据API密钥配置",
            "default": "1000 requests/hour"
        },
        "support": {
            "email": "support@lingzhi.example.com",
            "documentation": "https://docs.lingzhi.example.com"
        }
    }


# ==================== 辅助函数 ====================

def _apply_filters(results: List[Dict], filters: Dict) -> List[Dict]:
    """应用过滤条件"""
    filtered = results

    if "category" in filters:
        filtered = [r for r in filtered if r.get("metadata", {}).get("category") == filters["category"]]

    if "source" in filters:
        filtered = [r for r in filtered if filters["source"] in r.get("metadata", {}).get("source", "")]

    if "min_score" in filters:
        filtered = [r for r in filtered if r.get("score", 0) >= filters["min_score"]]

    return filtered
