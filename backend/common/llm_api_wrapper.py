"""
LLM API包装器

提供统一的LLM API调用接口，集成：
1. 分布式速率限制（跨进程）
2. 智能重试机制（指数退避）
3. 监控和日志
4. 1302错误处理
"""

import asyncio
import logging
import random
from typing import Any, Dict, Optional

from backend.common.rate_limiter import DistributedRateLimiter

logger = logging.getLogger(__name__)


class GLMRateLimitException(Exception):
    """GLM API速率限制异常"""


class LLMAPIClient:
    """LLM API客户端包装器

    提供统一的API调用接口，自动处理速率限制和重试
    """

    # 1302错误的重试配置
    RETRY_CONFIG = {
        "max_retries": 5,
        "initial_delay": 2.0,  # 初始延迟2秒
        "max_delay": 60.0,  # 最大延迟60秒
        "exponential_base": 2,  # 指数退避基数
    }

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        model: str = "deepseek-chat",
        max_calls_per_minute: int = 50,
        redis_url: str = "redis://localhost:6379/0",
    ):
        """
        初始化LLM API客户端

        Args:
            api_key: API密钥
            api_url: API地址
            model: 模型名称
            max_calls_per_minute: 每分钟最大调用次数
            redis_url: Redis连接URL
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model = model

        # 初始化速率限制器
        self.rate_limiter = DistributedRateLimiter(
            redis_url=redis_url, max_calls=max_calls_per_minute, period=60
        )

        # 监控统计
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "rate_limit_hits": 0,
            "total_tokens": 0,
        }

    async def call_api(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: int = 30,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        调用LLM API（带速率限制和重试）

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            timeout: 超时时间（秒）
            **kwargs: 其他参数

        Returns:
            API响应

        Raises:
            GLMRateLimitException: 速率限制重试失败
            Exception: 其他API错误
        """
        self.stats["total_calls"] += 1

        if not await self.rate_limiter.acquire_async("glm_api", timeout=60):
            self.stats["rate_limit_hits"] += 1
            raise GLMRateLimitException("Rate limit timeout")

        last_exception = None
        for attempt in range(self.RETRY_CONFIG["max_retries"]):
            try:
                return await self._attempt_call(
                    messages, temperature, max_tokens, timeout, **kwargs
                )
            except Exception as e:
                last_exception = e
                if not self._is_rate_limit_error(str(e)):
                    raise
                if attempt < self.RETRY_CONFIG["max_retries"] - 1:
                    delay = self._calc_retry_delay(attempt)
                    logger.warning(
                        f"Rate limit hit (attempt {attempt + 1}), retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Rate limit retry exhausted after {self.RETRY_CONFIG['max_retries']} attempts"
                    )

        self.stats["rate_limit_hits"] += 1
        raise GLMRateLimitException(f"API call failed after retries: {last_exception}")

    def _is_rate_limit_error(self, error_msg: str) -> bool:
        return "1302" in error_msg or "rate limit" in error_msg.lower() or "速率限制" in error_msg

    def _calc_retry_delay(self, attempt: int) -> float:
        base_delay = self.RETRY_CONFIG["initial_delay"]
        exponential = self.RETRY_CONFIG["exponential_base"] ** attempt
        jitter = random.uniform(0, 1)
        return min(base_delay * exponential + jitter, self.RETRY_CONFIG["max_delay"])

    async def _attempt_call(self, messages, temperature, max_tokens, timeout, **kwargs):
        response = await self._do_call_api(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs,
        )
        self.stats["successful_calls"] += 1
        if "usage" in response:
            self.stats["total_tokens"] += response["usage"].get("total_tokens", 0)
        return response

    async def _do_call_api(
        self, messages: list, temperature: float, max_tokens: int, timeout: int, **kwargs
    ) -> Dict[str, Any]:
        """
        实际执行API调用（需要根据具体API实现）

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            timeout: 超时时间
            **kwargs: 其他参数

        Returns:
            API响应
        """
        # 这里需要根据实际使用的API实现
        # 示例使用OpenAI兼容的API

        import aiohttp

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout, connect=10)
        ) as session:
            async with session.post(
                self.api_url,
                json=payload,
                headers=headers,
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(f"API error {response.status}: {error_text}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "rate_limit_hits": 0,
            "total_tokens": 0,
        }


# ==================== 全局单例 ====================

_global_client: Optional[LLMAPIClient] = None


def get_llm_client(
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    model: Optional[str] = None,
    max_calls_per_minute: int = 50,
) -> LLMAPIClient:
    """
    获取全局LLM API客户端单例

    Args:
        api_key: API密钥（如果为None，从环境变量读取）
        api_url: API地址
        model: 模型名称
        max_calls_per_minute: 每分钟最大调用次数

    Returns:
        LLMAPIClient实例
    """
    global _global_client

    if _global_client is None:
        import os

        if api_key is None:
            api_key = os.getenv("DEEPSEEK_API_KEY")

        if api_key is None:
            raise ValueError("DEEPSEEK_API_KEY not set")

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        deepseek_api_url = os.getenv(
            "DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions"
        )

        _global_client = LLMAPIClient(
            api_key=api_key,
            api_url=api_url or deepseek_api_url,
            model=model or "deepseek-chat",
            max_calls_per_minute=max_calls_per_minute,
            redis_url=redis_url,
        )

    return _global_client


# ==================== 使用示例 ====================

if __name__ == "__main__":
    pass

    async def example_usage():
        """使用示例"""

        # 方式1: 使用客户端包装器（推荐）
        client = get_llm_client()

        messages = [{"role": "user", "content": "你好，请介绍一下灵知系统"}]

        try:
            response = await client.call_api(messages=messages, temperature=0.7, max_tokens=1000)
            print("Response:", response)
            print("Stats:", client.get_stats())

        except GLMRateLimitException as e:
            print(f"Rate limit error: {e}")

        # 方式2: 使用装饰器
        # @with_rate_limit(max_calls_per_minute=50)
        # @with_retry(max_retries=3)
        # async def my_api_call():
        #     pass
        #
        # await my_api_call()

    # 运行示例
    # asyncio.run(example_usage())
