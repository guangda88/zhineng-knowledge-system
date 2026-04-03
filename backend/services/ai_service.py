"""AI服务统一接口

集成FreeTokenPool，提供便捷的AI调用接口
支持智能缓存、批处理和限流

V1.3.0 优化:
- 集成智能重试机制（指数退避）
- 集成熔断器防止级联故障
- 完善降级策略
- 目标：API成功率从95%提升到99%
"""

from typing import Optional

from backend.services.evolution.free_token_pool import TaskType, get_free_token_pool
from backend.services.evolution.smart_cache import get_cache

# 尝试导入增强版服务
try:
    from backend.services.ai_service_enhanced import (
        chat_enhanced,
        generate_text_enhanced,
        get_enhanced_ai_service,
    )

    ENHANCED_ENABLED = True
except ImportError:
    ENHANCED_ENABLED = None

# 全局开关：默认使用增强版（可通过环境变量关闭）
import os

USE_ENHANCED = os.getenv("AI_SERVICE_USE_ENHANCED", "true").lower() == "true"

_pool = None
_cache = None


def get_ai_service():
    """获取AI服务实例"""
    global _pool
    if _pool is None:
        _pool = get_free_token_pool()
    return _pool


def get_ai_cache():
    """获取AI缓存实例"""
    global _cache
    if _cache is None:
        _cache = get_cache(ttl_hours=48)
    return _cache


async def generate_text(
    prompt: str,
    complexity: str = "medium",
    max_tokens: int = 2000,
    task_type: TaskType = TaskType.GENERATION,
    use_enhanced: bool = None,
) -> dict:
    """
    生成文本（智能选择最优provider）

    V1.3.0: 支持增强版服务（智能重试+熔断器）

    Args:
        prompt: 提示词
        complexity: simple/medium/high
        max_tokens: 最大token数
        task_type: 任务类型
        use_enhanced: 是否使用增强版（None=自动判断）

    Returns:
        {
            "success": bool,
            "content": str,
            "provider": str,
            "tokens": int,
            "latency_ms": int,
            "fallback_from": str  # 如果使用了降级
        }
    """
    # 判断是否使用增强版
    should_use_enhanced = (
        use_enhanced if use_enhanced is not None else (USE_ENHANCED and ENHANCED_ENABLED)
    )

    if should_use_enhanced:
        # 使用增强版（带重试和熔断器）
        service = get_enhanced_ai_service()
        return await service.generate_text(prompt, complexity, max_tokens, task_type)

    # 使用标准版
    pool = get_ai_service()

    # 选择provider
    provider = await pool.select_provider(task_type=task_type, complexity=complexity)

    if not provider:
        return {"success": False, "error": "没有可用的provider"}

    # 调用
    result = await pool.call_provider(provider, prompt, max_tokens=max_tokens)

    return result


async def generate_with_fallback(prompt: str, max_retries: int = 3, max_tokens: int = 2000) -> dict:
    """
    生成文本（自动重试和fallback）

    如果某个provider失败，自动尝试其他provider
    """
    pool = get_ai_service()

    for attempt in range(max_retries):
        # 选择可用的provider
        provider = await pool.select_provider()

        if not provider:
            return {"success": False, "error": "没有可用的provider"}

        result = await pool.call_provider(provider, prompt, max_tokens)

        if result["success"]:
            return result

        # 失败，尝试下一个
        print(f"⚠️  {provider} 失败，尝试其他provider...")

    return {"success": False, "error": f"所有provider尝试失败 ({max_retries}次)"}


# ============ 便捷函数 ============


async def chat(prompt: str, use_cache: bool = True) -> Optional[str]:
    """简单对话（返回内容字符串）

    V1.3.0: 自动使用增强版服务提升成功率

    Args:
        prompt: 提示词
        use_cache: 是否使用缓存（默认True）
    """
    if use_cache:
        cache = get_ai_cache()
        cached_result = cache.get(prompt, "chat")
        if cached_result is not None:
            return cached_result

    # 使用增强版（如果可用）
    if USE_ENHANCED and ENHANCED_ENABLED:
        result = await chat_enhanced(prompt)
    else:
        result = await generate_text(prompt, complexity="simple")
        result = result.get("content") if result.get("success") else None

    if result and use_cache:
        cache = get_ai_cache()
        cache.set(prompt, result, "chat")

    return result


async def reason(prompt: str, use_cache: bool = True) -> Optional[str]:
    """复杂推理（使用DeepSeek等推理强的模型）

    Args:
        prompt: 提示词
        use_cache: 是否使用缓存（默认True）
    """
    if use_cache:
        cache = get_ai_cache()
        cached_result = cache.get(prompt, "reason")
        if cached_result is not None:
            return cached_result

    result = await generate_text(prompt, complexity="high", task_type=TaskType.REASONING)

    if result["success"] and use_cache:
        cache = get_ai_cache()
        cache.set(prompt, result["content"], "reason")

    return result["content"] if result["success"] else None


async def generate_code(prompt: str) -> Optional[str]:
    """代码生成（使用GLM Coding Plan）"""
    result = await generate_text(prompt, task_type=TaskType.TASK, max_tokens=3000)
    return result["content"] if result["success"] else None


async def summarize(text: str, max_length: int = 500) -> Optional[str]:
    """文本摘要"""
    prompt = f"""
    请为以下文本生成摘要，不超过{max_length}字:

    {text[:4000]}

    摘要应该:
    1. 包含主要观点
    2. 简洁明了
    3. 便于快速理解
    """

    result = await generate_text(prompt, max_tokens=1000)
    return result["content"] if result["success"] else None


async def extract_info(text: str, info_type: str) -> Optional[str]:
    """信息提取"""
    prompt = f"""
    从以下文本中提取{info_type}:

    {text[:4000]}

    请只返回提取的信息，不要额外解释。
    """

    result = await generate_text(prompt, complexity="simple", max_tokens=500)
    return result["content"] if result["success"] else None


async def code_development(prompt: str) -> Optional[str]:
    """
    代码开发（使用GLM Coding Plan）

    专门用于开发场景，自动使用包月的GLM Coding Plan
    适用于：代码生成、代码审查、调试等

    Args:
        prompt: 代码相关的提示词

    Returns:
        生成的代码或建议
    """
    pool = get_ai_service()

    # 直接使用glm_coding provider
    result = await pool.call_provider(
        "glm_coding", prompt, max_tokens=4000  # 代码任务可能需要更长输出
    )

    return result["content"] if result["success"] else None


async def debug_code(code: str, error: str = None) -> Optional[str]:
    """
    代码调试（使用GLM Coding Plan）

    Args:
        code: 有问题的代码
        error: 错误信息（可选）

    Returns:
        调试建议和修复方案
    """
    prompt = f"""
请帮我调试以下代码:

```python
{code}
```
"""

    if error:
        prompt += f"\n错误信息:\n```\n{error}\n```\n"

    prompt += """
请分析问题并提供:
1. 问题原因
2. 修复方案
3. 修复后的代码
"""

    return await code_development(prompt)


async def code_review(code: str, focus: str = None) -> Optional[str]:
    """
    代码审查（使用GLM Coding Plan）

    Args:
        code: 要审查的代码
        focus: 审查重点（如：性能、安全、可读性）

    Returns:
        审查意见和改进建议
    """
    prompt = f"""
请审查以下代码:

```python
{code}
```
"""

    if focus:
        prompt += f"\n请重点关注: {focus}"

    prompt += """

请提供:
1. 整体评价
2. 发现的问题
3. 改进建议
4. 优化后的代码（如需要）
"""

    return await code_development(prompt)


# ============ 状态查询 ============


def get_pool_status() -> dict:
    """获取Token池状态"""
    pool = get_ai_service()
    return pool.get_pool_status()


def format_pool_status() -> str:
    """格式化Token池状态"""
    status = get_pool_status()

    lines = [
        "📊 Token池状态",
        "=" * 60,
        f"总额度: {status['total_quota']:,} tokens",
        f"已使用: {status['total_used']:,} tokens",
        f"剩余: {status['total_remaining']:,} tokens",
        f"使用率: {status['usage_percentage']:.1f}%",
        "",
        "可用Provider:",
    ]

    for name, info in status["providers"].items():
        if info["available"]:
            lines.append(
                f"  ✅ {name}: {info['remaining']:,} tokens "
                f"(成功率: {info['success_rate']:.0%}, "
                f"延迟: {info['avg_latency_ms']:.0f}ms)"
            )

    return "\n".join(lines)


# ============ 导出 ============

__all__ = [
    "chat",
    "reason",
    "generate_code",
    "code_development",
    "debug_code",
    "code_review",
    "summarize",
    "extract_info",
    "generate_text",
    "generate_with_fallback",
    "get_pool_status",
    "format_pool_status",
    # V1.3.0 新增
    "get_enhanced_ai_service",
    "chat_enhanced",
    "generate_text_enhanced",
    "ENHANCED_ENABLED",
    "USE_ENHANCED",
]
