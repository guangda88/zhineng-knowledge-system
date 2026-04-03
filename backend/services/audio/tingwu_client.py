"""通义听悟(阿里云)客户端

通过阿里云Tingwu SDK调用离线转写API。
SDK: alibabacloud-tingwu20230930
文档: https://help.aliyun.com/zh/tingwu/developer-reference/api

支持：
- 创建转写任务（提交音频URL）
- 轮询任务状态
- 获取转写结果（含说话人分离）
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class TranscriptionSegment:
    start_time: float
    end_time: float
    text: str
    speaker: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class TranscriptionResult:
    task_id: str
    status: TaskStatus
    segments: List[TranscriptionSegment] = field(default_factory=list)
    full_text: str = ""
    duration: float = 0.0
    error_message: Optional[str] = None


class TingwuClient:
    """通义听悟API客户端

    使用阿里云Tingwu SDK进行音频离线转写。
    需要配置 ALIYUN_ACCESS_KEY_ID 和 ALIYUN_ACCESS_KEY_SECRET。
    """

    def __init__(
        self,
        access_key_id: Optional[str] = None,
        access_key_secret: Optional[str] = None,
    ):
        self._access_key_id = access_key_id or os.environ.get("ALIYUN_ACCESS_KEY_ID")
        self._access_key_secret = access_key_secret or os.environ.get("ALIYUN_ACCESS_KEY_SECRET")
        self._enabled = bool(self._access_key_id and self._access_key_secret)
        self._client = None

        if self._enabled:
            try:
                from alibabacloud_tea_openapi import models as open_api_models
                from alibabacloud_tingwu20230930.client import Client as TingwuClient

                config = open_api_models.Config(
                    access_key_id=self._access_key_id,
                    access_key_secret=self._access_key_secret,
                    region_id="cn-hangzhou",
                )
                self._client = TingwuClient(config)
                logger.info("Tingwu SDK client initialized")
            except ImportError:
                logger.warning(
                    "alibabacloud-tingwu20230930 not installed. "
                    "Install with: pip install alibabacloud-tingwu20230930"
                )
                self._enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize Tingwu client: {e}")
                self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    async def create_transcription_task(
        self,
        file_url: str,
        enable_speaker_diarization: bool = True,
        speaker_count: Optional[int] = None,
        language: str = "cn",
    ) -> str:
        """创建离线转写任务

        Args:
            file_url: 音频文件URL（公网可访问URL或OSS地址）
            enable_speaker_diarization: 是否启用说话人分离
            speaker_count: 预期说话人数量
            language: 语言代码，cn=中文

        Returns:
            task_id: 转写任务ID

        Raises:
            RuntimeError: SDK不可用或任务创建失败
        """
        if not self.enabled:
            raise RuntimeError("Tingwu client not enabled (missing AccessKey or SDK)")

        from alibabacloud_tingwu20230930 import models as tingwu_models

        request = tingwu_models.CreateTaskRequest(
            input=tingwu_models.CreateTaskRequestInput(
                file_url=file_url,
                source_language=language,
            ),
        )

        if enable_speaker_diarization:
            diarization = tingwu_models.CreateTaskRequestParametersTranscriptionDiarization()
            if speaker_count:
                diarization.speaker_count = speaker_count

            request.parameters = tingwu_models.CreateTaskRequestParameters(
                transcription=tingwu_models.CreateTaskRequestParametersTranscription(
                    diarization_enabled=True,
                    diarization=diarization,
                ),
            )

        try:
            response = await asyncio.to_thread(
                self._client.create_task_with_options, request, None, None, None
            )

            if response.status_code == 200 and response.body:
                task_id = response.body.data.task_id
                logger.info(f"Tingwu task created: {task_id}")
                return task_id
            else:
                error_msg = f"Tingwu API error: {response.status_code}"
                if response.body and hasattr(response.body, "message"):
                    error_msg += f" - {response.body.message}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Failed to create Tingwu task: {e}", exc_info=True)
            raise RuntimeError(f"Tingwu task creation failed: {e}")

    async def get_task_status(self, task_id: str) -> TaskStatus:
        """查询任务状态

        Args:
            task_id: 转写任务ID

        Returns:
            TaskStatus枚举值
        """
        if not self.enabled:
            raise RuntimeError("Tingwu client not enabled")

        try:
            response = await asyncio.to_thread(
                self._client.get_task_info_with_options, task_id, None, None, None
            )

            if response.status_code == 200 and response.body:
                status_str = response.body.data.task_status or "UNKNOWN"
                try:
                    return TaskStatus(status_str.upper())
                except ValueError:
                    return TaskStatus.UNKNOWN
            return TaskStatus.UNKNOWN

        except Exception as e:
            logger.error(f"Failed to check Tingwu task status: {e}")
            return TaskStatus.UNKNOWN

    async def get_transcription_result(self, task_id: str) -> TranscriptionResult:
        """获取转写结果

        Args:
            task_id: 转写任务ID

        Returns:
            TranscriptionResult对象
        """
        if not self.enabled:
            raise RuntimeError("Tingwu client not enabled")

        try:
            response = await asyncio.to_thread(
                self._client.get_task_info_with_options, task_id, None, None, None
            )

            if response.status_code != 200 or not response.body:
                return TranscriptionResult(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=f"API error: {response.status_code}",
                )

            body_data = response.body.data
            task_status_str = (body_data.task_status or "UNKNOWN").upper()

            try:
                task_status = TaskStatus(task_status_str)
            except ValueError:
                task_status = TaskStatus.UNKNOWN

            if task_status != TaskStatus.SUCCEEDED:
                error_msg = None
                if hasattr(body_data, "error_message"):
                    error_msg = body_data.error_message
                return TranscriptionResult(
                    task_id=task_id,
                    status=task_status,
                    error_message=error_msg,
                )

            result_obj = body_data.result
            if not result_obj or not hasattr(result_obj, "transcription"):
                return TranscriptionResult(
                    task_id=task_id,
                    status=TaskStatus.SUCCEEDED,
                    full_text="",
                )

            transcription = result_obj.transcription
            if not transcription:
                return TranscriptionResult(
                    task_id=task_id,
                    status=TaskStatus.SUCCEEDED,
                    full_text="",
                )

            transcription_dict = transcription.to_map() if hasattr(transcription, "to_map") else {}
            sentences = transcription_dict.get("Sentences", [])

            segments: List[TranscriptionSegment] = []
            full_text_parts: List[str] = []

            for sentence in sentences:
                text = sentence.get("Text", "")
                full_text_parts.append(text)

                begin_time = sentence.get("BeginTime", 0)
                end_time = sentence.get("EndTime", 0)
                speaker_id = sentence.get("SpeakerId")

                segments.append(
                    TranscriptionSegment(
                        start_time=begin_time / 1000.0,
                        end_time=end_time / 1000.0,
                        text=text,
                        speaker=speaker_id,
                    )
                )

            full_text = "".join(full_text_parts)
            duration = segments[-1].end_time if segments else 0.0

            return TranscriptionResult(
                task_id=task_id,
                status=TaskStatus.SUCCEEDED,
                segments=segments,
                full_text=full_text,
                duration=duration,
            )

        except Exception as e:
            logger.error(f"Failed to get Tingwu result: {e}", exc_info=True)
            return TranscriptionResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error_message=str(e),
            )

    async def wait_for_completion(
        self,
        task_id: str,
        poll_interval: float = 5.0,
        timeout: float = 3600.0,
    ) -> TranscriptionResult:
        """等待转写任务完成

        Args:
            task_id: 转写任务ID
            poll_interval: 轮询间隔（秒）
            timeout: 超时时间（秒）

        Returns:
            TranscriptionResult对象
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = await self.get_task_status(task_id)

            if status == TaskStatus.SUCCEEDED:
                return await self.get_transcription_result(task_id)
            elif status == TaskStatus.FAILED:
                return await self.get_transcription_result(task_id)

            await asyncio.sleep(poll_interval)

        return TranscriptionResult(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error_message=f"Task timed out after {timeout}s",
        )
