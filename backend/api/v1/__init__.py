"""API v1 路由模块"""

from fastapi import APIRouter

from . import documents, gateway, health, reasoning, search, textbook_processing, books, learning, generation, external, annotation, optimization

# 创建统一路由器
api_router = APIRouter()

# 注册各模块路由
api_router.include_router(documents.router)
api_router.include_router(search.router)
api_router.include_router(search.extra_router)  # 添加额外路由（ask, categories, stats）
api_router.include_router(reasoning.router)
api_router.include_router(gateway.router)
api_router.include_router(textbook_processing.router)
api_router.include_router(books.router)  # 添加书籍搜索路由（prefix已在router中定义）
api_router.include_router(learning.router)  # 添加自学习和进化路由
api_router.include_router(generation.router)  # 添加内容生成路由
api_router.include_router(external.router)  # 添加外部API路由
api_router.include_router(annotation.router)  # 添加标注系统路由
api_router.include_router(optimization.router)  # 添加自优化系统路由

# 健康检查路由不使用prefix
api_router.include_router(health.router)

__all__ = ["api_router"]
