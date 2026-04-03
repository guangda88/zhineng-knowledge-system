"""增强型AI服务 - 集成智能重试和熔断器

优化目标：
1. 将API成功率从95%提升到99%
2. 添加智能重试机制（指数退避）
3. 添加熔断器防止级联故障
4. 完善降级策略
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from backend.gateway.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
)
from backend.services.evolution.free_token_pool import TaskType, get_free_token_pool
from backend.services.evolution.resilient_caller import (
    ResilientAICaller,
    RetryableError,
    RetryConfig,
    RetryStrategy,
)

logger = logging.getLogger(__name__)


class EnhancedAIService:
    """增强型AI服务 - 集成重试和熔断器"""

    def __init__(self):
        # 获取底层token池
        self.token_pool = get_free_token_pool()

        # 初始化弹性调用器
        self.resilient_caller = ResilientAICaller()
        self.resilient_caller.retry_config = RetryConfig(
            max_attempts=5,  # 最多5次重试
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            max_delay=60.0,
            retriable_exceptions=(
                ConnectionError,
                TimeoutError,
                asyncio.TimeoutError,
                RetryableError,
            ),
        )

        # 初始化熔断器注册表
        self.circuit_breaker_registry = CircuitBreakerRegistry()

        # 为每个provider创建熔断器
        self._init_circuit_breakers()

        # 统计
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "retried_calls": 0,
            "fallback_calls": 0,
            "circuit_breaker_trips": 0,
            "failed_calls": 0,
        }

    def _init_circuit_breakers(self):
        """为每个provider初始化熔断器"""
        config = CircuitBreakerConfig(
            failure_threshold=5,  # 5次失败后熔断
            success_threshold=2,  # 2次成功后恢复
            timeout=60.0,  # 熔断60秒
            half_open_max_calls=3,
        )

        for provider_name in self.token_pool.providers.keys():
            self.circuit_breaker_registry.get_or_create(f"ai_provider_{provider_name}", config)
            logger.info(f"为 {provider_name} 创建熔断器")

    async def call_with_resilience(
        self, provider_name: str, prompt: str, max_tokens: int = 2000, timeout: float = 30.0
    ) -> Dict[str, Any]:
        """带弹性机制的API调用

        集成：
        1. 熔断器检查
        2. 智能重试
        3. 降级策略
        """
        self.stats["total_calls"] += 1

        # 获取熔断器
        circuit_breaker = self.circuit_breaker_registry.get_or_create(
            f"ai_provider_{provider_name}"
        )

        # 检查熔断器状态
        if circuit_breaker.state.value == "open":
            logger.warning(f"{provider_name} 熔断器开启，尝试降级")
            self.stats["circuit_breaker_trips"] += 1
            return await self._try_fallback_providers(provider_name, prompt, max_tokens, timeout)

        # 使用熔断器进行调用
        try:
            result = await circuit_breaker.call(
                self._call_with_retry, provider_name, prompt, max_tokens, timeout
            )

            self.stats["successful_calls"] += 1
            return result

        except CircuitBreakerOpenError:
            logger.warning(f"{provider_name} 熔断器开启")
            self.stats["circuit_breaker_trips"] += 1
            return await self._try_fallback_providers(provider_name, prompt, max_tokens, timeout)

        except Exception as e:
            logger.error(f"{provider_name} 调用失败: {e}")
            self.stats["failed_calls"] += 1
            return await self._try_fallback_providers(provider_name, prompt, max_tokens, timeout)

    async def _call_with_retry(
        self, provider_name: str, prompt: str, max_tokens: int, timeout: float
    ) -> Dict[str, Any]:
        """带重试的实际调用"""

        last_exception = None
        config = self.resilient_caller.retry_config

        for attempt in range(config.max_attempts):
            try:
                # 调用底层token池
                result = await self.token_pool.call_provider(provider_name, prompt, max_tokens)

                if result.get("success"):
                    if attempt > 0:
                        self.stats["retried_calls"] += 1
                        logger.info(
                            f"{provider_name} 重试成功 "
                            f"(尝试 {attempt + 1}/{config.max_attempts})"
                        )
                    return result
                else:
                    # API返回失败
                    error = result.get("error", "Unknown error")
                    if self._is_retriable_error(error):
                        if attempt < config.max_attempts - 1:
                            delay = self._calc_retry_delay(attempt, config)
                            logger.warning(
                                f"{provider_name} 失败: {error}, " f"{delay:.1f}s后重试..."
                            )
                            await asyncio.sleep(delay)
                            last_exception = Exception(error)
                            continue
                    else:
                        # 不可重试的错误
                        return result

            except (ConnectionError, TimeoutError, asyncio.TimeoutError) as e:
                last_exception = e
                if attempt < config.max_attempts - 1:
                    delay = self._calc_retry_delay(attempt, config)
                    logger.warning(f"{provider_name} 网络错误: {e}, " f"{delay:.1f}s后重试...")
                    await asyncio.sleep(delay)
                else:
                    raise RetryableError(f"{provider_name} 重试耗尽", original_error=e) from e

        # 所有重试都失败
        return {
            "success": False,
            "error": f"重试{config.max_attempts}次后仍失败: {last_exception}",
            "provider": provider_name,
        }

    async def _try_fallback_providers(
        self, failed_provider: str, prompt: str, max_tokens: int, timeout: float
    ) -> Dict[str, Any]:
        """尝试降级provider"""

        logger.info(f"为 {failed_provider} 尝试降级...")

        # 获取可用provider列表（排除失败的）
        fallback_candidates = [
            name
            for name, status in self.token_pool.status.items()
            if name != failed_provider and status.available and status.monthly_remaining > 1000
        ]

        # 按优先级排序
        fallback_candidates.sort(key=lambda x: self.token_pool.providers[x].priority)

        for fallback_name in fallback_candidates[:3]:  # 最多尝试3个
            try:
                logger.info(f"尝试降级到 {fallback_name}")
                result = await self._call_with_retry(fallback_name, prompt, max_tokens, timeout)

                if result.get("success"):
                    self.stats["fallback_calls"] += 1
                    logger.info(f"成功降级到 {fallback_name}")
                    result["fallback_from"] = failed_provider
                    return result

            except Exception as e:
                logger.warning(f"降级到 {fallback_name} 失败: {e}")
                continue

        # 所有降级都失败
        return {
            "success": False,
            "error": f"所有provider尝试失败 (主:{failed_provider})",
            "provider": "none",
        }

    def _is_retriable_error(self, error_msg: str) -> bool:
        """判断错误是否可重试"""
        retriable_patterns = [
            "timeout",
            "超时",
            "rate limit",
            "速率限制",
            "503",
            "502",
            "500",
            "connection",
            "连接",
        ]
        error_lower = error_msg.lower()
        return any(pattern in error_lower for pattern in retriable_patterns)

    def _calc_retry_delay(self, attempt: int, config: RetryConfig) -> float:
        """计算重试延迟（指数退避 + 抖动）"""
        import random

        if config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            base_delay = min(config.base_delay * (2**attempt), config.max_delay)
            jitter = base_delay * 0.1 * random.random()
            return base_delay + jitter
        else:
            return config.base_delay

    async def generate_text(
        self,
        prompt: str,
        complexity: str = "medium",
        max_tokens: int = 2000,
        task_type: TaskType = TaskType.GENERATION,
    ) -> Dict[str, Any]:
        """生成文本（带弹性机制）"""
        # 选择provider
        provider = await self.token_pool.select_provider(task_type=task_type, complexity=complexity)

        if not provider:
            return {"success": False, "error": "没有可用的provider"}

        # 使用弹性调用
        return await self.call_with_resilience(provider, prompt, max_tokens)

    async def chat(self, prompt: str, use_cache: bool = True) -> Optional[str]:
        """简单对话"""
        result = await self.generate_text(prompt, complexity="simple")
        return result.get("content") if result.get("success") else None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.stats["total_calls"]
        return {
            **self.stats,
            "success_rate": (self.stats["successful_calls"] / total * 100 if total > 0 else 0),
            "circuit_breakers": self.circuit_breaker_registry.get_all_stats(),
        }


# 全局单例
_enhanced_service: Optional[EnhancedAIService] = None


def get_enhanced_ai_service() -> EnhancedAIService:
    """获取增强型AI服务单例"""
    global _enhanced_service
    if _enhanced_service is None:
        _enhanced_service = EnhancedAIService()
        logger.info("增强型AI服务已初始化")
    return _enhanced_service


# 便捷函数
async def chat_enhanced(prompt: str) -> Optional[str]:
    """增强版对话（自动重试和降级）"""
    service = get_enhanced_ai_service()
    return await service.chat(prompt)


async def generate_text_enhanced(
    prompt: str, complexity: str = "medium", max_tokens: int = 2000
) -> Dict[str, Any]:
    """增强版文本生成"""
    service = get_enhanced_ai_service()
    return await service.generate_text(prompt, complexity, max_tokens)
