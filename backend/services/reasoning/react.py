"""ReAct 推理模块

实现 ReAct (Reasoning + Acting) 模式，让模型在推理过程中执行行动
"""

import time
import re
import asyncio
from typing import List, Dict, Any, Optional
import logging

import httpx

from .base import BaseReasoner, ReasoningResult, ReasoningStep, QueryType

logger = logging.getLogger(__name__)


class ReActReasoner(BaseReasoner):
    """ReAct 推理器

    结合推理和行动，在推理过程中可以执行工具调用
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
                        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
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
        self,
        question: str,
        context: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[Dict[str, Any]] = None,
        max_iterations: int = 5,
        **kwargs
    ) -> ReasoningResult:
        """执行ReAct推理

        Args:
            question: 用户问题
            context: 上下文文档
            tools: 可用工具字典
            max_iterations: 最大推理迭代次数
            **kwargs: 其他参数

        Returns:
            推理结果
        """
        start_time = time.time()

        # 分析问题类型
        query_type = self.analyze_query(question)

        # 初始化工具
        available_tools = tools or self._default_tools(context)

        # ReAct循环
        steps = []
        current_context = f"问题：{question}\n\n"

        if context:
            current_context += f"参考上下文：\n{self.format_context(context)}\n\n"

        for iteration in range(max_iterations):
            # 构建提示词
            prompt = self._build_react_prompt(
                question,
                current_context,
                available_tools,
                iteration > 0
            )

            # 调用LLM获取下一步行动
            response = await self._call_llm(
                prompt,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 1000)
            )

            # 解析响应
            thought, action, action_input = self._parse_react_response(response)

            # 创建推理步骤
            step = ReasoningStep(
                step_number=iteration + 1,
                content=thought or "",
                action=action,
                observation=None
            )
            steps.append(step)

            # 检查是否完成
            if action == "finish" or action == "answer":
                step.observation = action_input or "推理完成"
                break

            # 执行行动
            if action and action in available_tools:
                observation = await self._execute_tool(
                    action,
                    action_input,
                    available_tools[action]
                )
                step.observation = observation
                current_context += f"执行 {action}: {action_input}\n观察: {observation}\n\n"
            elif action:
                step.observation = f"未知工具: {action}"

        # 生成最终答案
        answer = await self._generate_final_answer(question, steps, context)

        reasoning_time = time.time() - start_time

        return ReasoningResult(
            answer=answer,
            query_type=query_type,
            steps=steps,
            sources=context or [],
            confidence=self._calculate_confidence(steps),
            reasoning_time=reasoning_time,
            model_used=self.model_name
        )

    def _default_tools(self, context: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """定义默认工具集

        Args:
            context: 上下文文档

        Returns:
            工具字典
        """
        tools = {}

        # 搜索工具
        async def search_tool(query: str) -> str:
            if context:
                results = [
                    f"- {doc.get('title', '')}: {doc.get('content', '')[:100]}..."
                    for doc in context[:3]
                    if query.lower() in doc.get('content', '').lower() or
                       query.lower() in doc.get('title', '').lower()
                ]
                return "\n".join(results) if results else "未找到相关内容"
            return "无可用上下文"

        # 知识查询工具
        async def knowledge_lookup(topic: str) -> str:
            if context:
                for doc in context:
                    if topic.lower() in doc.get('title', '').lower():
                        return f"{doc.get('title', '')}: {doc.get('content', '')[:200]}"
            return f"未找到关于'{topic}'的知识"

        tools["search"] = {
            "description": "在知识库中搜索相关信息",
            "function": search_tool
        }

        tools["lookup"] = {
            "description": "查找特定主题的知识",
            "function": knowledge_lookup
        }

        return tools

    def _build_react_prompt(
        self,
        question: str,
        context: str,
        tools: Dict[str, Any],
        has_history: bool
    ) -> str:
        """构建ReAct提示词

        Args:
            question: 用户问题
            context: 当前上下文
            tools: 可用工具
            has_history: 是否有历史记录

        Returns:
            提示词字符串
        """
        tools_desc = "\n".join([
            f"- {name}: {info['description']}"
            for name, info in tools.items()
        ])

        if has_history:
            return f"""继续以下推理过程（{context}）

可用工具：
{tools_desc}

请按照以下格式回复：
思考：[你的思考过程]
行动：[工具名称或finish]
行动输入：[工具参数或最终答案]
"""
        else:
            return f"""使用ReAct模式回答以下问题：

{context}

可用工具：
{tools_desc}

请按照以下格式回复：
思考：[你的思考过程]
行动：[工具名称或finish]
行动输入：[工具参数或最终答案]

示例：
思考：我需要搜索关于八段锦的信息
行动：search
行动输入：八段锦
"""

    async def _call_llm(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """调用大语言模型"""
        if not self.api_key:
            return self._mock_response()

        try:
            client = await self._get_client()
            response = await client.post(
                self.api_url or "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一个使用ReAct模式的推理助手。"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return self._mock_response()

    def _mock_response(self) -> str:
        """模拟响应"""
        return """思考：这是一个复杂的问题，我需要搜索相关信息
行动：finish
行动输入：这是一个模拟的回答结果。实际使用需要配置DEEPSEEK_API_KEY环境变量。"""

    def _parse_react_response(self, response: str) -> tuple:
        """解析ReAct响应

        Args:
            response: 模型响应

        Returns:
            (思考, 行动, 行动输入)
        """
        thought = ""
        action = "finish"
        action_input = ""

        # 提取思考
        thought_match = re.search(r'思考[：:]\s*(.+?)(?=\n行动[：:]|$)', response, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        # 提取行动
        action_match = re.search(r'行动[：:]\s*(\w+)', response)
        if action_match:
            action = action_match.group(1).strip()

        # 提取行动输入
        input_match = re.search(r'行动输入[：:]\s*(.+)', response, re.DOTALL)
        if input_match:
            action_input = input_match.group(1).strip()

        return thought, action, action_input

    async def _execute_tool(
        self,
        action: str,
        action_input: str,
        tool_info: Dict[str, Any]
    ) -> str:
        """执行工具

        Args:
            action: 工具名称
            action_input: 工具参数
            tool_info: 工具信息

        Returns:
            执行结果
        """
        try:
            if "function" in tool_info:
                if asyncio.iscoroutinefunction(tool_info["function"]):
                    return await tool_info["function"](action_input)
                else:
                    return tool_info["function"](action_input)
        except Exception as e:
            return f"工具执行错误: {str(e)}"

        return f"未知工具: {action}"

    async def _generate_final_answer(
        self,
        question: str,
        steps: List[ReasoningStep],
        context: Optional[List[Dict[str, Any]]]
    ) -> str:
        """生成最终答案

        Args:
            question: 原始问题
            steps: 推理步骤
            context: 上下文

        Returns:
            最终答案
        """
        # 从最后步骤获取答案
        if steps:
            last_step = steps[-1]
            if last_step.action == "finish" and last_step.observation:
                return last_step.observation

        # 生成摘要
        summary = f"基于{len(steps)}步推理，得出以下结论：\n\n"
        for i, step in enumerate(steps[:3], 1):
            if step.content:
                summary += f"{i}. {step.content[:100]}...\n"

        return summary

    def _calculate_confidence(self, steps: List[ReasoningStep]) -> float:
        """计算置信度"""
        if not steps:
            return 0.3

        # 基于完成的推理步骤和是否有行动执行
        completed_actions = sum(1 for s in steps if s.action and s.action != "finish")
        base_confidence = min(len(steps) * 0.1, 0.5)
        action_bonus = min(completed_actions * 0.15, 0.3)

        return round(min(base_confidence + action_bonus, 1.0), 2)
