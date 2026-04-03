"""Provider-specific API adapters

每个provider的特定调用逻辑
"""

import os
from typing import Any, Dict

import httpx


class ProviderAdapter:
    """Provider适配器基类"""

    def __init__(self, name: str, api_key_env: str):
        self.name = name
        self.api_key_env = api_key_env
        self.api_key = os.getenv(api_key_env)

    async def call(
        self, prompt: str, model: str, max_tokens: int = 2000, api_url: str = None
    ) -> Dict[str, Any]:
        """调用API - 子类实现"""
        raise NotImplementedError


class BaiduQianfanAdapter(ProviderAdapter):
    """百度千帆适配器"""

    async def call(
        self, prompt: str, model: str, max_tokens: int = 2000, api_url: str = None
    ) -> Dict[str, Any]:
        """百度千帆使用access_token作为query parameter"""

        url = f"{api_url}?access_token={self.api_key}"

        headers = {"Content-Type": "application/json"}

        payload = {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}

        # 如果指定了model，添加到payload
        if model and model != "ernie-4.0":
            payload["model"] = model

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()

                # 千帆返回格式：{"result": "...", "usage": {...}}
                if "result" in data:
                    return {
                        "success": True,
                        "content": data["result"],
                        "usage": data.get("usage", {}),
                    }
                else:
                    return {
                        "success": False,
                        "error": "Unexpected response format",
                        "response": data,
                    }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text[:200],
                }


class QwenAdapter(ProviderAdapter):
    """通义千问适配器"""

    async def call(
        self, prompt: str, model: str, max_tokens: int = 2000, api_url: str = None
    ) -> Dict[str, Any]:
        """通义千问标准OpenAI格式"""

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        # 修正模型名称
        model_mapping = {
            "qwen-max": "qwen-max",
            "ernie-4.0": "qwen-max",  # 映射
            "default": "qwen-max",
        }

        actual_model = model_mapping.get(model, model)

        payload = {
            "model": actual_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    return {
                        "success": True,
                        "content": data["choices"][0]["message"]["content"],
                        "usage": data.get("usage", {}),
                    }
                else:
                    return {"success": False, "error": "No choices in response", "response": data}
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text[:200],
                }


class DoubaoAdapter(ProviderAdapter):
    """豆包适配器"""

    async def call(
        self, prompt: str, model: str, max_tokens: int = 2000, api_url: str = None
    ) -> Dict[str, Any]:
        """豆包API调用"""

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        # 修正模型名称
        model_mapping = {
            "doubao-pro": "ep-20241105111448-l7jgz",  # 实际endpoint
            "default": "ep-20241105111448-l7jgz",
        }

        actual_model = model_mapping.get(model, model)

        payload = {
            "model": actual_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    return {
                        "success": True,
                        "content": data["choices"][0]["message"]["content"],
                        "usage": data.get("usage", {}),
                    }
                else:
                    return {"success": False, "error": "No choices in response", "response": data}
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text[:200],
                }


class HunyuanAdapter(ProviderAdapter):
    """混元适配器"""

    async def call(
        self, prompt: str, model: str, max_tokens: int = 2000, api_url: str = None
    ) -> Dict[str, Any]:
        """混元API调用"""

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        # 修正模型名称
        model_mapping = {"hunyuan-lite": "hunyuan-lite", "default": "hunyuan-lite"}

        actual_model = model_mapping.get(model, model)

        payload = {
            "model": actual_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    return {
                        "success": True,
                        "content": data["choices"][0]["message"]["content"],
                        "usage": data.get("usage", {}),
                    }
                else:
                    return {"success": False, "error": "No choices in response", "response": data}
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text[:200],
                }


class SparkAdapter(ProviderAdapter):
    """讯飞星火适配器"""

    async def call(
        self, prompt: str, model: str, max_tokens: int = 2000, api_url: str = None
    ) -> Dict[str, Any]:
        """讯飞星火API调用（使用API Key认证）"""

        # 讯飞使用API Key，不是Bearer token
        headers = {
            "Authorization": self.api_key,  # 直接使用API Key
            "Content-Type": "application/json",
        }

        payload = {
            "model": "spark-4.0",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    return {
                        "success": True,
                        "content": data["choices"][0]["message"]["content"],
                        "usage": data.get("usage", {}),
                    }
                else:
                    return {"success": False, "error": "No choices in response", "response": data}
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text[:200],
                }


class MinimaxAdapter(ProviderAdapter):
    """Minimax适配器"""

    async def call(
        self, prompt: str, model: str, max_tokens: int = 2000, api_url: str = None
    ) -> Dict[str, Any]:
        """Minimax API调用"""

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "model": "abab6.5s-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()

                # Minimax返回格式可能不同
                if "choices" in data and len(data["choices"]) > 0:
                    return {
                        "success": True,
                        "content": data["choices"][0]["message"]["content"],
                        "usage": data.get("usage", {}),
                    }
                elif "reply" in data:  # Minimax原生格式
                    return {
                        "success": True,
                        "content": data["reply"],
                        "usage": data.get("usage", {}),
                    }
                else:
                    return {
                        "success": False,
                        "error": "Unexpected response format",
                        "response": data,
                    }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text[:200],
                }
