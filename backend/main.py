"""智能知识系统 - FastAPI 主入口（安全加固版）

重构后版本 - 简洁入口文件
- FastAPI应用初始化
- 中间件配置（包含安全加固）
- 路由注册
- 生命周期管理

性能说明: GZip 压缩由 Nginx 统一处理，此处不再重复启用。
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1 import api_router
from backend.api.v2 import api_router_v2
from backend.auth.middleware import AuthConfig, AuthMiddleware
from backend.core import (
    get_allowed_origins,
    log_requests,
)
from backend.core.lifespan import lifespan
from backend.middleware import RateLimitMiddleware
from backend.middleware.security_headers import SecurityHeadersMiddleware

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app(lifespan_ctx=None) -> FastAPI:
    """创建并配置FastAPI应用"""
    _lifespan = lifespan_ctx or lifespan
    app = FastAPI(
        title="智能知识系统 API",
        description="基于 RAG 的儒释道医武哲科气心理九大领域知识问答系统",
        version="1.0.0",
        lifespan=_lifespan,
    )

    # 设置应用状态
    app.state.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    # CORS 中间件配置（安全加固版）
    allowed_origins = get_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    )

    # 安全响应头中间件（新增）
    app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=True)

    # 认证中间件（测试环境在中间件内部自动跳过）
    auth_config = AuthConfig(
        protected_path_prefixes={
            "/api",
            "/api/v1",
            "/api/v2",
        },
        public_paths={
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        },
        public_path_prefixes={
            "/static",
            "/favicon",
            "/api/v1/health",
            "/api/v1/search",
            "/api/v1/categories",
            "/api/v1/stats",
            "/api/v1/ask",
            "/api/v1/feedback",
            "/api/v1/knowledge-gaps",
            "/api/v1/retrieval",
            "/api/v1/documents",
            "/api/v1/reason",
            "/api/v1/reasoning",
            "/api/v1/graph",
            "/api/v1/guoxue",
            "/api/v1/sysbooks",
            "/api/v1/discuss",
            "/api/v1/lingmessage",
            "/api/v2/library",
        },
    )
    app.add_middleware(AuthMiddleware, config=auth_config)

    # 请求日志中间件
    app.middleware("http")(log_requests)

    # GZip 由 Nginx 统一处理，此处不再重复压缩

    # API限流中间件（已配置）
    app.add_middleware(RateLimitMiddleware)

    # 注册API路由
    app.include_router(api_router)
    app.include_router(api_router_v2)  # 添加v2路由（书籍搜索）

    logger.info("FastAPI application initialized with security enhancements")
    logger.info(f"CORS allowed origins: {allowed_origins}")

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    # nosec: B104 - 绑定0.0.0.0用于Docker容器环境，生产环境通过环境变量配置
    uvicorn.run(app, host="0.0.0.0", port=8000)
