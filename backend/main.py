"""智能知识系统 - FastAPI 主入口（安全加固版）

重构后版本 - 简洁入口文件
- FastAPI应用初始化
- 中间件配置（包含安全加固）
- 路由注册
- 生命周期管理
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.api.v1 import api_router
from backend.api.v2 import api_router_v2
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


def create_app() -> FastAPI:
    """创建并配置FastAPI应用"""
    app = FastAPI(
        title="智能知识系统 API",
        description="基于 RAG 的儒释道医武哲科气心理九大领域知识问答系统",
        version="1.0.0",
        lifespan=lifespan,
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

    # 请求日志中间件
    app.middleware("http")(log_requests)

    # GZip 压缩中间件 - 仅压缩大于1000字节的响应
    app.add_middleware(GZipMiddleware, minimum_size=1000)

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
