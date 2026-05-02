"""
OCR 模块

提供图像文本识别功能，基于 Tesseract OCR。
"""

from .ocr_engine import DocumentWithOCR, OCREngine

__all__ = [
    "OCREngine",
    "DocumentWithOCR",
]
