"""Cohere Transcribe 本地 ASR 引擎

使用 CohereLabs/cohere-transcribe-03-2026 进行本地语音转写。
支持中文、长音频自动分片、批量推理。
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL_ID = "CohereLabs/cohere-transcribe-03-2026"
DEFAULT_LANGUAGE = "zh"
DEFAULT_MAX_NEW_TOKENS = 512


class CohereTranscriber:
    """Cohere Transcribe 本地转写引擎

    使用 2B 参数 Conformer 模型进行离线 ASR。
    支持 14 种语言，包括中文普通话。
    """

    def __init__(
        self,
        model_id: str = MODEL_ID,
        device: Optional[str] = None,
        language: str = DEFAULT_LANGUAGE,
        compile_encoder: bool = False,
    ):
        self._model_id = model_id
        self._language = language
        self._compile_encoder = compile_encoder
        self._device = device or ("cuda:0" if _torch_cuda_available() else "cpu")
        self._processor = None
        self._model = None
        self._initialized = False

    def _ensure_initialized(self):
        """延迟初始化模型"""
        if self._initialized:
            return

        from transformers import AutoProcessor, CohereAsrForConditionalGeneration

        logger.info(f"Loading Cohere Transcribe model on {self._device}...")
        t0 = time.time()

        self._processor = AutoProcessor.from_pretrained(self._model_id)
        self._model = CohereAsrForConditionalGeneration.from_pretrained(
            self._model_id,
            device_map=self._device,
        )
        self._model.eval()

        elapsed = time.time() - t0
        logger.info(f"Cohere Transcribe loaded in {elapsed:.1f}s (device={self._device})")
        self._initialized = True

    def transcribe_file(
        self,
        audio_path: str,
        language: Optional[str] = None,
        punctuation: bool = True,
    ) -> Dict[str, Any]:
        """转写单个音频文件

        Args:
            audio_path: 音频文件路径
            language: 语言代码 (默认 zh)
            punctuation: 是否输出标点

        Returns:
            {"text": str, "duration": float, "rtfx": float}
        """
        self._ensure_initialized()

        from transformers.audio_utils import load_audio

        lang = language or self._language
        audio = load_audio(audio_path, sampling_rate=16000)
        duration = len(audio) / 16000.0

        inputs = self._processor(
            audio,
            sampling_rate=16000,
            return_tensors="pt",
            language=lang,
            punctuation=punctuation,
        )
        audio_chunk_index = inputs.get("audio_chunk_index")
        inputs = inputs.to(self._model.device, dtype=self._model.dtype)

        t0 = time.time()
        outputs = self._model.generate(**inputs, max_new_tokens=DEFAULT_MAX_NEW_TOKENS)
        texts = self._processor.decode(
            outputs,
            skip_special_tokens=True,
            audio_chunk_index=audio_chunk_index,
            language=lang,
        )
        elapsed = time.time() - t0

        if isinstance(texts, list):
            text = texts[0] if texts else ""
        else:
            text = texts

        rtfx = duration / elapsed if elapsed > 0 else 0

        return {
            "text": text.strip(),
            "duration": duration,
            "elapsed": elapsed,
            "rtfx": rtfx,
        }

    def transcribe_batch(
        self,
        audio_paths: List[str],
        language: Optional[str] = None,
        punctuation: bool = True,
    ) -> List[Dict[str, Any]]:
        """批量转写音频文件

        Args:
            audio_paths: 音频文件路径列表
            language: 语言代码
            punctuation: 是否输出标点

        Returns:
            转写结果列表
        """
        self._ensure_initialized()

        from transformers.audio_utils import load_audio

        lang = language or self._language

        audios = []
        durations = []
        for p in audio_paths:
            audio = load_audio(p, sampling_rate=16000)
            audios.append(audio)
            durations.append(len(audio) / 16000.0)

        inputs = self._processor(
            audios,
            sampling_rate=16000,
            return_tensors="pt",
            language=lang,
            punctuation=punctuation,
        )
        audio_chunk_index = inputs.get("audio_chunk_index")
        inputs = inputs.to(self._model.device, dtype=self._model.dtype)

        t0 = time.time()
        outputs = self._model.generate(**inputs, max_new_tokens=DEFAULT_MAX_NEW_TOKENS)
        texts = self._processor.decode(
            outputs,
            skip_special_tokens=True,
            audio_chunk_index=audio_chunk_index,
            language=lang,
        )
        elapsed = time.time() - t0

        if isinstance(texts, str):
            texts = [texts]

        results = []
        for i, (text, dur) in enumerate(zip(texts, durations)):
            file_elapsed = elapsed / len(audio_paths)
            results.append(
                {
                    "text": text.strip() if text else "",
                    "duration": dur,
                    "elapsed": file_elapsed,
                    "rtfx": dur / file_elapsed if file_elapsed > 0 else 0,
                    "file": audio_paths[i],
                }
            )

        return results

    def transcribe_directory(
        self,
        audio_dir: str,
        extensions: Optional[set] = None,
        language: Optional[str] = None,
        batch_size: int = 1,
        max_files: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """批量转写目录下所有音频文件

        Args:
            audio_dir: 音频目录
            extensions: 文件扩展名集合
            language: 语言代码
            batch_size: 批处理大小
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

        for i in range(0, len(files), batch_size):
            batch = files[i : i + batch_size]
            batch_paths = [str(f) for f in batch]

            try:
                if len(batch) == 1:
                    r = self.transcribe_file(batch_paths[0], language=language)
                    r["file"] = batch_paths[0]
                    results.append(r)
                else:
                    batch_results = self.transcribe_batch(batch_paths, language=language)
                    results.extend(batch_results)

                done = min(i + batch_size, len(files))
                logger.info(
                    f"  [{done}/{len(files)}] "
                    f"{batch[0].name} -> {results[-1].get('text', '')[:40]}..."
                )

            except Exception as e:
                logger.error(f"Failed to transcribe batch starting at {batch[0]}: {e}")
                for f in batch:
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
    def language(self) -> str:
        return self._language


def _torch_cuda_available() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False
