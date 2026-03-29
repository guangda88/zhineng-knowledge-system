"""API v1 路由模块"""

from fastapi import APIRouter

from . import documents, gateway, health, reasoning, search, textbook_processing

# 创建统一路由器
api_router = APIRouter()

# 注册各模块路由
api_router.include_router(documents.router)
api_router.include_router(search.router)
api_router.include_router(search.extra_router)  # 添加额外路由（ask, categories, stats）
api_router.include_router(reasoning.router)
api_router.include_router(gateway.router)
api_router.include_router(textbook_processing.router)

# 健康检查路由不使用prefix
api_router.include_router(health.router)

__all__ = ["api_router"]
