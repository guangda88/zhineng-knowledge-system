"""Whisper 本地 ASR 引擎

使用 OpenAI Whisper 进行本地语音转写。
支持中文、长音频自动分段、带时间戳输出。
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL_SIZE = "medium"
DEFAULT_LANGUAGE = "zh"


class WhisperTranscriber:
    """Whisper 本地转写引擎

    模型大小选择（显存需求）：
    - tiny: ~39M, ~1GB VRAM
    - base: ~74M, ~1GB VRAM
    - small: ~244M, ~2GB VRAM
    - medium: ~769M, ~5GB VRAM（推荐 6GB 显卡）
    - large-v3: ~1.5G, ~10GB VRAM（6GB 卡需用 float16 + CPU fallback）
    """

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: Optional[str] = None,
        language: str = DEFAULT_LANGUAGE,
    ):
        self._model_size = model_size
        self._language = language
        self._device = device or ("cuda" if _torch_cuda_available() else "cpu")
        self._model = None
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return

        import whisper

        logger.info(f"Loading Whisper {self._model_size} on {self._device}...")
        t0 = time.time()
        self._model = whisper.load_model(self._model_size, device=self._device)
        elapsed = time.time() - t0
        logger.info(f"Whisper {self._model_size} loaded in {elapsed:.1f}s")
        self._initialized = True

    def transcribe_file(
        self,
        audio_path: str,
        language: Optional[str] = None,
        word_timestamps: bool = True,
    ) -> Dict[str, Any]:
        """转写单个音频文件

        Args:
            audio_path: 音频文件路径
            language: 语言代码（默认 zh）
            word_timestamps: 是否输出词级时间戳

        Returns:
            {
                "text": str,
                "duration": float,
                "elapsed": float,
                "rtfx": float,
                "segments": [{"start": float, "end": float, "text": str}],
            }
        """
        self._ensure_initialized()

        lang = language or self._language

        t0 = time.time()
        result = self._model.transcribe(
            audio_path,
            language=lang,
            word_timestamps=word_timestamps,
            fp16=(self._device == "cuda"),
        )
        elapsed = time.time() - t0

        text = result["text"].strip()
        duration = (
            result.get("segments", [{}])[-1].get("end", 0.0) if result.get("segments") else 0.0
        )

        segments = [
            {
                "start": round(seg["start"], 3),
                "end": round(seg["end"], 3),
                "text": seg["text"].strip(),
            }
            for seg in result.get("segments", [])
            if seg["text"].strip()
        ]

        rtfx = duration / elapsed if elapsed > 0 else 0

        return {
            "text": text,
            "duration": duration,
            "elapsed": elapsed,
            "rtfx": rtfx,
            "segments": segments,
        }

    def transcribe_directory(
        self,
        audio_dir: str,
        extensions: Optional[set] = None,
        language: Optional[str] = None,
        max_files: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """批量转写目录下所有音频文件

        Args:
            audio_dir: 音频目录
            extensions: 文件扩展名集合
            language: 语言代码
            max_files: 最大文件数

        Returns:
            转写结果列表
        """
        if extensions is None:
            extensions = {"mp3", "wav", "m4a", "flac", "ogg", "wma", "aac"}

        audio_dir = Path(audio_dir)
        files = sorted(
            f
            for f in audio_dir.iterdir()
            if f.is_file() and f.suffix.lstrip(".").lower() in extensions
        )

        if max_files:
            files = files[:max_files]

        if not files:
            logger.warning(f"No audio files found in {audio_dir}")
            return []

        logger.info(f"Transcribing {len(files)} files from {audio_dir}")
        results = []
        failed = []

        for i, f in enumerate(files, 1):
            try:
                r = self.transcribe_file(str(f), language=language)
                r["file"] = str(f)
                results.append(r)
                logger.info(
                    f"  [{i}/{len(files)}] {f.name} -> "
                    f"{r['text'][:50]}... (rtfx={r['rtfx']:.1f})"
                )
            except Exception as e:
                logger.error(f"Failed to transcribe {f}: {e}")
                failed.append({"file": str(f), "error": str(e)})

        logger.info(
            f"Transcription complete: {len(results)} succeeded, "
            f"{len(failed)} failed out of {len(files)} files"
        )
        return results

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def device(self) -> str:
        return self._device

    @property
    def model_size(self) -> str:
        return self._model_size


def _torch_cuda_available() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False
