"""网关API路由"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from backend.cache.decorators import cached_api_domain_stats
from backend.common.typing import JSONResponse
from backend.domains import get_registry
from backend.gateway import APIGateway, InMemoryRateLimiter
from backend.monitoring import get_metrics_collector
from backend.monitoring.prometheus import PrometheusExporter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["gateway"])

# P5组件实例
_domain_gateway: Optional[APIGateway] = None
_rate_limiter: Optional[InMemoryRateLimiter] = None


# ========== 辅助函数 ==========


async def get_domain_gateway() -> APIGateway:
    """获取领域网关实例"""
    global _domain_gateway
    if _domain_gateway is None:
        registry = get_registry()
        _domain_gateway = APIGateway(registry)
    return _domain_gateway


async def get_rate_limiter() -> InMemoryRateLimiter:
    """获取速率限制器实例"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = InMemoryRateLimiter()
    return _rate_limiter


# ========== 数据模型 ==========


class GatewayQueryRequest(BaseModel):
    """网关查询请求"""

    question: str = Field(..., min_length=1, max_length=500, description="用户问题")
    session_id: Optional[str] = Field(None, description="会话ID")
    multi_domain: bool = Field(False, description="是否查询多个领域")


class DomainQueryRequest(BaseModel):
    """领域查询请求"""

    question: str = Field(..., min_length=1, max_length=500)


# ========== 路由 ==========


@router.post("/gateway/query", response_model=JSONResponse)
async def gateway_query(request: GatewayQueryRequest) -> JSONResponse:
    """
    网关统一查询API

    自动路由到合适的领域进行查询

    Args:
        request: 查询请求

    Returns:
        查询结果
    """
    metrics = get_metrics_collector()
    metrics.increment_counter("gateway_query_total")

    # 速率限制
    rate_limiter = await get_rate_limiter()
    client_ip = "default"  # 实际应用中应从请求中获取
    allowed, limit_info = await rate_limiter.check(client_ip)

    if not allowed:
        metrics.increment_counter("gateway_rate_limited")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "retry_after": limit_info.get("retry_after", 60),
            },
        )

    # 路由查询
    gateway = await get_domain_gateway()

    try:
        if request.multi_domain:
            results = await gateway.route_multi(request.question)
            return {
                "question": request.question,
                "domain": "multi",
                "results": [r.to_dict() for r in results],
                "session_id": request.session_id or datetime.now().strftime("%Y%m%d%H%M%S"),
            }
        else:
            routing_result = await gateway.route(request.question)
            query_result = await routing_result.handler(request.question)
            metrics.increment_counter("gateway_query_success")
            return {
                "question": request.question,
                "domain": routing_result.domain,
                "strategy": routing_result.strategy,
                "result": query_result.to_dict(),
                "session_id": request.session_id or datetime.now().strftime("%Y%m%d%H%M%S"),
            }
    except Exception as e:
        metrics.increment_counter("gateway_query_error")
        logger.error(f"网关查询失败: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/domains", response_model=JSONResponse)
async def list_domains() -> JSONResponse:
    """获取所有领域列表"""
    try:
        registry = get_registry()
        health_report = await registry.health_check()

        return {
            "domains": health_report["domains"],
            "total": health_report["total_domains"],
            "enabled": health_report["enabled_domains"],
        }
    except Exception as e:
        logger.error(f"获取领域列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取领域列表失败: {e}")


@router.get("/domains/{domain_name}/stats", response_model=JSONResponse)
@cached_api_domain_stats(ttl=600)
async def get_domain_stats(domain_name: str) -> JSONResponse:
    """获取领域统计信息（缓存10分钟）"""
    try:
        registry = get_registry()
        domain = registry.get(domain_name)

        if not domain:
            raise HTTPException(status_code=404, detail=f"领域 {domain_name} 不存在")

        stats = domain.get_stats()
        health = await domain.health_check()

        return {
            "name": domain_name,
            "type": domain.domain_type.value,
            "enabled": domain.enabled,
            "priority": domain.priority,
            "stats": {
                "document_count": stats.document_count,
                "query_count": stats.query_count,
                "avg_response_time": stats.avg_response_time,
                "cache_hit_rate": stats.cache_hit_rate,
            },
            "health": health,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取领域统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取领域统计失败: {e}")


@router.post("/domains/{domain_name}/query", response_model=JSONResponse)
async def domain_query(domain_name: str, request: DomainQueryRequest) -> JSONResponse:
    """直接向指定领域查询"""
    try:
        registry = get_registry()
        domain = registry.get(domain_name)

        if not domain:
            raise HTTPException(status_code=404, detail=f"领域 {domain_name} 不存在")

        if not domain.enabled:
            raise HTTPException(status_code=400, detail=f"领域 {domain_name} 未启用")

        result = await domain.query(request.question)
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"领域查询失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"领域查询失败: {e}")


@router.get("/metrics", response_model=JSONResponse)
async def get_metrics() -> JSONResponse:
    """获取系统指标"""
    try:
        metrics = get_metrics_collector()
        all_metrics = metrics.get_all_metrics()

        gateway = await get_domain_gateway()
        gateway_metrics = gateway.get_metrics()

        return {
            "metrics": all_metrics,
            "gateway": gateway_metrics,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"获取指标失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取指标失败: {e}")


@router.get("/metrics/prometheus", response_class=Response)
async def get_prometheus_metrics() -> Response:
    """获取Prometheus格式的指标"""
    try:
        exporter = PrometheusExporter()
        prometheus_text = exporter.export()

        return Response(
            content=prometheus_text,
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=metrics.txt"},
        )
    except Exception as e:
        logger.error(f"获取Prometheus指标失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取Prometheus指标失败: {e}")


@router.get("/gateway/stats", response_model=JSONResponse)
async def gateway_stats() -> JSONResponse:
    """获取网关统计信息"""
    try:
        gateway = await get_domain_gateway()
        return gateway.get_metrics()
    except Exception as e:
        logger.error(f"获取网关统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取网关统计失败: {e}")
