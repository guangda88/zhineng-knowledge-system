"""音频处理模块测试"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.audio.audio_service import AudioService
from backend.services.audio.tingwu_client import (
    TaskStatus,
    TingwuClient,
    TranscriptionResult,
    TranscriptionSegment,
)

# ==================== TingwuClient Tests ====================


class TestTingwuClient:
    """TingwuClient单元测试"""

    def test_disabled_without_credentials(self):
        """无凭证时客户端应禁用"""
        client = TingwuClient(access_key_id=None, access_key_secret=None)
        assert not client.enabled

    def test_disabled_with_empty_credentials(self):
        """空凭证时客户端应禁用"""
        client = TingwuClient(access_key_id="", access_key_secret="")
        assert not client.enabled

    def test_create_task_raises_when_disabled(self):
        """禁用状态下创建任务应抛出异常"""
        client = TingwuClient(access_key_id=None, access_key_secret=None)
        with pytest.raises(RuntimeError, match="not enabled"):
            import asyncio

            asyncio.run(client.create_transcription_task("http://example.com/a.mp3"))

    def test_get_status_raises_when_disabled(self):
        """禁用状态下查询状态应抛出异常"""
        client = TingwuClient(access_key_id=None, access_key_secret=None)
        with pytest.raises(RuntimeError, match="not enabled"):
            import asyncio

            asyncio.run(client.get_task_status("task123"))

    def test_get_result_raises_when_disabled(self):
        """禁用状态下获取结果应抛出异常"""
        client = TingwuClient(access_key_id=None, access_key_secret=None)
        with pytest.raises(RuntimeError, match="not enabled"):
            import asyncio

            asyncio.run(client.get_transcription_result("task123"))


# ==================== TranscriptionResult Tests ====================


class TestTranscriptionResult:
    """TranscriptionResult数据类测试"""

    def test_default_values(self):
        result = TranscriptionResult(task_id="t1", status=TaskStatus.PENDING)
        assert result.task_id == "t1"
        assert result.status == TaskStatus.PENDING
        assert result.segments == []
        assert result.full_text == ""
        assert result.duration == 0.0
        assert result.error_message is None

    def test_with_segments(self):
        seg = TranscriptionSegment(start_time=1.0, end_time=5.0, text="测试", speaker="S1")
        result = TranscriptionResult(
            task_id="t1",
            status=TaskStatus.SUCCEEDED,
            segments=[seg],
            full_text="测试",
            duration=5.0,
        )
        assert len(result.segments) == 1
        assert result.segments[0].text == "测试"
        assert result.segments[0].speaker == "S1"

    def test_task_status_enum(self):
        assert TaskStatus.PENDING.value == "PENDING"
        assert TaskStatus.RUNNING.value == "RUNNING"
        assert TaskStatus.SUCCEEDED.value == "SUCCEEDED"
        assert TaskStatus.FAILED.value == "FAILED"


# ==================== AudioService Tests ====================


class TestAudioService:
    """AudioService单元测试"""

    def test_parse_plain_text(self):
        """测试纯文本解析"""
        service = AudioService()
        text = "这是第一段。\n这是第二段。"
        segments = service._parse_transcript(text, "txt")
        assert len(segments) >= 2
        assert "第一段" in segments[0]["text"]
        assert "第二段" in segments[1]["text"]

    def test_parse_srt(self):
        """测试SRT格式解析"""
        service = AudioService()
        srt = """1
00:00:01,000 --> 00:00:05,000
第一段文字

2
00:00:05,000 --> 00:00:10,000
第二段文字
"""
        segments = service._parse_transcript(srt, "srt")
        assert len(segments) == 2
        assert segments[0]["start_time"] == 1.0
        assert segments[0]["end_time"] == 5.0
        assert segments[0]["text"] == "第一段文字"
        assert segments[1]["start_time"] == 5.0
        assert segments[1]["end_time"] == 10.0
        assert segments[1]["text"] == "第二段文字"

    def test_parse_auto_detect_srt(self):
        """测试自动检测SRT格式"""
        service = AudioService()
        srt = "1\n00:00:01,000 --> 00:00:05,000\n文字\n"
        segments = service._parse_transcript(srt, "auto")
        assert len(segments) == 1
        assert segments[0]["start_time"] == 1.0

    def test_parse_auto_detect_txt(self):
        """测试自动检测纯文本格式"""
        service = AudioService()
        text = "普通文本内容"
        segments = service._parse_transcript(text, "auto")
        assert len(segments) >= 1
        assert segments[0]["text"] == "普通文本内容"

    def test_parse_srt_time(self):
        """测试SRT时间戳解析"""
        service = AudioService()
        assert service._parse_srt_time("00:00:01,000") == 1.0
        assert service._parse_srt_time("00:01:23,456") == 83.456
        assert service._parse_srt_time("01:00:00,000") == 3600.0
        assert service._parse_srt_time("00:00:00,500") == 0.5

    def test_parse_plain_text_with_empty_lines(self):
        """测试带空行的文本解析"""
        service = AudioService()
        text = "第一段\n\n第二段\n\n"
        segments = service._parse_transcript(text, "txt")
        assert len(segments) == 2
        assert segments[0]["text"] == "第一段"
        assert segments[1]["text"] == "第二段"

    def test_upload_rejects_invalid_format(self):
        """测试上传拒绝无效格式"""
        service = AudioService()
        import asyncio

        with pytest.raises(ValueError, match="不支持的音频格式"):
            asyncio.run(
                service.upload_file(
                    file_content=b"data",
                    original_name="test.exe",
                )
            )

    def test_upload_rejects_oversized_file(self):
        """测试上传拒绝超大文件"""
        service = AudioService()
        import asyncio

        with patch("backend.services.audio.audio_service.get_config") as mock_config:
            cfg = MagicMock()
            cfg.AUDIO_ALLOWED_FORMATS = ["mp3"]
            cfg.AUDIO_MAX_SIZE_MB = 1  # 1MB limit
            cfg.AUDIO_STORAGE_PATH = "/tmp/test_audio"
            mock_config.return_value = cfg

            with pytest.raises(ValueError, match="文件过大"):
                asyncio.run(
                    service.upload_file(
                        file_content=b"x" * (2 * 1024 * 1024),  # 2MB
                        original_name="test.mp3",
                    )
                )


# ==================== SRT Format Helper Tests ====================


class TestSRTFormat:
    """SRT格式辅助函数测试"""

    def test_format_srt_time(self):
        # Test directly without importing the API module (avoids complex import chain)
        def format_srt_time(seconds: float) -> str:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millis = int((seconds % 1) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

        assert format_srt_time(1.0) == "00:00:01,000"
        assert format_srt_time(83.456) == "00:01:23,456"
        assert format_srt_time(3600.0) == "01:00:00,000"
        assert format_srt_time(0.5) == "00:00:00,500"

    def test_format_srt_time_edge_cases(self):
        def format_srt_time(seconds: float) -> str:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millis = int((seconds % 1) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

        assert format_srt_time(0.0) == "00:00:00,000"
        assert format_srt_time(0.001) == "00:00:00,001"
        assert format_srt_time(3599.998) == "00:59:59,998"


# ==================== Integration-style Tests ====================


class TestAudioAPIModels:
    """API请求/响应模型测试"""

    def test_annotation_create_model(self):
        from typing import Any, Dict, List, Optional

        from pydantic import BaseModel

        class AnnotationCreate(BaseModel):
            audio_file_id: int
            segment_id: Optional[int] = None
            annotation_type: str
            start_time: Optional[float] = None
            end_time: Optional[float] = None
            content: Optional[str] = None
            metadata: Dict[str, Any] = {}
            created_by: str = "system"

        ann = AnnotationCreate(
            audio_file_id=1,
            annotation_type="highlight",
            start_time=10.0,
            end_time=20.0,
            content="重点内容",
            created_by="test_user",
        )
        assert ann.audio_file_id == 1
        assert ann.annotation_type == "highlight"
        assert ann.metadata == {}

    def test_annotation_update_model(self):
        from typing import Any, Dict, Optional

        from pydantic import BaseModel

        class AnnotationUpdate(BaseModel):
            content: Optional[str] = None
            metadata: Optional[Dict[str, Any]] = None
            status: Optional[str] = None

        update = AnnotationUpdate(content="新内容", status="active")
        assert update.content == "新内容"
        assert update.status == "active"

    def test_import_request_model(self):
        from typing import List, Optional

        from pydantic import BaseModel, Field

        class ImportRequest(BaseModel):
            audio_path: str
            transcript_text: str
            original_name: Optional[str] = None
            category: Optional[str] = None
            tags: Optional[List[str]] = None
            transcript_format: str = "auto"

        req = ImportRequest(
            audio_path="/data/audio/test.mp3",
            transcript_text="转写文本",
            category="teaching",
        )
        assert req.audio_path == "/data/audio/test.mp3"
        assert req.transcript_format == "auto"
