"""AI调用优化层

整合缓存、批处理、限流等功能，最大化提升效率并避免频率限制
"""

import logging
from typing import Callable, List, Optional

from backend.services.ai_service import chat, code_development, reason
from backend.services.evolution.rate_limiter import get_rate_limiter
from backend.services.evolution.smart_cache import get_cache

logger = logging.getLogger(__name__)


class OptimizedAIClient:
    """优化的AI调用客户端"""

    def __init__(
        self,
        enable_cache: bool = True,
        enable_rate_limit: bool = True,
        cache_ttl_hours: int = 48,
        max_requests_per_minute: int = 80,
    ):
        self.enable_cache = enable_cache
        self.enable_rate_limit = enable_rate_limit

        # 初始化缓存
        if enable_cache:
            self.cache = get_cache(ttl_hours=cache_ttl_hours)

        # 初始化限流器
        if enable_rate_limit:
            self.limiter = get_rate_limiter(
                "glm_coding", max_requests_per_minute=max_requests_per_minute
            )

    async def call_with_optimization(
        self, prompt: str, func: Callable, use_cache: bool = None, use_rate_limit: bool = None
    ) -> Optional[str]:
        """带所有优化的AI调用

        Args:
            prompt: 提示词
            func: AI调用函数
            use_cache: 是否使用缓存
            use_rate_limit: 是否使用限流

        Returns:
            AI响应
        """

        # 使用默认设置
        if use_cache is None:
            use_cache = self.enable_cache
        if use_rate_limit is None:
            use_rate_limit = self.enable_rate_limit

        # 1. 尝试缓存
        if use_cache and self.cache:
            cached_result = self.cache.get(prompt, "optimized")
            if cached_result is not None:
                logger.info("✅ 缓存命中，跳过API调用")
                return cached_result

        # 2. 限流控制
        if use_rate_limit and self.limiter:
            if not await self.limiter.acquire(timeout=60.0, show_waiting=False):
                logger.warning("⚠️  限流等待超时")
                return None

        # 3. 调用API
        try:
            result = await func(prompt)

            # 4. 保存到缓存
            if result and use_cache and self.cache:
                self.cache.set(prompt, result, "optimized")

            return result

        except Exception as e:
            logger.error(f"❌ API调用失败: {e}")
            return None

    async def batch_call(
        self,
        prompts: List[str],
        func: Callable,
        batch_size: int = 5,
        delay_between_batches: float = 3.0,
        use_cache: bool = True,
    ) -> List[Optional[str]]:
        """批量AI调用（自动应用优化）"""

        results = []

        # 过滤已缓存的
        uncached_prompts = []
        cache_hits = []

        if use_cache and self.cache:
            for prompt in prompts:
                cached = self.cache.get(prompt, "batch")
                if cached:
                    cache_hits.append(cached)
                else:
                    uncached_prompts.append(prompt)

            logger.info(f"💾 缓存命中: {len(cache_hits)}/{len(prompts)}")

            if not uncached_prompts:
                # 全部命中缓存
                return cache_hits

        # 批量处理未缓存的请求
        from backend.services.evolution.batch_processor import BatchProcessor

        processor = BatchProcessor(
            batch_size=batch_size, delay_between_batches=delay_between_batches
        )

        batch_results = await processor.batch_process(uncached_prompts, func, show_progress=False)

        # 合并结果
        results = cache_hits + batch_results

        return results

    def get_optimization_stats(self) -> dict:
        """获取优化统计"""

        stats = {
            "cache_enabled": self.enable_cache,
            "rate_limit_enabled": self.enable_rate_limit,
        }

        if self.enable_cache and self.cache:
            stats["cache"] = self.cache.get_stats()

        if self.enable_rate_limit and self.limiter:
            stats["rate_limiter"] = self.limiter.get_stats()

        return stats

    def format_optimization_stats(self) -> str:
        """格式化优化统计"""

        lines = [
            "📊 AI调用优化统计",
            "=" * 60,
            f"缓存启用: {'✅' if self.enable_cache else '❌'}",
            f"限流启用: {'✅' if self.enable_rate_limit else '❌'}",
            "",
        ]

        stats = self.get_optimization_stats()

        if "cache" in stats:
            lines.append("💾 缓存统计:")
            cache_stats = stats["cache"]
            lines.append(f"  命中率: {cache_stats['hit_rate']:.1%}")
            lines.append(f"  节省请求: {cache_stats['hits']}")
            lines.append("")

        if "rate_limiter" in stats:
            lines.append("⏱️  限流器统计:")
            limiter_stats = stats["rate_limiter"]
            lines.append(f"  成功请求: {limiter_stats['successful_requests']}")
            lines.append(f"  限流次数: {limiter_stats['rate_limited']}")
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)


# 全局实例
_optimized_client: OptimizedAIClient = None


def get_optimized_client(
    enable_cache: bool = True, enable_rate_limit: bool = True
) -> OptimizedAIClient:
    """获取优化的AI客户端实例"""

    global _optimized_client

    if _optimized_client is None:
        _optimized_client = OptimizedAIClient(
            enable_cache=enable_cache, enable_rate_limit=enable_rate_limit
        )

    return _optimized_client


# 便捷函数
async def optimized_chat(prompt: str) -> Optional[str]:
    """优化的简单对话"""

    client = get_optimized_client()
    return await client.call_with_optimization(prompt, chat)


async def optimized_reason(prompt: str) -> Optional[str]:
    """优化的复杂推理"""

    client = get_optimized_client()
    return await client.call_with_optimization(prompt, reason)


async def optimized_code_development(prompt: str) -> Optional[str]:
    """优化的代码开发"""

    client = get_optimized_client()
    return await client.call_with_optimization(prompt, code_development)


async def batch_chat(
    prompts: List[str], batch_size: int = 5, delay_between_batches: float = 2.0
) -> List[Optional[str]]:
    """批量简单对话（带优化）"""

    client = get_optimized_client()
    return await client.batch_call(
        prompts, chat, batch_size=batch_size, delay_between_batches=delay_between_batches
    )


async def batch_code_development(
    prompts: List[str], batch_size: int = 3, delay_between_batches: float = 5.0
) -> List[Optional[str]]:
    """批量代码开发（带优化）"""

    client = get_optimized_client()
    return await client.batch_call(
        prompts,
        code_development,
        batch_size=batch_size,
        delay_between_batches=delay_between_batches,
    )


def show_optimization_stats():
    """显示优化统计"""
    client = get_optimized_client()
    print(client.format_optimization_stats())
