"""ASR 路由 - 多引擎转写切换

支持引擎：
- whisper: OpenAI Whisper（本地，无需账号，带时间戳）
- cohere: Cohere Transcribe（本地，需 HF Token + gated repo 权限）
- funasr: FunASR Paraformer-zh（本地，中文最优精度，~220M 参数）
- sensevoice: SenseVoiceSmall（本地，多语言+情感+音频事件检测，~230M 参数）
- tingwu: 阿里云听悟（云端，需 AccessKey）

使用方式：
    router = ASRRouter()
    result = router.transcribe(file_path, engine="funasr", language="zh")
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ENGINE_WHISPER = "whisper"
ENGINE_COHERE = "cohere"
ENGINE_FUNASR = "funasr"
ENGINE_SENSEVOICE = "sensevoice"
ENGINE_TINGWU = "tingwu"

AVAILABLE_ENGINES = [
    ENGINE_WHISPER,
    ENGINE_COHERE,
    ENGINE_FUNASR,
    ENGINE_SENSEVOICE,
    ENGINE_TINGWU,
]
DEFAULT_ENGINE = ENGINE_WHISPER


class ASRRouter:
    """ASR 多引擎路由

    懒加载各引擎，按需初始化。通过 engine 参数切换。
    """

    def __init__(self):
        self._instances: Dict[str, object] = {}

    def _get_whisper(self):
        if "whisper" not in self._instances:
            from .whisper_transcriber import WhisperTranscriber

            self._instances["whisper"] = WhisperTranscriber()
        return self._instances["whisper"]

    def _get_cohere(self):
        if "cohere" not in self._instances:
            from .cohere_transcriber import CohereTranscriber

            self._instances["cohere"] = CohereTranscriber()
        return self._instances["cohere"]

    def _get_funasr(self):
        if "funasr" not in self._instances:
            from .funasr_transcriber import FunASRTranscriber

            self._instances["funasr"] = FunASRTranscriber()
        return self._instances["funasr"]

    def _get_sensevoice(self):
        if "sensevoice" not in self._instances:
            from .sensevoice_transcriber import SenseVoiceTranscriber

            self._instances["sensevoice"] = SenseVoiceTranscriber()
        return self._instances["sensevoice"]

    def _get_engine(self, engine: str):
        if engine == ENGINE_WHISPER:
            return self._get_whisper()
        elif engine == ENGINE_COHERE:
            return self._get_cohere()
        elif engine == ENGINE_FUNASR:
            return self._get_funasr()
        elif engine == ENGINE_SENSEVOICE:
            return self._get_sensevoice()
        else:
            raise ValueError(f"未知的 ASR 引擎: {engine}. 可选: {', '.join(AVAILABLE_ENGINES)}")

    def transcribe(
        self,
        audio_path: str,
        engine: str = DEFAULT_ENGINE,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """转写音频文件

        Args:
            audio_path: 音频文件路径
            engine: 引擎名称 (whisper/cohere/funasr/sensevoice)
            language: 语言代码

        Returns:
            {"text", "duration", "elapsed", "rtfx", "segments"?}
        """
        eng = self._get_engine(engine)
        result = eng.transcribe_file(audio_path, language=language)
        result["engine"] = engine
        return result

    def transcribe_directory(
        self,
        audio_dir: str,
        engine: str = DEFAULT_ENGINE,
        language: Optional[str] = None,
        max_files: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """批量转写目录下所有音频文件"""
        eng = self._get_engine(engine)
        results = eng.transcribe_directory(audio_dir, language=language, max_files=max_files)
        for r in results:
            r["engine"] = engine
        return results

    def list_engines(self) -> List[Dict[str, Any]]:
        """列出所有可用引擎及其状态"""
        engines = []
        for name in AVAILABLE_ENGINES:
            info = {"name": name, "available": True, "error": None}
            if name == ENGINE_COHERE:
                try:
                    import transformers

                    hasattr(transformers, "CohereAsrForConditionalGeneration")
                except Exception:
                    info["available"] = False
            elif name in (ENGINE_FUNASR, ENGINE_SENSEVOICE):
                try:
                    import funasr  # noqa: F401
                except ImportError:
                    info["available"] = False
            engines.append(info)
        return engines
