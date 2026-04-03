"""FunASR (Paraformer) 本地 ASR 引擎

使用阿达摩院 FunASR Paraformer-zh 进行本地语音转写。
中文最优精度，~220M 参数，速度快，自带标点恢复。
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL_ID = "paraformer-zh"
PUNC_MODEL_ID = "ct-punc"
DEFAULT_LANGUAGE = "zh"


class FunASRTranscriber:
    """FunASR Paraformer 本地转写引擎

    Paraformer-zh 是达摩院推出的非自回归端到端语音识别模型，
    中文识别精度业界领先，推理速度极快。

    可选加载标点恢复模型 ct-punc，自动为转写结果添加标点。
    """

    def __init__(
        self,
        model_id: str = MODEL_ID,
        punc_model_id: Optional[str] = PUNC_MODEL_ID,
        device: Optional[str] = None,
        language: str = DEFAULT_LANGUAGE,
        disable_pbar: bool = True,
        ncpu: int = 4,
    ):
        self._model_id = model_id
        self._punc_model_id = punc_model_id
        self._language = language
        self._device = device or ("cuda:0" if _torch_cuda_available() else "cpu")
        self._disable_pbar = disable_pbar
        self._ncpu = ncpu
        self._model = None
        self._initialized = False

    def _ensure_initialized(self):
        """延迟初始化模型"""
        if self._initialized:
            return

        from funasr import AutoModel

        model_kwargs = {
            "model": self._model_id,
            "device": self._device,
            "disable_pbar": self._disable_pbar,
            "ncpu": self._ncpu,
        }
        if self._punc_model_id:
            model_kwargs["punc_model"] = self._punc_model_id

        logger.info(f"Loading FunASR {self._model_id} on {self._device}...")
        t0 = time.time()
        self._model = AutoModel(**model_kwargs)
        elapsed = time.time() - t0
        logger.info(f"FunASR {self._model_id} loaded in {elapsed:.1f}s (device={self._device})")
        self._initialized = True

    def transcribe_file(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """转写单个音频文件

        Args:
            audio_path: 音频文件路径
            language: 语言代码（默认 zh，Paraformer 以中文为主）

        Returns:
            {"text": str, "duration": float, "elapsed": float, "rtfx": float}
        """
        self._ensure_initialized()

        import torchaudio

        t0 = time.time()
        result = self._model.generate(input=audio_path, batch_size_s=300)
        elapsed = time.time() - t0

        text = ""
        if result and len(result) > 0:
            item = result[0]
            if isinstance(item, dict):
                text = item.get("text", "")
            elif isinstance(item, (list, tuple)) and len(item) > 0:
                entry = item[0]
                if isinstance(entry, dict):
                    text = entry.get("text", str(entry))
                else:
                    text = str(entry)
            else:
                text = str(item)

        try:
            info = torchaudio.info(audio_path)
            duration = info.num_frames / info.sample_rate
        except Exception:
            duration = 0.0

        rtfx = duration / elapsed if elapsed > 0 else 0

        return {
            "text": text.strip(),
            "duration": duration,
            "elapsed": elapsed,
            "rtfx": rtfx,
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
    def language(self) -> str:
        return self._language


def _torch_cuda_available() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False
