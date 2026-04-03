"""SenseVoice 本地 ASR 引擎

使用达摩院 SenseVoiceSmall 进行本地语音转写。
支持 50+ 语言识别 + 情感检测 + 音频事件检测。
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL_ID = "iic/SenseVoiceSmall"
DEFAULT_LANGUAGE = "zh"

EVENT_TAGS = {
    "<|SPOKEN_LANGUAGE|>": "spoken_language",
    "<|EMOTION|>": "emotion",
    "<|EVENT|>": "audio_event",
}


class SenseVoiceTranscriber:
    """SenseVoice 本地转写引擎

    SenseVoiceSmall 是达摩院推出的多语言语音理解模型，
    除文字转写外还支持：
    - 情感识别（HAPPY/SAD/ANGRY/NEUTRAL）
    - 音频事件检测（LAUGHTER/APPLAUSE/MUSIC 等）
    - 语种识别（50+ 语言）

    约 230M 参数，推理速度极快。
    """

    def __init__(
        self,
        model_id: str = MODEL_ID,
        device: Optional[str] = None,
        language: str = DEFAULT_LANGUAGE,
        disable_pbar: bool = True,
        ncpu: int = 4,
    ):
        self._model_id = model_id
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

        logger.info(f"Loading SenseVoice {self._model_id} on {self._device}...")
        t0 = time.time()
        self._model = AutoModel(
            model=self._model_id,
            device=self._device,
            disable_pbar=self._disable_pbar,
            ncpu=self._ncpu,
        )
        elapsed = time.time() - t0
        logger.info(f"SenseVoice {self._model_id} loaded in {elapsed:.1f}s (device={self._device})")
        self._initialized = True

    @staticmethod
    def _parse_rich_text(raw_text: str) -> Dict[str, Any]:
        """解析 SenseVoice 富文本输出中的情感和事件标签

        SenseVoice 输出格式示例：
            <|SPOKEN_LANGUAGE|>zh<|EMOTION|>HAPPY<|EVENT|>LAUGHTER<|/EVENT|>你好世界

        Returns:
            {"text": str, "emotion": str|None, "audio_events": list, "language_detected": str|None}
        """
        text = raw_text
        emotion = None
        audio_events = []
        language_detected = None

        import re

        event_pattern = re.compile(r"<\|EVENT\|>(.*?)<\|/EVENT\|>")
        for match in event_pattern.finditer(text):
            audio_events.append(match.group(1).strip())
        text = event_pattern.sub("", text)

        emo_pattern = re.compile(r"<\|EMOTION\|>(\w+)")
        emo_match = emo_pattern.search(text)
        if emo_match:
            emotion = emo_match.group(1)
        text = emo_pattern.sub("", text)

        lang_pattern = re.compile(r"<\|SPOKEN_LANGUAGE\|>(\w+)")
        lang_match = lang_pattern.search(text)
        if lang_match:
            language_detected = lang_match.group(1)
        text = lang_pattern.sub("", text)

        tag_pattern = re.compile(r"<\|[^|]*\|>")
        text = tag_pattern.sub("", text)

        return {
            "text": text.strip(),
            "emotion": emotion,
            "audio_events": audio_events,
            "language_detected": language_detected,
        }

    def transcribe_file(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """转写单个音频文件

        Args:
            audio_path: 音频文件路径
            language: 语言代码（默认 zh）

        Returns:
            {"text": str, "duration": float, "elapsed": float, "rtfx": float,
             "emotion": str|None, "audio_events": list, "language_detected": str|None}
        """
        self._ensure_initialized()

        import torchaudio

        t0 = time.time()
        result = self._model.generate(input=audio_path, batch_size_s=300)
        elapsed = time.time() - t0

        raw_text = ""
        if result and len(result) > 0:
            item = result[0]
            if isinstance(item, dict):
                raw_text = item.get("text", "")
            elif isinstance(item, (list, tuple)) and len(item) > 0:
                entry = item[0]
                if isinstance(entry, dict):
                    raw_text = entry.get("text", str(entry))
                else:
                    raw_text = str(entry)
            else:
                raw_text = str(item)

        parsed = self._parse_rich_text(raw_text)

        try:
            info = torchaudio.info(audio_path)
            duration = info.num_frames / info.sample_rate
        except Exception:
            duration = 0.0

        rtfx = duration / elapsed if elapsed > 0 else 0

        return {
            "text": parsed["text"],
            "duration": duration,
            "elapsed": elapsed,
            "rtfx": rtfx,
            "emotion": parsed["emotion"],
            "audio_events": parsed["audio_events"],
            "language_detected": parsed["language_detected"],
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
