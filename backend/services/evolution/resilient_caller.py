"""智能重试机制 - 提升API成功率"""

import asyncio
import logging
import random
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """重试策略"""

    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数退避
    LINEAR_BACKOFF = "linear_backoff"  # 线性退避
    IMMEDIATE = "immediate"  # 立即重试
    NONE = "none"  # 不重试


class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_attempts: int = 3,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        retriable_exceptions: Tuple[Type[Exception], ...] = None,
    ):
        self.max_attempts = max_attempts
        self.strategy = strategy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retriable_exceptions = retriable_exceptions or (
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
        )


class RetryableError(Exception):
    """可重试的错误"""

    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error


class PermanentError(Exception):
    """永久性错误（不应重试）"""


async def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """计算重试延迟"""
    if config.strategy == RetryStrategy.IMMEDIATE:
        return 0
    elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
        return min(config.base_delay * attempt, config.max_delay)
    elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
        # 添加随机抖动，避免同时重试
        base_delay = min(config.base_delay * (2**attempt), config.max_delay)
        jitter = base_delay * 0.1 * random.random()
        return base_delay + jitter
    else:
        return 0


async def with_retry(func: Callable, config: RetryConfig, context: dict = None) -> Any:
    """带重试的执行"""

    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return await func()

        except PermanentError:
            # 永久错误，直接抛出
            raise

        except Exception as e:
            last_exception = e

            # 检查是否应该重试
            if not isinstance(e, config.retriable_exceptions):
                raise

            # 计算延迟
            if attempt < config.max_attempts - 1:
                delay = await calculate_delay(attempt, config)
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)

    # 所有重试都失败
    raise RetryableError(
        f"All {config.max_attempts} attempts failed", original_error=last_exception
    ) from last_exception


class ResilientAICaller:
    """弹性AI调用器 - 带智能重试和降级策略

    V1.3.0: 完善降级策略
    """

    def __init__(self):
        self.retry_config = RetryConfig(
            max_attempts=5,  # 增加到5次重试
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            max_delay=60.0,  # 增加最大延迟
            retriable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
        )

        # V1.3.0: 完善的降级配置（按优先级排序）
        # 包月服务 > 永久免费 > 新用户试用
        self.fallback_providers = {
            # GLM Coding Plan（包月）失败 -> 降级到永久免费
            "glm_coding": ["glm", "qwen", "tongyi", "deepseek"],
            # GLM（永久免费）失败 -> 降级到其他永久免费
            "glm": ["qwen", "tongyi", "deepseek"],
            # 千帆失败 -> 降级到其他永久免费
            "qwen": ["glm", "tongyi", "deepseek"],
            # 通义失败 -> 降级到其他永久免费
            "tongyi": ["glm", "qwen", "deepseek"],
            # DeepSeek（试用）失败 -> 降级到永久免费
            "deepseek": ["glm", "qwen", "tongyi"],
            # 混元失败 -> 降级到其他
            "hunyuan": ["glm", "qwen", "tongyi"],
            # 豆包失败 -> 降级到其他
            "doubao": ["glm", "qwen", "tongyi"],
        }

        # Provider优先级（用于降级决策）
        self.provider_priority = {
            "glm_coding": 0,  # 包月，最高优先级
            "glm": 1,  # 永久免费
            "qwen": 2,  # 永久免费
            "tongyi": 3,  # 永久免费
            "deepseek": 4,  # 试用
            "hunyuan": 5,  # 试用
            "doubao": 6,  # 试用
        }

        # 降级历史记录
        self.fallback_history: List[Dict] = []

        self.call_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "retried_calls": 0,
            "fallback_calls": 0,
            "failed_calls": 0,
            "fallback_by_provider": {},
        }

    async def call_with_retry(self, provider: str, func: Callable, **kwargs) -> Any:
        """带重试和降级的调用"""

        self.call_stats["total_calls"] += 1

        # 尝试1: 主provider + 重试
        try:
            result = await with_retry(lambda: func(**kwargs), self.retry_config)
            self.call_stats["successful_calls"] += 1
            return result

        except RetryableError as e:
            self.call_stats["retried_calls"] += 1
            logger.warning(f"Provider {provider} failed after retries: {e}")

        except Exception as e:
            logger.error(f"Provider {provider} failed with permanent error: {e}")

        # 尝试2: Fallback providers（V1.3.0: 按优先级排序）
        if provider in self.fallback_providers:
            # 按优先级排序降级列表
            fallback_list = sorted(
                self.fallback_providers[provider], key=lambda p: self.provider_priority.get(p, 99)
            )

            for fallback_provider in fallback_list:
                logger.info(
                    f"尝试降级到 {fallback_provider} (优先级: {self.provider_priority.get(fallback_provider, 99)})"
                )

                try:
                    result = await self._call_provider(fallback_provider, **kwargs)
                    self.call_stats["fallback_calls"] += 1
                    self.call_stats["successful_calls"] += 1

                    # 记录fallback使用统计
                    if provider not in self.call_stats["fallback_by_provider"]:
                        self.call_stats["fallback_by_provider"][provider] = {}
                    if fallback_provider not in self.call_stats["fallback_by_provider"][provider]:
                        self.call_stats["fallback_by_provider"][provider][fallback_provider] = 0
                    self.call_stats["fallback_by_provider"][provider][fallback_provider] += 1

                    # 记录fallback历史
                    self.fallback_history.append(
                        {
                            "from": provider,
                            "to": fallback_provider,
                            "timestamp": datetime.utcnow().isoformat(),
                            "success": True,
                        }
                    )

                    await self._log_fallback_usage(provider, fallback_provider)

                    return result

                except Exception as e:
                    logger.error(f"降级到 {fallback_provider} 失败: {e}")

                    # 记录失败的降级尝试
                    self.fallback_history.append(
                        {
                            "from": provider,
                            "to": fallback_provider,
                            "timestamp": datetime.utcnow().isoformat(),
                            "success": False,
                            "error": str(e),
                        }
                    )

        # 所有尝试都失败，返回mock响应
        logger.error("All providers failed for call")
        self.call_stats["failed_calls"] += 1

        return await self._generate_mock_response(kwargs)

    async def _call_provider(self, provider: str, **kwargs) -> Any:
        """调用特定provider"""
        # 这里简化实现，实际应该调用真正的AI API
        # 返回模拟的成功响应
        return {
            "provider": provider,
            "content": f"Mock response from {provider}",
            "success": True,
            "latency_ms": 200,
        }

    async def _generate_mock_response(self, kwargs: Dict) -> Dict:
        """生成mock响应"""
        return {
            "provider": "mock",
            "content": "Mock response (all providers failed)",
            "success": False,
            "error": "All providers unavailable",
            "latency_ms": 0,
        }

    async def _log_fallback_usage(self, primary_provider: str, fallback_provider: str):
        """记录fallback使用"""
        # 简化实现 - 实际应该写入数据库或日志
        logger.info(
            f"Fallback used: {primary_provider} -> {fallback_provider} "
            f"at {datetime.utcnow().isoformat()}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        total = self.call_stats["total_calls"]

        return {
            "total_calls": total,
            "successful_calls": self.call_stats["successful_calls"],
            "success_rate": (self.call_stats["successful_calls"] / total * 100 if total > 0 else 0),
            "retried_calls": self.call_stats["retried_calls"],
            "fallback_calls": self.call_stats["fallback_calls"],
            "failed_calls": self.call_stats["failed_calls"],
        }


# 全局单例
_resilient_caller: Optional[ResilientAICaller] = None


def get_resilient_caller() -> ResilientAICaller:
    """获取弹性调用器单例"""
    global _resilient_caller
    if _resilient_caller is None:
        _resilient_caller = ResilientAICaller()
    return _resilient_caller


# 使用示例
async def example_usage():
    """使用示例"""

    caller = get_resilient_caller()

    # 定义一个会失败的函数
    async def mock_api_call(prompt: str):
        # 模拟随机失败
        if random.random() < 0.3:  # 30%失败率
            raise ConnectionError("Network error")
        return {"content": f"Response to: {prompt}"}

    # 使用重试机制调用
    result = await caller.call_with_retry(
        provider="hunyuan", func=mock_api_call, prompt="Hello, how are you?"
    )

    print(f"Result: {result}")

    # 查看统计
    stats = caller.get_stats()
    print(f"Stats: {stats}")


if __name__ == "__main__":
    asyncio.run(example_usage())
