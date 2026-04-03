"""Chain-of-Thought 推理模块

实现链式推理，让模型逐步思考问题
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from .base import BaseReasoner, QueryType, ReasoningResult, ReasoningStep

logger = logging.getLogger(__name__)


class CoTReasoner(BaseReasoner):
    """Chain-of-Thought 推理器

    使用逐步推理的方式回答复杂问题
    """

    def __init__(self, api_key: str = "", api_url: str = ""):
        super().__init__(api_key, api_url)
        self.model_name = "deepseek-chat"
        self._http_client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建HTTP客户端（使用连接池）"""
        if self._http_client is None:
            async with self._client_lock:
                if self._http_client is None:
                    self._http_client = httpx.AsyncClient(
                        timeout=60.0,
                        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                    )
        return self._http_client

    async def close(self) -> None:
        """关闭HTTP客户端连接"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def reason(
        self, question: str, context: Optional[List[Dict[str, Any]]] = None, **kwargs
    ) -> ReasoningResult:
        """执行CoT推理

        Args:
            question: 用户问题
            context: 上下文文档
            **kwargs: 其他参数（如temperature, max_tokens等）

        Returns:
            推理结果
        """
        start_time = time.time()

        # 分析问题类型
        query_type = self.analyze_query(question)

        # 构建提示词
        prompt = self._build_cot_prompt(question, context, query_type)

        # 调用LLM
        response_text = await self._call_llm(
            prompt,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2000),
        )

        # 解析推理过程
        steps, answer = self._parse_cot_response(response_text)

        reasoning_time = time.time() - start_time

        return ReasoningResult(
            answer=answer,
            query_type=query_type,
            steps=steps,
            sources=context or [],
            confidence=self._calculate_confidence(steps, answer),
            reasoning_time=reasoning_time,
            model_used=self.model_name,
        )

    def _build_cot_prompt(
        self, question: str, context: Optional[List[Dict[str, Any]]], query_type: QueryType
    ) -> str:
        """构建CoT提示词

        Args:
            question: 用户问题
            context: 上下文文档
            query_type: 问题类型

        Returns:
            提示词字符串
        """
        context_str = self.format_context(context) if context else "无参考上下文"

        # 根据问题类型选择提示模板
        templates = {
            QueryType.FACTUAL: """
请直接回答以下事实性问题，不需要详细推理。

参考上下文：
{context}

问题：{question}

答案：
""",
            QueryType.EXPLANATION: """
请使用逐步推理的方式解释以下问题。

参考上下文：
{context}

问题：{question}

请按照以下格式回答：

思考过程：
1. 首先分析问题的核心概念
2. 然后逐步解释相关知识
3. 最后总结要点

答案：
[你的完整解释]
""",
            QueryType.COMPARISON: """
请使用逐步比较的方式分析以下问题。

参考上下文：
{context}

问题：{question}

请按照以下格式回答：

思考过程：
1. 首先明确比较的对象
2. 从多个维度进行对比分析
3. 总结相同点和不同点

答案：
[你的完整分析]
""",
            QueryType.MULTI_HOP: """
请使用多步推理的方式回答以下复杂问题。

参考上下文：
{context}

问题：{question}

请按照以下格式回答：

思考过程：
1. 首先分解问题，识别关键信息
2. 然后逐步推理，建立逻辑链条
3. 最后得出结论

答案：
[你的最终答案]
""",
            QueryType.REASONING: """
请使用逐步推理的方式回答以下问题。

参考上下文：
{context}

问题：{question}

请按照以下格式回答：

思考过程：
1. 首先分析问题的关键点
2. 然后逐步推理
3. 最后得出结论

答案：
[你的最终答案]
""",
        }

        template = templates.get(query_type, templates[QueryType.REASONING])
        return template.format(context=context_str, question=question)

    async def _call_llm(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """调用大语言模型（使用速率限制器）

        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            模型响应文本
        """
        # 优先使用LLM API包装器（带速率限制）
        if self.llm_client:
            try:
                from backend.common.llm_api_wrapper import GLMRateLimitException

                response = await self.llm_client.call_api(
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个专业的知识问答助手，擅长逐步推理分析问题。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response["choices"][0]["message"]["content"]

            except GLMRateLimitException as e:
                logger.error(f"Rate limit exceeded: {e}")
                raise RuntimeError(
                    "LLM API rate limit exceeded. "
                    "Please retry later or configure DEEPSEEK_API_KEY."
                ) from e

            except Exception as e:
                logger.error(f"LLM API call failed: {e}")
                raise RuntimeError(
                    f"LLM API call failed: {e}. " "Please check DEEPSEEK_API_KEY configuration."
                ) from e

        # 降级到原始HTTP客户端
        if not self.api_key:
            raise RuntimeError(
                "No API key configured. "
                "Set DEEPSEEK_API_KEY environment variable to enable LLM reasoning."
            )

        try:
            client = await self._get_client()
            response = await client.post(
                self.api_url or "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一个专业的知识问答助手，擅长逐步推理分析问题。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API returned HTTP {e.response.status_code}: {e}")
            raise RuntimeError(f"LLM API HTTP error {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"LLM API request failed: {e}")
            raise RuntimeError(f"LLM API request failed: {e}") from e

    def _build_fallback_response(self) -> str:
        """构建降级响应模板（仅用于已知 API 不可用时的开发调试）"""
        return """思考过程：
1. 首先分析问题的关键点
   - 问题涉及的知识领域
   - 需要关注的核心概念

2. 然后逐步推理
   - 根据已知信息进行逻辑推导
   - 考虑不同的可能性

3. 最后得出结论
   - 综合分析结果
   - 给出明确答案

答案：
[LLM 服务不可用，请配置 DEEPSEEK_API_KEY 环境变量]
"""

    def _parse_cot_response(self, response: str) -> tuple:
        """解析CoT响应

        Args:
            response: 模型响应文本

        Returns:
            (推理步骤列表, 最终答案)
        """
        steps = []
        answer = response

        # 尝试分离思考过程和答案
        if "思考过程：" in response or "思考过程:" in response:
            parts = (
                response.split("答案：", 1)
                if "答案：" in response
                else response.split("答案:", 1) if "答案:" in response else [response, ""]
            )

            if len(parts) == 2:
                thought_section, answer_section = parts
                answer = answer_section.strip()

                # 解析推理步骤
                thought_lines = thought_section.strip().split("\n")
                step_num = 0
                current_step = []

                for line in thought_lines:
                    if line.strip().startswith(f"{step_num + 1}."):
                        if current_step:
                            steps.append(
                                ReasoningStep(
                                    step_number=step_num, content="\n".join(current_step).strip()
                                )
                            )
                        step_num += 1
                        current_step = [line]
                    elif current_step:
                        current_step.append(line)

                if current_step:
                    steps.append(
                        ReasoningStep(step_number=step_num, content="\n".join(current_step).strip())
                    )

        # 如果没有解析出步骤，创建一个默认步骤
        if not steps:
            steps.append(ReasoningStep(step_number=1, content=response[:500]))

        return steps, answer

    def _calculate_confidence(self, steps: List[ReasoningStep], answer: str) -> float:
        """计算置信度

        Args:
            steps: 推理步骤
            answer: 答案

        Returns:
            置信度分数 (0-1)
        """
        # 基于推理步骤数量和答案完整性估算
        step_score = min(len(steps) * 0.15, 0.5)
        answer_score = min(len(answer) / 500, 0.5)

        return round(min(step_score + answer_score, 1.0), 2)
