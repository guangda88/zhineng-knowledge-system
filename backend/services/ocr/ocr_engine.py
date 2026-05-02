"""
OCR 引擎

使用 Tesseract OCR 进行图像文本识别。
支持中文和英文识别。
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

try:
    import pytesseract
    from PIL import Image

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logging.warning("pytesseract 或 Pillow 未安装，OCR 功能将不可用")

logger = logging.getLogger(__name__)


class OCREngine:
    """
    OCR 引擎

    使用 Tesseract OCR 进行图像文本提取。
    """

    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        language: str = "chi_sim+eng",
        max_workers: int = 4,
    ):
        """
        初始化 OCR 引擎

        Args:
            tesseract_cmd: Tesseract 可执行文件路径（可选）
            language: 识别语言（默认：中文简体+英文）
            max_workers: 线程池最大工作线程数
        """
        if not TESSERACT_AVAILABLE:
            raise RuntimeError("pytesseract 或 Pillow 未安装，OCR 功能不可用")

        # 配置 Tesseract 路径
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            logger.info(f"使用自定义 Tesseract 路径: {tesseract_cmd}")

        self.language = language
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        logger.info(f"OCR 引擎初始化成功 - 语言: {language}, 线程数: {max_workers}")

    async def recognize_image(
        self, image_path: str, config: Optional[str] = None
    ) -> Dict[str, any]:
        """
        识别图像中的文本

        Args:
            image_path: 图像文件路径
            config: Tesseract 配置选项（可选）

        Returns:
            识别结果: {
                "text": str,
                "confidence": float,
                "metadata": Dict,
                "status": "success" | "error",
                "error": Optional[str]
            }
        """
        if not os.path.exists(image_path):
            return {
                "text": "",
                "confidence": 0.0,
                "metadata": {},
                "status": "error",
                "error": f"图像文件不存在: {image_path}",
            }

        try:
            loop = asyncio.get_event_loop()

            def _recognize():
                # 默认配置
                tesseract_config = config or "--psm 6 --oem 3"

                # 获取文本和置信度
                data = pytesseract.image_to_data(
                    Image.open(image_path),
                    lang=self.language,
                    config=tesseract_config,
                    output_type=pytesseract.Output.DICT,
                )

                # 提取文本
                text = pytesseract.image_to_string(
                    Image.open(image_path), lang=self.language, config=tesseract_config
                )

                # 计算平均置信度
                confidences = [float(c) for c in data["conf"] if float(c) > 0]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

                # 提取元数据
                metadata = {
                    "language": self.language,
                    "num_words": len(text.split()),
                    "num_lines": len([l for l in text.split("\n") if l.strip()]),
                    "avg_confidence": avg_confidence,
                }

                return {
                    "text": text,
                    "confidence": avg_confidence,
                    "metadata": metadata,
                    "status": "success",
                }

            result = await loop.run_in_executor(self.executor, _recognize)
            logger.info(
                f"OCR 识别成功: {image_path} - {len(result['text'])} 字符, 置信度: {result['confidence']:.2f}"
            )
            return result

        except Exception as e:
            logger.error(f"OCR 识别失败 {image_path}: {e}", exc_info=True)
            return {
                "text": "",
                "confidence": 0.0,
                "metadata": {},
                "status": "error",
                "error": str(e),
            }

    async def recognize_batch(
        self, image_paths: List[str], config: Optional[str] = None
    ) -> List[Dict[str, any]]:
        """
        批量识别图像

        Args:
            image_paths: 图像文件路径列表
            config: Tesseract 配置选项（可选）

        Returns:
            识别结果列表
        """
        tasks = [self.recognize_image(path, config) for path in image_paths]
        return await asyncio.gather(*tasks)

    def extract_text_only(self, image_path: str, config: Optional[str] = None) -> str:
        """
        仅提取文本（轻量级，不返回置信度）

        Args:
            image_path: 图像文件路径
            config: Tesseract 配置选项（可选）

        Returns:
            文本内容
        """
        result = asyncio.run(self.recognize_image(image_path, config))
        return result.get("text", "")

    async def get_image_info(self, image_path: str) -> Dict[str, any]:
        """
        获取图像信息

        Args:
            image_path: 图像文件路径

        Returns:
            图像信息
        """
        try:
            loop = asyncio.get_event_loop()

            def _get_info():
                img = Image.open(image_path)
                return {
                    "width": img.width,
                    "height": img.height,
                    "mode": img.mode,
                    "format": img.format,
                    "size_bytes": os.path.getsize(image_path),
                    "aspect_ratio": img.width / img.height if img.height > 0 else 0,
                }

            return await loop.run_in_executor(self.executor, _get_info)

        except Exception as e:
            logger.error(f"获取图像信息失败 {image_path}: {e}", exc_info=True)
            return {}

    def is_supported_format(self, image_path: str) -> bool:
        """
        检查是否为支持的图像格式

        Args:
            image_path: 图像文件路径

        Returns:
            是否支持
        """
        supported_formats = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp"}
        ext = Path(image_path).suffix.lower()
        return ext in supported_formats

    async def close(self):
        """关闭 OCR 引擎，释放资源"""
        if self.executor:
            self.executor.shutdown(wait=True)
            logger.info("OCR 引擎已关闭")


class DocumentWithOCR:
    """
    带 OCR 支持的文档解析器

    将 OCR 功能集成到文档解析流程中。
    """

    def __init__(
        self,
        ocr_engine: OCREngine,
        enable_auto_ocr: bool = True,
        confidence_threshold: float = 60.0,
    ):
        """
        初始化

        Args:
            ocr_engine: OCR 引擎
            enable_auto_ocr: 是否自动对图像文件启用 OCR
            confidence_threshold: OCR 置信度阈值
        """
        self.ocr_engine = ocr_engine
        self.enable_auto_ocr = enable_auto_ocr
        self.confidence_threshold = confidence_threshold

    async def parse_image(self, image_path: str) -> Dict[str, any]:
        """
        解析图像文件（使用 OCR）

        Args:
            image_path: 图像文件路径

        Returns:
            解析结果
        """
        if not self.ocr_engine.is_supported_format(image_path):
            return {
                "content": "",
                "metadata": {},
                "status": "error",
                "error": f"不支持的图像格式: {image_path}",
            }

        # OCR 识别
        ocr_result = await self.ocr_engine.recognize_image(image_path)

        # 检查置信度
        if ocr_result["status"] == "success":
            if ocr_result["confidence"] < self.confidence_threshold:
                logger.warning(
                    f"OCR 置信度较低: {image_path} - {ocr_result['confidence']:.2f} < {self.confidence_threshold}"
                )

            # 合并图像信息和 OCR 结果
            image_info = await self.ocr_engine.get_image_info(image_path)
            ocr_result["metadata"].update(image_info)

        return ocr_result

    async def extract_text_from_pdf_images(
        self, pdf_path: str, temp_dir: Optional[str] = None
    ) -> Dict[str, any]:
        """
        从 PDF 中的图像提取文本（高级功能）

        注意：需要额外的依赖来提取 PDF 图像

        Args:
            pdf_path: PDF 文件路径
            temp_dir: 临时目录

        Returns:
            提取结果
        """
        # 这里可以实现 PDF 图像提取逻辑
        # 例如使用 pdf2image 库将 PDF 页面转换为图像，然后使用 OCR
        return {
            "content": "",
            "metadata": {},
            "status": "not_implemented",
            "error": "PDF 图像提取功能尚未实现",
        }
