"""API v2 路由模块

包含新的书籍搜索功能
"""
from fastapi import APIRouter

from backend.api.v1 import books

# 创建v2路由器
api_router_v2 = APIRouter(prefix="/api/v2", tags=["v2"])

# 注册v2模块路由（复用v1 books router，无代码重复）
api_router_v2.include_router(books.router)

__all__ = ["api_router_v2"]
