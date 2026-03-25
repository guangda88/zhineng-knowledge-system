"""领域注册表

管理所有已注册的领域，提供服务发现和路由功能
"""

import logging
from typing import Dict, List, Optional, Any

from .base import BaseDomain, DomainType, QueryResult

logger = logging.getLogger(__name__)


class DomainRegistry:
    """领域注册表

    管理所有领域实例，提供服务发现和路由
    """

    def __init__(self):
        """初始化注册表"""
        self._domains: Dict[str, BaseDomain] = {}
        self._initialized = False

    def register(self, domain: BaseDomain) -> None:
        """注册领域

        Args:
            domain: 领域实例
        """
        if domain.name in self._domains:
            logger.warning(f"领域 {domain.name} 已存在，将被覆盖")

        self._domains[domain.name] = domain
        logger.info(f"注册领域: {domain.name} ({domain.domain_type.value})")

    def unregister(self, domain_name: str) -> None:
        """注销领域

        Args:
            domain_name: 领域名称
        """
        if domain_name in self._domains:
            del self._domains[domain_name]
            logger.info(f"注销领域: {domain_name}")

    def get(self, domain_name: str) -> Optional[BaseDomain]:
        """获取领域实例

        Args:
            domain_name: 领域名称

        Returns:
            领域实例，如果不存在返回None
        """
        return self._domains.get(domain_name)

    def get_all(self) -> Dict[str, BaseDomain]:
        """获取所有领域"""
        return self._domains.copy()

    def get_enabled(self) -> List[BaseDomain]:
        """获取所有已启用的领域

        按优先级排序
        """
        enabled = [d for d in self._domains.values() if d.enabled]
        return sorted(enabled, key=lambda x: -x.priority)

    def get_by_type(self, domain_type: DomainType) -> List[BaseDomain]:
        """根据类型获取领域

        Args:
            domain_type: 领域类型

        Returns:
            该类型的所有领域
        """
        return [
            d for d in self._domains.values()
            if d.domain_type == domain_type
        ]

    async def route(
        self,
        question: str,
        context: Optional[str] = None,
        **kwargs
    ) -> QueryResult:
        """智能路由到最适合的领域

        Args:
            question: 用户问题
            context: 额外上下文
            **kwargs: 其他参数

        Returns:
            查询结果
        """
        # 计算每个领域的匹配分数
        scored_domains = []
        for domain in self.get_enabled():
            score = domain.matches_question(question)
            if score > 0:
                scored_domains.append((domain, score))

        # 按分数和优先级排序
        scored_domains.sort(
            key=lambda x: (x[1], x[0].priority),
            reverse=True
        )

        if not scored_domains:
            # 使用通用领域作为兜底
            general_domain = self.get("general")
            if general_domain:
                return await general_domain.query(question, context, **kwargs)
            else:
                return QueryResult(
                    content="没有可用的领域来处理此问题。",
                    confidence=0.0
                )

        # 使用匹配度最高的领域
        best_domain, _ = scored_domains[0]
        logger.info(f"路由问题到领域: {best_domain.name}")

        return await best_domain.query(question, context, **kwargs)

    async def multi_domain_query(
        self,
        question: str,
        domains: Optional[List[str]] = None,
        merge_results: bool = True,
        **kwargs
    ) -> List[QueryResult]:
        """多领域查询

        Args:
            question: 用户问题
            domains: 指定领域列表，None表示所有启用领域
            merge_results: 是否合并结果
            **kwargs: 其他参数

        Returns:
            查询结果列表
        """
        if domains:
            target_domains = [
                self.get(name) for name in domains
                if self.get(name) and self.get(name).enabled
            ]
        else:
            target_domains = self.get_enabled()

        results = []
        for domain in target_domains:
            try:
                result = await domain.query(question, **kwargs)
                if result.confidence > 0.3:  # 只保留置信度较高的结果
                    results.append(result)
            except Exception as e:
                logger.error(f"领域 {domain.name} 查询失败: {e}")

        # 按置信度排序
        results.sort(key=lambda x: x.confidence, reverse=True)

        return results

    async def initialize_all(self) -> None:
        """初始化所有已注册的领域"""
        if self._initialized:
            return

        logger.info("初始化所有领域...")
        for domain in self._domains.values():
            try:
                await domain.initialize()
            except Exception as e:
                logger.error(f"领域 {domain.name} 初始化失败: {e}")

        self._initialized = True
        logger.info(f"领域初始化完成，共 {len(self._domains)} 个领域")

    async def shutdown_all(self) -> None:
        """关闭所有领域"""
        logger.info("关闭所有领域...")
        for domain in self._domains.values():
            try:
                await domain.shutdown()
            except Exception as e:
                logger.error(f"领域 {domain.name} 关闭失败: {e}")

        self._initialized = False

    async def health_check(self) -> Dict[str, Any]:
        """检查所有领域健康状态

        Returns:
            健康状态报告
        """
        health_report = {
            "total_domains": len(self._domains),
            "enabled_domains": len(self.get_enabled()),
            "domains": []
        }

        for domain in self._domains.values():
            try:
                health = await domain.health_check()
                health_report["domains"].append(health)
            except Exception as e:
                health_report["domains"].append({
                    "domain": domain.name,
                    "status": "error",
                    "error": str(e)
                })

        return health_report

    def get_stats(self) -> Dict[str, Any]:
        """获取所有领域统计"""
        stats = {
            "total_queries": 0,
            "domains": {}
        }

        for domain in self._domains.values():
            domain_stats = domain.get_stats()
            stats["domains"][domain.name] = {
                "document_count": domain_stats.document_count,
                "query_count": domain_stats.query_count,
                "avg_response_time": domain_stats.avg_response_time
            }
            stats["total_queries"] += domain_stats.query_count

        return stats


# 全局注册表实例
_global_registry: Optional[DomainRegistry] = None


def get_registry() -> DomainRegistry:
    """获取全局注册表实例

    Returns:
        领域注册表
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = DomainRegistry()
    return _global_registry


async def setup_domains(db_pool=None) -> DomainRegistry:
    """设置并初始化所有领域

    Args:
        db_pool: 数据库连接池

    Returns:
        初始化后的注册表
    """
    from .qigong import QigongDomain
    from .tcm import TcmDomain
    from .confucian import ConfucianDomain
    from .general import GeneralDomain

    registry = get_registry()

    # 注册所有领域
    registry.register(QigongDomain(db_pool))
    registry.register(TcmDomain(db_pool))
    registry.register(ConfucianDomain(db_pool))
    registry.register(GeneralDomain(db_pool))

    # 初始化所有领域
    await registry.initialize_all()

    return registry
