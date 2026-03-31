"""书籍相关的Pydantic Schema

定义请求和响应的数据模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class BookBase(BaseModel):
    """书籍基础模型"""
    title: str = Field(..., description="书籍标题")
    author: Optional[str] = Field(None, description="作者")
    category: Optional[str] = Field(None, description="分类（气功/中医/儒家）")
    dynasty: Optional[str] = Field(None, description="朝代")
    year: Optional[str] = Field(None, description="年代")
    description: Optional[str] = Field(None, description="简介")


class BookResponse(BookBase):
    """书籍响应模型"""
    id: int
    title: str
    author: Optional[str]
    category: Optional[str]
    dynasty: Optional[str]
    year: Optional[str]
    language: str
    description: Optional[str]
    has_content: bool
    total_pages: int
    total_chars: int
    view_count: int
    source_id: Optional[int]
    created_at: Optional[str]

    model_config = {"from_attributes": True}


class BookDetailResponse(BookResponse):
    """书籍详情响应模型"""
    chapters: List[dict] = Field(default_factory=list, description="章节列表")


class BookListItem(BaseModel):
    """书籍列表项"""
    id: int
    title: str
    author: Optional[str]
    category: Optional[str]
    dynasty: Optional[str]
    description: Optional[str]
    has_content: bool
    view_count: int


class BookSearchResult(BaseModel):
    """搜索结果"""
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    size: int = Field(..., description="每页数量")
    results: List[BookListItem] = Field(..., description="结果列表")


class ContentSearchResult(BaseModel):
    """全文搜索结果"""
    id: int
    book_id: int
    book_title: str
    chapter_num: int
    title: Optional[str]
    preview: str = Field(..., description="内容预览（带高亮）")
    char_count: int


class ContentSearchResponse(BaseModel):
    """全文搜索响应"""
    total: int
    page: int
    size: int
    results: List[ContentSearchResult]


class SimilarBookResponse(BaseModel):
    """相似书籍响应"""
    id: int
    title: str
    author: Optional[str]
    category: Optional[str]
    dynasty: Optional[str]
    similarity: float = Field(..., description="相似度（0-1）")


class ChapterResponse(BaseModel):
    """章节响应"""
    id: int
    book_id: int
    chapter_num: int
    title: Optional[str]
    content: Optional[str]
    char_count: int


class DataSourceResponse(BaseModel):
    """数据源响应"""
    id: int
    code: str
    name_zh: str
    name_en: Optional[str]
    description: Optional[str]
    category: Optional[str]
    supports_search: bool
    supports_fulltext: bool
    is_active: bool


class FiltersResponse(BaseModel):
    """筛选选项响应"""
    categories: List[str]
    dynasties: List[str]
    languages: List[str]
    sources: List[DataSourceResponse]
