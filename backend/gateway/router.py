"""API路由器

实现请求路由、负载均衡和服务发现
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from backend.domains import DomainRegistry, get_registry

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """路由策略"""

    PRIORITY = "priority"  # 按优先级
    ROUND_ROBIN = "round_robin"  # 轮询
    LEAST_CONNECTIONS = "least_connections"  # 最少连接
    DOMAIN_MATCH = "domain_match"  # 领域匹配


@dataclass
class ServiceEndpoint:
    """服务端点"""

    name: str
    url: str
    health: bool = True
    connections: int = 0
    response_time: float = 0.0
    error_count: int = 0
    last_check: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "health": self.health,
            "connections": self.connections,
            "response_time": self.response_time,
            "error_count": self.error_count,
        }


@dataclass
class RoutingResult:
    """路由结果"""

    domain: str
    handler: Callable
    endpoint: Optional[ServiceEndpoint] = None
    strategy: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "endpoint": self.endpoint.to_dict() if self.endpoint else None,
            "strategy": self.strategy,
        }


class APIGateway:
    """API网关

    提供统一的路由、负载均衡和服务发现
    """

    def __init__(self, domain_registry: Optional[DomainRegistry] = None):
        """初始化网关

        Args:
            domain_registry: 领域注册表
        """
        self._registry = domain_registry or get_registry()
        self._strategy = RoutingStrategy.DOMAIN_MATCH
        self._endpoints: Dict[str, List[ServiceEndpoint]] = defaultdict(list)
        self._metrics: Dict[str, Any] = defaultdict(int)

        # 领域关键词（用于路由决策）
        self._domain_keywords = {
            "qigong": ["气功", "八段锦", "五禽戏", "太极拳", "功法", "养生", "呼吸"],
            "tcm": ["中医", "中药", "针灸", "经络", "穴位", "方剂", "辨证"],
            "confucian": ["儒家", "孔子", "论语", "孟子", "仁义", "礼智"],
            "general": [],  # 默认
        }

    def add_endpoint(self, domain: str, endpoint: ServiceEndpoint) -> None:
        """添加服务端点

        Args:
            domain: 领域名称
            endpoint: 服务端点
        """
        self._endpoints[domain].append(endpoint)
        logger.info(f"添加端点: {domain} -> {endpoint.url}")

    def remove_endpoint(self, domain: str, url: str) -> None:
        """移除服务端点

        Args:
            domain: 领域名称
            url: 端点URL
        """
        self._endpoints[domain] = [ep for ep in self._endpoints[domain] if ep.url != url]

    def set_routing_strategy(self, strategy: RoutingStrategy) -> None:
        """设置路由策略

        Args:
            strategy: 路由策略
        """
        self._strategy = strategy
        logger.info(f"路由策略设置为: {strategy.value}")

    def detect_domain(self, question: str) -> str:
        """检测问题所属领域

        Args:
            question: 用户问题

        Returns:
            领域名称
        """
        question_lower = question.lower()

        # 计算每个领域的匹配分数
        scores = {}
        for domain, keywords in self._domain_keywords.items():
            score = sum(1 for kw in keywords if kw.lower() in question_lower)
            if score > 0:
                scores[domain] = score

        if not scores:
            return "general"  # 默认通用领域

        # 返回分数最高的领域
        return max(scores.items(), key=lambda x: x[1])[0]

    async def route(self, question: str, context: Optional[str] = None, **kwargs) -> RoutingResult:
        """路由请求到合适的领域

        Args:
            question: 用户问题
            context: 额外上下文
            **kwargs: 其他参数

        Returns:
            路由结果
        """
        start_time = time.time()

        # 检测领域
        domain = self.detect_domain(question)
        self._metrics[f"domain_{domain}"] += 1

        # 获取领域处理器
        domain_instance = self._registry.get(domain)
        if not domain_instance or not domain_instance.enabled:
            # 降级到通用领域
            domain = "general"
            domain_instance = self._registry.get(domain)

        if not domain_instance:
            raise RuntimeError(f"没有可用的领域处理器: {domain}")

        # 选择端点（如果有多个）
        endpoint = self._select_endpoint(domain)

        # 更新连接数
        if endpoint:
            endpoint.connections += 1

        # 记录路由时间
        routing_time = time.time() - start_time
        self._metrics["routing_time"] += routing_time

        return RoutingResult(
            domain=domain,
            handler=domain_instance.query,
            endpoint=endpoint,
            strategy=self._strategy.value,
        )

    def _select_endpoint(self, domain: str) -> Optional[ServiceEndpoint]:
        """选择服务端点

        Args:
            domain: 领域名称

        Returns:
            选中的端点
        """
        endpoints = self._endpoints.get(domain, [])
        if not endpoints:
            return None

        # 过滤健康的端点
        healthy_endpoints = [ep for ep in endpoints if ep.health]
        if not healthy_endpoints:
            return None

        if self._strategy == RoutingStrategy.LEAST_CONNECTIONS:
            # 选择连接数最少的
            return min(healthy_endpoints, key=lambda ep: ep.connections)
        elif self._strategy == RoutingStrategy.ROUND_ROBIN:
            # 简单轮询
            return healthy_endpoints[self._metrics["round_robin_index"] % len(healthy_endpoints)]
        else:
            # 默认第一个
            return healthy_endpoints[0]

    async def route_multi(
        self, question: str, domains: Optional[List[str]] = None, **kwargs
    ) -> List[Any]:
        """多领域路由

        Args:
            question: 用户问题
            domains: 指定领域列表
            **kwargs: 其他参数

        Returns:
            所有领域的结果
        """
        if domains:
            target_domains = [
                self._registry.get(name) for name in domains if self._registry.get(name)
            ]
        else:
            # 获取所有启用的领域
            target_domains = self._registry.get_enabled()

        results = []
        for domain in target_domains:
            try:
                result = await domain.query(question, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"领域 {domain.name} 查询失败: {e}")

        return results

    def get_metrics(self) -> Dict[str, Any]:
        """获取网关指标

        Returns:
            指标数据
        """
        return {
            "strategy": self._strategy.value,
            "total_requests": sum(v for k, v in self._metrics.items() if k.startswith("domain_")),
            "domain_distribution": {
                k: v for k, v in self._metrics.items() if k.startswith("domain_")
            },
            "endpoints": {
                domain: [ep.to_dict() for ep in eps] for domain, eps in self._endpoints.items()
            },
            "avg_routing_time": self._metrics.get("routing_time", 0)
            / max(sum(v for k, v in self._metrics.items() if k.startswith("domain_")), 1),
        }

    async def health_check(self) -> Dict[str, Any]:
        """网关健康检查

        Returns:
            健康状态
        """
        domain_health = await self._registry.health_check()

        return {
            "status": "healthy",
            "strategy": self._strategy.value,
            "domains": domain_health,
            "endpoints_count": sum(len(eps) for eps in self._endpoints.values()),
        }

    def reset_metrics(self) -> None:
        """重置指标"""
        self._metrics.clear()
        logger.info("网关指标已重置")
