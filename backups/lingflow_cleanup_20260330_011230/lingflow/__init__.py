"""LingFlow - Advanced Context Compression Library

提供智能上下文压缩功能，用于优化AI对话的token使用。
"""

from .compression import (
    AdvancedContextCompressor,
    CompressionResult,
    CompressionStrategy,
    compress_context,
    compress_messages,
    compress_text,
)

__version__ = "0.1.0"
__all__ = [
    "AdvancedContextCompressor",
    "CompressionStrategy",
    "CompressionResult",
    "compress_context",
    "compress_text",
    "compress_messages",
]
