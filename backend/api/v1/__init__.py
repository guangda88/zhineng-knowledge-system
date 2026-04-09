"""API v1 路由模块"""

from fastapi import APIRouter

from . import (
    analytics,
    annotation,
    audio,
    books,
    context,
    documents,
    evolution,
    external,
    feedback,
    gateway,
    generation,
    guoxue,
    health,
    intelligence,
    knowledge_gaps,
    learning,
    lifecycle,
    lingmessage,
    optimization,
    pipeline,
    reasoning,
    search,
    staging,
    sysbooks,
    textbook_processing,
    user_profiles,
)

# 创建统一路由器
api_router = APIRouter()

# 注册各模块路由
api_router.include_router(analytics.router)  # 添加用户价值分析路由
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
api_router.include_router(audio.router)
api_router.include_router(lifecycle.router)  # 添加音频处理路由
api_router.include_router(evolution.router)  # 添加自学习进化路由
api_router.include_router(intelligence.router)  # 情报系统路由
api_router.include_router(context.router)  # 添加上下文管理路由
api_router.include_router(sysbooks.router)  # 书目检索（sys_books 302万条）
api_router.include_router(pipeline.router)  # Phase 2/3 管道（提取、标注、知识图谱）
api_router.include_router(guoxue.router)  # 国学经典（guoxue_content 26万条）
api_router.include_router(lingmessage.router)  # 灵信通信系统（灵字辈跨项目讨论）
api_router.include_router(knowledge_gaps.router)  # 知识缺口感知
api_router.include_router(staging.router)  # 知识临时区
api_router.include_router(feedback.router)  # 检索反馈闭环
api_router.include_router(user_profiles.router)  # 用户画像与评估系统

# 健康检查路由不使用prefix
api_router.include_router(health.router)

__all__ = ["api_router"]
