"""
数据模型模块
遵循开发规则：集中管理数据模型，使用Pydantic进行验证
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ========== 文档模型 ==========

class DocumentBase(BaseModel):
    """文档基础模型"""
    title: str = Field(..., min_length=1, max_length=500, description="文档标题")
    content: str = Field(..., min_length=1, description="文档内容")
    category: str = Field(..., pattern="^(气功|中医|儒家)$", description="文档分类")
    tags: List[str] = Field(default_factory=list, description="文档标签")


class DocumentCreate(DocumentBase):
    """创建文档请求模型"""
    pass


class DocumentUpdate(BaseModel):
    """更新文档请求模型"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = Field(None, pattern="^(气功|中医|儒家)$")
    tags: Optional[List[str]] = None


class DocumentResponse(DocumentBase):
    """文档响应模型"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 搜索模型 ==========

class SearchRequest(BaseModel):
    """搜索请求模型"""
    query: str = Field(..., min_length=1, max_length=200, description="搜索关键词")
    category: Optional[str] = Field(None, pattern="^(气功|中医|儒家)$")
    limit: int = Field(10, ge=1, le=100)


class SearchResult(BaseModel):
    """搜索结果模型"""
    id: int
    title: str
    content: str
    category: str
    score: Optional[float] = None
    similarity: Optional[float] = None
    method: str = "keyword"


# ========== 聊天模型 ==========

class ChatRequest(BaseModel):
    """聊天请求模型"""
    question: str = Field(..., min_length=1, max_length=1000, description="用户问题")
    category: Optional[str] = Field(None, pattern="^(气功|中医|儒家)$")
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应模型"""
    answer: str
    sources: List[Dict[str, Any]]
    session_id: str


# ========== 混合检索模型 ==========

class HybridSearchRequest(BaseModel):
    """混合搜索请求模型"""
    query: str = Field(..., min_length=1, max_length=200)
    category: Optional[str] = Field(None, pattern="^(气功|中医|儒家)$")
    top_k: int = Field(10, ge=1, le=50)
    use_vector: bool = Field(True, description="是否使用向量检索")
    use_bm25: bool = Field(True, description="是否使用BM25检索")


class HybridSearchResponse(BaseModel):
    """混合搜索响应模型"""
    query: str
    total: int
    results: List[SearchResult]


# ========== 嵌入模型 ==========

class EmbeddingUpdateRequest(BaseModel):
    """嵌入更新请求模型"""
    doc_ids: Optional[List[int]] = None
    all_docs: bool = False


class EmbeddingUpdateResponse(BaseModel):
    """嵌入更新响应模型"""
    status: str
    message: str
    updated: Optional[int] = None
    stats: Optional[Dict[str, int]] = None
