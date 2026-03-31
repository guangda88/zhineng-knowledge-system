"""人机交互标注服务模块

提供OCR和语音转录的标注功能，通过人工校正提升识别精度：
- OCR文本标注
- 语音转写标注
- 标注数据管理
- 模型精调
"""

from .ocr_annotator import OCRAnnotator
from .transcription_annotator import TranscriptionAnnotator
from .annotation_manager import AnnotationManager

__all__ = [
    "OCRAnnotator",
    "TranscriptionAnnotator",
    "AnnotationManager",
]
