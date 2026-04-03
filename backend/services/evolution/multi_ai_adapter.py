"""多AI适配器

支持并行调用多个AI服务进行对比学习：
- 灵知系统（自有）
- 混元（腾讯）
- 豆包（字节）
- DeepSeek
- GLM（智谱）
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class BaseAIAdapter(ABC):
    """AI适配器基类"""

    def __init__(self):
        self.timeout = 30.0  # 30秒超时

    @abstractmethod
    async def generate(self, prompt: str, request_type: str = "qa", **kwargs) -> Dict[str, Any]:
        """生成内容

        Args:
            prompt: 用户提示
            request_type: 请求类型（qa, podcast, other）
            **kwargs: 其他参数

        Returns:
            {
                "content": "生成的内容",
                "metadata": {...},
                "provider": "ai_provider_name",
                "model": "model_name",
                "latency_ms": 150,
                "timestamp": "2026-04-01T12:00:00"
            }
        """

    async def _make_request(
        self, url: str, headers: Dict[str, str], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """统一的HTTP请求方法"""
        start_time = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()

            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return {
                "content": result.get("content")
                or result.get("answer")
                or result.get("output", ""),
                "raw_response": result,
                "latency_ms": latency_ms,
                "success": True,
            }

        except Exception as e:
            logger.error(f"AI request failed: {e}", exc_info=True)
            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return {"content": "", "error": str(e), "latency_ms": latency_ms, "success": False}


class LingzhiAdapter(BaseAIAdapter):
    """灵知系统适配器（内部系统）"""

    async def generate(self, prompt: str, request_type: str = "qa", **kwargs) -> Dict[str, Any]:
        """调用灵知系统内部API"""
        from backend.services.rag_pipeline import RAGPipeline

        start_time = datetime.now()

        try:
            if request_type == "qa":
                # 使用RAG管道
                pipeline = RAGPipeline()
                result = await pipeline.query(question=prompt, use_rag=True, use_reasoning=False)

                content = f"{result.get('answer', '')}\n\n**参考资料：**\n"
                for source in result.get("sources", [])[:3]:
                    content += f"- {source.get('title', '')}\n"

                return {
                    "content": content,
                    "metadata": {"sources": result.get("sources", []), "reasoning_used": False},
                    "provider": "lingzhi",
                    "model": "RAG-v1",
                    "latency_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                    "timestamp": datetime.now().isoformat(),
                    "success": True,
                }

            elif request_type == "podcast":
                # 播客生成
                from backend.services.generation.ppt_generator import PPTGenerator

                _generator = PPTGenerator()  # noqa: F841
                # 简化：暂时返回脚本
                content = f"# {prompt}\n\n（播客脚本生成中...）"

                return {
                    "content": content,
                    "metadata": {"format": "script"},
                    "provider": "lingzhi",
                    "model": "Content-v1",
                    "latency_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                    "timestamp": datetime.now().isoformat(),
                    "success": True,
                }

            else:
                return {
                    "content": "灵知系统暂不支持此类型",
                    "provider": "lingzhi",
                    "model": "unknown",
                    "latency_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                    "timestamp": datetime.now().isoformat(),
                    "success": False,
                }

        except Exception as e:
            logger.error(f"Lingzhi generation failed: {e}", exc_info=True)
            return {
                "content": "",
                "error": str(e),
                "provider": "lingzhi",
                "model": "unknown",
                "latency_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                "timestamp": datetime.now().isoformat(),
                "success": False,
            }


class HunyuanAdapter(BaseAIAdapter):
    """混元API适配器（腾讯）"""

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("HUNYUAN_API_KEY")
        self.api_url = "https://api.hunyuan.cloud.tencent.com/v1/chat/completions"

    async def generate(self, prompt: str, request_type: str = "qa", **kwargs) -> Dict[str, Any]:
        """调用混元API"""

        if not self.api_key:
            logger.warning("HUNYUAN_API_KEY not set, returning mock response")
            return self._mock_response(prompt, "hunyuan")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        # 根据请求类型调整prompt
        system_prompt = self._get_system_prompt(request_type)

        payload = {
            "model": "hunyuan-lite",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        result = await self._make_request(self.api_url, headers, payload)

        return {
            "content": result.get("content", ""),
            "metadata": {"model": "hunyuan-lite", "request_type": request_type},
            "provider": "hunyuan",
            "model": "hunyuan-lite",
            "latency_ms": result.get("latency_ms", 0),
            "timestamp": datetime.now().isoformat(),
            "success": result.get("success", False),
        }

    def _get_system_prompt(self, request_type: str) -> str:
        """获取系统提示"""
        prompts = {
            "qa": "你是一个知识渊博的助手，擅长回答气功、中医、养生等问题。请提供准确、实用、结构清晰的回答。",
            "podcast": "你是一个专业的播客内容创作者，擅长生成吸引人的播客脚本。",
        }
        return prompts.get(request_type, "你是一个有用的AI助手。")

    def _mock_response(self, prompt: str, provider: str) -> Dict[str, Any]:
        """返回模拟响应（当API密钥未设置时）"""
        return {
            "content": f"[模拟{provider}回答]\n\n关于'{prompt}'，这是一个很好的问题。建议从以下几个方面考虑：1. 明确目标 2. 制定计划 3. 持续实践。",
            "metadata": {"mock": True},
            "provider": provider,
            "model": "mock",
            "latency_ms": 500,
            "timestamp": datetime.now().isoformat(),
            "success": True,
        }


class DoubaoAdapter(BaseAIAdapter):
    """豆包API适配器（字节）"""

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("DOUBAO_API_KEY")
        self.api_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

    async def generate(self, prompt: str, request_type: str = "qa", **kwargs) -> Dict[str, Any]:
        """调用豆包API"""

        if not self.api_key:
            logger.warning("DOUBAO_API_KEY not set, returning mock response")
            return self._mock_response(prompt, "doubao")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "model": "ep-20241105111448-l7jgz",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        result = await self._make_request(self.api_url, headers, payload)

        return {
            "content": result.get("content", ""),
            "metadata": {},
            "provider": "doubao",
            "model": "doubao-pro",
            "latency_ms": result.get("latency_ms", 0),
            "timestamp": datetime.now().isoformat(),
            "success": result.get("success", False),
        }

    def _mock_response(self, prompt: str, provider: str) -> Dict[str, Any]:
        """返回模拟响应"""
        return {
            "content": f"[模拟{provider}回答]\n\n针对'{prompt}'这个问题，我认为关键在于：\n\n1. 理解核心原理\n2. 掌握正确方法\n3. 坚持持续练习\n\n这些都需要时间和耐心，建议循序渐进。",
            "metadata": {"mock": True},
            "provider": provider,
            "model": "mock",
            "latency_ms": 600,
            "timestamp": datetime.now().isoformat(),
            "success": True,
        }


class DeepSeekAdapter(BaseAIAdapter):
    """DeepSeek API适配器"""

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.api_url = "https://api.deepseek.com/v1/chat/completions"

    async def generate(self, prompt: str, request_type: str = "qa", **kwargs) -> Dict[str, Any]:
        """调用DeepSeek API"""

        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY not set, returning mock response")
            return self._mock_response(prompt, "deepseek")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        result = await self._make_request(self.api_url, headers, payload)

        return {
            "content": result.get("content", ""),
            "metadata": {},
            "provider": "deepseek",
            "model": "deepseek-chat",
            "latency_ms": result.get("latency_ms", 0),
            "timestamp": datetime.now().isoformat(),
            "success": result.get("success", False),
        }

    def _mock_response(self, prompt: str, provider: str) -> Dict[str, Any]:
        """返回模拟响应"""
        return {
            "content": f"[模拟{provider}回答]\n\n关于'{prompt}'，我的建议是：\n\n首先，要明确学习的目标和方向。其次，找到适合自己的学习方法。最后，保持持续的练习和反思。\n\n记住，任何技能的提升都需要时间积累。",
            "metadata": {"mock": True},
            "provider": provider,
            "model": "mock",
            "latency_ms": 700,
            "timestamp": datetime.now().isoformat(),
            "success": True,
        }


class GLMAdapter(BaseAIAdapter):
    """GLM API适配器（智谱）"""

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("GLM_API_KEY")
        self.api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    async def generate(self, prompt: str, request_type: str = "qa", **kwargs) -> Dict[str, Any]:
        """调用GLM API"""

        if not self.api_key:
            logger.warning("GLM_API_KEY not set, returning mock response")
            return self._mock_response(prompt, "glm")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "model": "glm-4",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        result = await self._make_request(self.api_url, headers, payload)

        return {
            "content": result.get("content", ""),
            "metadata": {},
            "provider": "glm",
            "model": "glm-4",
            "latency_ms": result.get("latency_ms", 0),
            "timestamp": datetime.now().isoformat(),
            "success": result.get("success", False),
        }

    def _mock_response(self, prompt: str, provider: str) -> Dict[str, Any]:
        """返回模拟响应"""
        return {
            "content": f"[模拟{provider}回答]\n\n对于'{prompt}'这个问题，我认为：\n\n1. 理论基础很重要\n2. 实践应用是关键\n3. 持续改进才能进步\n\n建议从这三个方面入手，逐步提升。",
            "metadata": {"mock": True},
            "provider": provider,
            "model": "mock",
            "latency_ms": 800,
            "timestamp": datetime.now().isoformat(),
            "success": True,
        }


class MultiAIAdapter:
    """多AI适配器管理器"""

    ADAPTERS = {
        "lingzhi": LingzhiAdapter,
        "hunyuan": HunyuanAdapter,
        "doubao": DoubaoAdapter,
        "deepseek": DeepSeekAdapter,
        "glm": GLMAdapter,
    }

    def __init__(self):
        self._adapters = {}
        for name, adapter_class in self.ADAPTERS.items():
            self._adapters[name] = adapter_class()

    async def parallel_generate(
        self,
        prompt: str,
        request_type: str = "qa",
        providers: Optional[List[str]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Dict[str, Any]]:
        """并行调用多个AI生成内容

        Args:
            prompt: 用户提示
            request_type: 请求类型
            providers: 要调用的AI列表，None表示全部
            timeout: 总超时时间（秒）

        Returns:
            {
                "lingzhi": {...},
                "hunyuan": {...},
                "doubao": {...},
                ...
            }
        """
        if providers is None:
            providers = list(self.ADAPTERS.keys())

        # 并行调用
        tasks = []
        for provider in providers:
            task = self._adapters[provider].generate(prompt, request_type)
            tasks.append((provider, task))

        # 等待所有任务完成（或超时）
        results = {}
        for provider, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=timeout)
                results[provider] = result
            except asyncio.TimeoutError:
                logger.warning(f"Provider {provider} timed out")
                results[provider] = {
                    "content": "",
                    "error": "Timeout",
                    "provider": provider,
                    "success": False,
                }
            except Exception as e:
                logger.error(f"Provider {provider} failed: {e}")
                results[provider] = {
                    "content": "",
                    "error": str(e),
                    "provider": provider,
                    "success": False,
                }

        return results

    async def compare_responses(
        self, prompt: str, request_type: str = "qa", providers: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """对比多个AI的响应

        Returns:
            {
                "responses": {...},
                "summary": {
                    "total": 5,
                    "successful": 4,
                    "failed": 1,
                    "avg_latency_ms": 600
                }
            }
        """
        responses = await self.parallel_generate(prompt, request_type, providers)

        # 统计摘要
        total = len(responses)
        successful = sum(1 for r in responses.values() if r.get("success", False))
        failed = total - successful

        latencies = [r.get("latency_ms", 0) for r in responses.values() if r.get("success", False)]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        return {
            "responses": responses,
            "summary": {
                "total": total,
                "successful": successful,
                "failed": failed,
                "avg_latency_ms": int(avg_latency),
            },
        }


# 全局实例
_multi_ai_adapter = None


def get_multi_ai_adapter() -> MultiAIAdapter:
    """获取多AI适配器单例"""
    global _multi_ai_adapter
    if _multi_ai_adapter is None:
        _multi_ai_adapter = MultiAIAdapter()
    return _multi_ai_adapter
