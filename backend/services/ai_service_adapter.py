"""
AI Service Adapter - Unified AI Service via CLIProxyAPI

Provides a unified interface to multiple AI models through CLIProxyAPI:
- Claude (Sonnet, Haiku, Opus)
- Gemini (Flash, Pro)
- DeepSeek (Chat, Reasoner)
- Qwen (Chat, Plus)
"""

import logging
import os
from enum import Enum
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ModelProvider(str, Enum):
    """AI Model Providers"""

    CLAUDE = "claude"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"


class TaskType(str, Enum):
    """Task Types for Model Selection"""

    REASONING = "reasoning"
    CODING = "coding"
    CHAT = "chat"
    CHINESE = "chinese"
    MULTIMODAL = "multimodal"
    ANALYSIS = "analysis"
    SUMMARIZATION = "summarization"


class ModelSelector:
    """Select the best model for a given task"""

    # Task to model mapping
    TASK_MODEL_MAPPING = {
        TaskType.REASONING: {
            "primary": "claude-opus",
            "fallback": "claude-sonnet",
            "reason": "Best reasoning quality",
        },
        TaskType.CODING: {
            "primary": "claude-sonnet",
            "fallback": "deepseek-chat",
            "reason": "Strong coding capabilities",
        },
        TaskType.CHAT: {
            "primary": "deepseek-chat",
            "fallback": "qwen-chat",
            "reason": "Cost-effective for chat",
        },
        TaskType.CHINESE: {
            "primary": "qwen-chat",
            "fallback": "gemini-flash",
            "reason": "Best Chinese language support",
        },
        TaskType.MULTIMODAL: {
            "primary": "gemini-flash",
            "fallback": "claude-sonnet",
            "reason": "Fast multimodal processing",
        },
        TaskType.ANALYSIS: {
            "primary": "claude-sonnet",
            "fallback": "deepseek-reasoner",
            "reason": "Strong analytical capabilities",
        },
        TaskType.SUMMARIZATION: {
            "primary": "deepseek-chat",
            "fallback": "qwen-chat",
            "reason": "Good summarization at low cost",
        },
    }

    # Model aliases (configured in CLIProxyAPI)
    MODEL_ALIASES = {
        # Claude models
        "claude-opus": "claude-3-5-sonnet-20241022",  # Opus 4.6
        "claude-sonnet": "claude-3-5-sonnet-20241022",
        "claude-haiku": "claude-3-5-haiku-20241022",
        # Gemini models
        "gemini-flash": "gemini-2.0-flash-exp",
        "gemini-pro": "gemini-1.5-pro",
        # DeepSeek models
        "deepseek-chat": "deepseek-chat",
        "deepseek-reasoner": "deepseek-reasoner",
        # Qwen models
        "qwen-chat": "qwen-plus",
        "qwen-plus": "qwen-plus",
    }

    @classmethod
    def select_for_task(cls, task_type: TaskType) -> str:
        """Select model for a given task"""
        if task_type not in cls.TASK_MODEL_MAPPING:
            logger.warning(f"Unknown task type: {task_type}, using default")
            task_type = TaskType.CHAT

        mapping = cls.TASK_MODEL_MAPPING[task_type]
        return cls.MODEL_ALIASES[mapping["primary"]]

    @classmethod
    def get_fallback(cls, task_type: TaskType) -> str:
        """Get fallback model for a given task"""
        if task_type not in cls.TASK_MODEL_MAPPING:
            task_type = TaskType.CHAT

        mapping = cls.TASK_MODEL_MAPPING[task_type]
        return cls.MODEL_ALIASES[mapping["fallback"]]


class AIServiceAdapter:
    """
    AI Service Adapter

    Provides unified interface to multiple AI models through CLIProxyAPI.
    Handles model selection, load balancing, and fallback logic.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        """
        Initialize AI Service Adapter

        Args:
            base_url: CLIProxyAPI base URL (default: http://localhost:8317/v1)
            api_key: API key for CLIProxyAPI (default: lingzhi-api-key-001)
            default_model: Default model to use (default: deepseek-chat)
        """
        self.base_url = base_url or os.getenv("CLIPROXYAPI_BASE_URL", "http://localhost:8317/v1")
        self.api_key = api_key or os.getenv("CLIPROXYAPI_API_KEY", "lingzhi-api-key-001")
        self.default_model = default_model or os.getenv("DEFAULT_AI_MODEL", "deepseek-chat")

        # Initialize OpenAI client (compatible with CLIProxyAPI)
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

        logger.info(f"AI Service Adapter initialized: {self.base_url}")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Send chat completion request

        Args:
            messages: Chat messages
            model: Model to use (auto-selected if not provided)
            task_type: Task type for model selection
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Response dict with content, usage, model
        """
        # Select model
        if not model:
            if task_type:
                model = ModelSelector.select_for_task(task_type)
            else:
                model = self.default_model

        logger.info(f"AI Request: model={model}, task_type={task_type}")

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "finish_reason": response.choices[0].finish_reason,
            }

        except Exception as e:
            logger.error(f"AI request failed: {e}")

            # Try fallback model
            if task_type:
                fallback_model = ModelSelector.get_fallback(task_type)
                logger.info(f"Trying fallback model: {fallback_model}")

                try:
                    response = await self.client.chat.completions.create(
                        model=fallback_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs,
                    )

                    return {
                        "content": response.choices[0].message.content,
                        "model": response.model,
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens,
                        },
                        "finish_reason": response.choices[0].finish_reason,
                    }

                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {fallback_error}")
                    raise

            raise

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        temperature: float = 0.7,
        **kwargs,
    ):
        """
        Stream chat completion

        Args:
            messages: Chat messages
            model: Model to use
            task_type: Task type for model selection
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Yields:
            Response chunks
        """
        if not model:
            if task_type:
                model = ModelSelector.select_for_task(task_type)
            else:
                model = self.default_model

        logger.info(f"AI Stream Request: model={model}")

        stream = await self.client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, stream=True, **kwargs
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def embed(self, text: str, model: str = "text-embedding-3-small") -> List[float]:
        """
        Generate text embedding

        Args:
            text: Text to embed
            model: Embedding model

        Returns:
            Embedding vector
        """
        try:
            response = await self.client.embeddings.create(model=model, input=text)

            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise

    async def count_tokens(self, text: str, model: str = "deepseek-chat") -> int:
        """
        Estimate token count for text

        Args:
            text: Text to count
            model: Model for tokenization

        Returns:
            Estimated token count
        """
        # Rough estimation: 1 token ≈ 4 characters for Chinese
        # More accurate would require tiktoken
        return len(text) // 4


class UnifiedAIService:
    """
    Unified AI Service for the ZhiNeng Knowledge System

    Provides high-level AI operations using CLIProxyAPI:
    - RAG (Retrieval-Augmented Generation)
    - Audio transcription analysis
    - Text summarization
    - Semantic search
    """

    def __init__(self):
        self.adapter = AIServiceAdapter()

    async def rag_query(
        self, query: str, context: List[Dict[str, Any]], max_tokens: int = 2000
    ) -> str:
        """
        RAG query with context

        Args:
            query: User query
            context: Retrieved context chunks
            max_tokens: Maximum tokens in response

        Returns:
            Generated answer
        """
        # Build context string
        context_str = "\n\n".join(
            [
                f"【{chunk.get('title', 'Document')}】\n{chunk.get('content', '')}"
                for chunk in context[:5]  # Top 5 chunks
            ]
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "你是灵知系统的智能助手。基于提供的上下文回答用户问题。\n"
                    "如果上下文不足以回答问题，请诚实说明。\n"
                    "回答要准确、清晰、有礼貌。"
                ),
            },
            {"role": "user", "content": f"上下文：\n{context_str}\n\n问题：{query}"},
        ]

        response = await self.adapter.chat(
            messages=messages, task_type=TaskType.CHINESE, max_tokens=max_tokens
        )

        return response["content"]

    async def summarize_audio_transcript(self, transcript: str, max_length: int = 500) -> str:
        """
        Summarize audio transcript

        Args:
            transcript: Audio transcript text
            max_length: Maximum summary length

        Returns:
            Summary text
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个专业的内容摘要助手。"
                    "请简洁地总结音频转录的主要内容，"
                    "保留关键信息和要点。"
                ),
            },
            {
                "role": "user",
                "content": f"请总结以下音频转录（不超过{max_length}字）：\n\n{transcript}",
            },
        ]

        response = await self.adapter.chat(
            messages=messages,
            task_type=TaskType.SUMMARIZATION,
            max_tokens=max_length * 2,  # Account for tokens
        )

        return response["content"]

    async def extract_teaching_points(self, transcript: str) -> List[Dict[str, Any]]:
        """
        Extract teaching points from transcript

        Args:
            transcript: Audio transcript text

        Returns:
            List of teaching points with timestamps
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个教学内容分析助手。"
                    "从音频转录中提取教学要点，每个要点包含："
                    "1. 标题（简短）"
                    "2. 时间戳（基于转录内容估算）"
                    "3. 详细说明"
                    "返回JSON格式的列表。"
                ),
            },
            {"role": "user", "content": f"请提取以下音频转录的教学要点：\n\n{transcript}"},
        ]

        response = await self.adapter.chat(
            messages=messages, task_type=TaskType.ANALYSIS, max_tokens=3000
        )

        # Parse JSON response
        import json

        try:
            return json.loads(response["content"])
        except json.JSONDecodeError:
            logger.error("Failed to parse teaching points JSON")
            return []

    async def correct_asr_errors(self, transcript: str, domain: str = "general") -> str:
        """
        Correct ASR errors in transcript

        Args:
            transcript: Raw ASR transcript
            domain: Domain context (e.g., "qigong", "teaching", "medical")

        Returns:
            Corrected transcript
        """
        domain_hints = {
            "qigong": "智能气功、混元灵通、组场、发气",
            "teaching": "教学、学习、课程、练习",
            "medical": "治疗、康复、健康、病症",
        }

        hints = domain_hints.get(domain, "")

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个ASR错误纠正助手。"
                    f"领域：{domain}"
                    f"关键词：{hints}\n"
                    "请纠正转录中的明显错误，但保持原意不变。"
                ),
            },
            {"role": "user", "content": f"请纠正以下转录：\n\n{transcript}"},
        ]

        response = await self.adapter.chat(
            messages=messages,
            task_type=TaskType.CHINESE,
            temperature=0.3,  # Lower temperature for more accurate correction
        )

        return response["content"]
