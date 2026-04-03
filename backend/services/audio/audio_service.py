"""音频处理服务

编排音频上传、转写、分段、向量化等操作。
"""

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import get_config
from backend.core.database import init_db_pool

logger = logging.getLogger(__name__)


class AudioService:
    """音频处理服务

    负责：
    - 文件上传和存储
    - 调用听悟API进行转写
    - 存储转写结果（分段）
    - 管理音频文件状态
    - 音频分段向量化和语义搜索
    """

    def __init__(self):
        self._tingwu_client = None
        self._vector_retriever = None
        self._asr_router = None

    async def _get_vector_retriever(self):
        """延迟初始化向量检索器"""
        if self._vector_retriever is None:
            from backend.services.retrieval.vector import VectorRetriever

            pool = await init_db_pool()
            self._vector_retriever = VectorRetriever(pool)
        return self._vector_retriever

    async def vectorize_segments(self, file_id: int) -> Dict[str, Any]:
        """对音频分段文本进行向量化并存储

        Args:
            file_id: 音频文件ID

        Returns:
            向量化结果统计
        """
        pool = await init_db_pool()

        segments = await pool.fetch(
            """
            SELECT id, text FROM audio_segments
            WHERE audio_file_id = $1 AND embedding IS NULL
            ORDER BY segment_index
            """,
            file_id,
        )

        if not segments:
            return {"file_id": file_id, "vectorized": 0, "message": "无待向量化分段"}

        retriever = await self._get_vector_retriever()
        texts = [seg["text"] for seg in segments]
        embeddings = await retriever.embed_batch(texts)

        count = 0
        for seg, emb in zip(segments, embeddings):
            await pool.execute(
                "UPDATE audio_segments SET embedding = $1 WHERE id = $2",
                str(emb),
                seg["id"],
            )
            count += 1

        logger.info(f"Vectorized {count} segments for audio_file_id={file_id}")
        return {"file_id": file_id, "vectorized": count}

    async def vectorize_all_unembedded(self) -> Dict[str, Any]:
        """向量化所有缺少embedding的音频分段"""
        pool = await init_db_pool()

        file_ids = await pool.fetch(
            """
            SELECT DISTINCT audio_file_id FROM audio_segments
            WHERE embedding IS NULL
            """
        )

        total = 0
        for row in file_ids:
            result = await self.vectorize_segments(row["audio_file_id"])
            total += result["vectorized"]

        logger.info(f"Total vectorized: {total} segments across {len(file_ids)} files")
        return {"total_vectorized": total, "files_processed": len(file_ids)}

    async def search_segments(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
        threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """语义搜索音频分段

        Args:
            query: 搜索查询
            category: 分类过滤
            top_k: 返回数量
            threshold: 相似度阈值

        Returns:
            匹配的分段列表
        """
        retriever = await self._get_vector_retriever()
        query_vec = await retriever.embed_text(query)

        pool = await init_db_pool()

        category_filter = ""
        params: list = [str(query_vec), top_k]
        if category:
            category_filter = "AND af.category = $3"
            params.append(category)

        rows = await pool.fetch(
            f"""
            SELECT
                s.id, s.audio_file_id, s.segment_index,
                s.start_time, s.end_time, s.text, s.speaker,
                af.original_name, af.category,
                1 - (s.embedding <=> $1::vector) AS similarity
            FROM audio_segments s
            JOIN audio_files af ON af.id = s.audio_file_id
            WHERE s.embedding IS NOT NULL
                AND af.status = 'transcribed'
                {category_filter}
            ORDER BY s.embedding <=> $1::vector
            LIMIT $2
            """,
            *params,
        )

        results = []
        for r in rows:
            sim = r["similarity"]
            if sim >= threshold:
                results.append(
                    {
                        "segment_id": r["id"],
                        "audio_file_id": r["audio_file_id"],
                        "audio_name": r["original_name"],
                        "category": r["category"],
                        "segment_index": r["segment_index"],
                        "start_time": r["start_time"],
                        "end_time": r["end_time"],
                        "text": r["text"],
                        "speaker": r["speaker"],
                        "similarity": round(sim, 4),
                    }
                )

        return results

    def _get_asr_router(self):
        if self._asr_router is None:
            from .asr_router import ASRRouter

            self._asr_router = ASRRouter()
        return self._asr_router

    async def transcribe_local(
        self,
        file_id: int,
        language: str = "zh",
        engine: str = "whisper",
    ) -> Dict[str, Any]:
        """本地 ASR 转写

        Args:
            file_id: 音频文件ID
            language: 语言代码 (zh/en/ja...)
            engine: ASR 引擎 (whisper/cohere)

        Returns:
            转写结果
        """
        pool = await init_db_pool()

        row = await pool.fetchrow(
            "SELECT file_path, status FROM audio_files WHERE id = $1",
            file_id,
        )
        if not row:
            raise ValueError(f"音频文件不存在: {file_id}")

        file_path = row["file_path"]
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"音频文件不存在: {file_path}")

        await pool.execute(
            """UPDATE audio_files SET status = 'transcribing', updated_at = NOW()
               WHERE id = $1""",
            file_id,
        )

        try:
            router = self._get_asr_router()
            result = await asyncio.to_thread(
                router.transcribe,
                file_path,
                engine=engine,
                language=language,
            )

            text = result["text"]
            duration = result["duration"]

            raw_segments = result.get("segments", [])
            if raw_segments:
                segments = raw_segments
            else:
                segments = self._parse_plain_text(text)

            await pool.execute(
                """UPDATE audio_files
                   SET status = 'transcribed',
                       transcription_text = $1,
                       duration = $2,
                       updated_at = NOW()
                   WHERE id = $3""",
                text,
                duration,
                file_id,
            )

            await pool.execute(
                "DELETE FROM audio_segments WHERE audio_file_id = $1",
                file_id,
            )

            for i, seg in enumerate(segments):
                await pool.execute(
                    """INSERT INTO audio_segments
                        (audio_file_id, segment_index, start_time, end_time, text)
                    VALUES ($1, $2, $3, $4, $5)""",
                    file_id,
                    i,
                    seg["start_time"],
                    seg["end_time"],
                    seg["text"],
                )

            logger.info(
                f"Local transcription done: file_id={file_id}, "
                f"duration={duration:.1f}s, segments={len(segments)}, "
                f"rtfx={result['rtfx']:.1f}"
            )

            return {
                "file_id": file_id,
                "status": "transcribed",
                "text": text,
                "duration": duration,
                "segments_count": len(segments),
                "rtfx": result["rtfx"],
            }

        except Exception as e:
            await pool.execute(
                """UPDATE audio_files SET status = 'failed', updated_at = NOW()
                   WHERE id = $1""",
                file_id,
            )
            logger.error(f"Local transcription failed: file_id={file_id}: {e}")
            raise

    def _get_tingwu_client(self):
        """延迟初始化Tingwu客户端"""
        if self._tingwu_client is None:
            from .tingwu_client import TingwuClient

            config = get_config()
            self._tingwu_client = TingwuClient(
                access_key_id=config.ALIYUN_ACCESS_KEY_ID,
                access_key_secret=config.ALIYUN_ACCESS_KEY_SECRET,
            )
        return self._tingwu_client

    async def upload_file(
        self,
        file_content: bytes,
        original_name: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by: str = "system",
    ) -> Dict[str, Any]:
        """上传音频文件

        Args:
            file_content: 文件二进制内容
            original_name: 原始文件名
            category: 分类
            tags: 标签列表
            created_by: 上传者

        Returns:
            包含文件信息的字典
        """
        config = get_config()

        file_ext = Path(original_name).suffix.lstrip(".").lower()
        if file_ext not in config.AUDIO_ALLOWED_FORMATS:
            raise ValueError(
                f"不支持的音频格式: {file_ext}. " f"支持: {', '.join(config.AUDIO_ALLOWED_FORMATS)}"
            )

        max_bytes = config.AUDIO_MAX_SIZE_MB * 1024 * 1024
        if len(file_content) > max_bytes:
            raise ValueError(
                f"文件过大: {len(file_content)} bytes, "
                f"最大: {max_bytes} bytes ({config.AUDIO_MAX_SIZE_MB}MB)"
            )

        file_id = uuid.uuid4().hex[:12]
        filename = f"{file_id}_{original_name}"
        storage_path = Path(config.AUDIO_STORAGE_PATH) / "uploads" / filename
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        with open(storage_path, "wb") as f:
            f.write(file_content)

        pool = await init_db_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO audio_files
                (filename, original_name, file_path, format, size_bytes,
                 status, category, tags, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id, filename, original_name, file_path, format,
                      size_bytes, status, category, tags, created_by, created_at
            """,
            filename,
            original_name,
            str(storage_path),
            file_ext,
            len(file_content),
            "uploaded",
            category,
            tags or [],
            created_by,
        )

        result = dict(row)
        logger.info(
            f"Audio file uploaded: id={result['id']}, name={original_name}, "
            f"size={len(file_content)}"
        )
        return result

    async def get_file(self, file_id: int) -> Optional[Dict[str, Any]]:
        """获取音频文件信息"""
        pool = await init_db_pool()
        row = await pool.fetchrow(
            """
            SELECT id, filename, original_name, file_path, duration, format,
                   size_bytes, sample_rate, channels, status, tingwu_task_id,
                   transcription_text, category, tags, created_by,
                   created_at, updated_at
            FROM audio_files WHERE id = $1
            """,
            file_id,
        )
        return dict(row) if row else None

    async def list_files(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """列出音频文件"""
        pool = await init_db_pool()

        conditions = []
        params = []
        idx = 1

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        if category:
            conditions.append(f"category = ${idx}")
            params.append(category)
            idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_row = await pool.fetchrow(
            f"SELECT COUNT(*) as total FROM audio_files {where_clause}",
            *params,
        )
        total = count_row["total"] if count_row else 0

        rows = await pool.fetch(
            f"""
            SELECT id, filename, original_name, duration, format, size_bytes,
                   status, category, created_by, created_at
            FROM audio_files {where_clause}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )

        return {
            "total": total,
            "items": [dict(r) for r in rows],
            "limit": limit,
            "offset": offset,
        }

    async def delete_file(self, file_id: int) -> bool:
        """删除音频文件（同时删除磁盘文件）"""
        pool = await init_db_pool()

        row = await pool.fetchrow(
            "SELECT file_path FROM audio_files WHERE id = $1",
            file_id,
        )
        if not row:
            return False

        file_path = row["file_path"]
        if os.path.exists(file_path):
            os.remove(file_path)

        await pool.execute("DELETE FROM audio_files WHERE id = $1", file_id)
        logger.info(f"Audio file deleted: id={file_id}")
        return True

    async def start_transcription(self, file_id: int) -> Dict[str, Any]:
        """提交转写任务到听悟

        Args:
            file_id: 音频文件ID

        Returns:
            包含task_id的字典
        """
        client = self._get_tingwu_client()
        if not client.enabled:
            raise RuntimeError(
                "Tingwu转写服务未启用。请配置 ALIYUN_ACCESS_KEY_ID 和 "
                "ALIYUN_ACCESS_KEY_SECRET 环境变量。"
            )

        pool = await init_db_pool()

        row = await pool.fetchrow(
            "SELECT file_path, status FROM audio_files WHERE id = $1",
            file_id,
        )
        if not row:
            raise ValueError(f"音频文件不存在: {file_id}")

        if row["status"] == "transcribing":
            raise ValueError(f"文件正在转写中: {file_id}")

        file_path = row["file_path"]

        file_url = f"file://{file_path}"

        task_id = await client.create_transcription_task(
            file_url=file_url,
            enable_speaker_diarization=True,
        )

        await pool.execute(
            """
            UPDATE audio_files
            SET status = 'transcribing', tingwu_task_id = $1, updated_at = NOW()
            WHERE id = $2
            """,
            task_id,
            file_id,
        )

        logger.info(f"Transcription started: file_id={file_id}, task_id={task_id}")
        return {"task_id": task_id, "file_id": file_id, "status": "transcribing"}

    async def check_transcription_status(self, file_id: int) -> Dict[str, Any]:
        """检查转写状态"""
        pool = await init_db_pool()

        row = await pool.fetchrow(
            "SELECT tingwu_task_id, status FROM audio_files WHERE id = $1",
            file_id,
        )
        if not row:
            raise ValueError(f"音频文件不存在: {file_id}")

        if not row["tingwu_task_id"]:
            return {"file_id": file_id, "status": row["status"], "message": "未提交转写"}

        client = self._get_tingwu_client()
        task_status = await client.get_task_status(row["tingwu_task_id"])

        if task_status.value == "SUCCEEDED":
            await self._save_transcription_result(file_id, row["tingwu_task_id"])

        return {
            "file_id": file_id,
            "task_id": row["tingwu_task_id"],
            "status": task_status.value,
        }

    async def _save_transcription_result(self, file_id: int, task_id: str) -> None:
        """保存转写结果到数据库"""
        client = self._get_tingwu_client()
        result = await client.get_transcription_result(task_id)

        if result.status.value != "SUCCEEDED":
            logger.error(
                f"Transcription failed: task_id={task_id}, " f"error={result.error_message}"
            )
            pool = await init_db_pool()
            await pool.execute(
                """
                UPDATE audio_files
                SET status = 'failed', updated_at = NOW()
                WHERE id = $1
                """,
                file_id,
            )
            return

        pool = await init_db_pool()

        await pool.execute(
            """
            UPDATE audio_files
            SET status = 'transcribed',
                transcription_text = $1,
                duration = $2,
                updated_at = NOW()
            WHERE id = $3
            """,
            result.full_text,
            result.duration,
            file_id,
        )

        await pool.execute(
            "DELETE FROM audio_segments WHERE audio_file_id = $1",
            file_id,
        )

        for i, seg in enumerate(result.segments):
            await pool.execute(
                """
                INSERT INTO audio_segments
                    (audio_file_id, segment_index, start_time, end_time,
                     text, speaker, confidence)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                file_id,
                i,
                seg.start_time,
                seg.end_time,
                seg.text,
                seg.speaker,
                seg.confidence,
            )

        logger.info(
            f"Transcription saved: file_id={file_id}, "
            f"segments={len(result.segments)}, duration={result.duration}"
        )

    async def get_segments(self, file_id: int) -> List[Dict[str, Any]]:
        """获取音频的分段列表"""
        pool = await init_db_pool()
        rows = await pool.fetch(
            """
            SELECT id, segment_index, start_time, end_time, text,
                   speaker, confidence
            FROM audio_segments
            WHERE audio_file_id = $1
            ORDER BY segment_index
            """,
            file_id,
        )
        return [dict(r) for r in rows]

    async def import_with_transcript(
        self,
        audio_path: str,
        transcript_text: str,
        original_name: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by: str = "import",
        transcript_format: str = "auto",
    ) -> Dict[str, Any]:
        """导入已有转写文本的音频文件（从听悟导出的数据）

        Args:
            audio_path: 音频文件路径
            transcript_text: 转写文本内容
            original_name: 原始文件名
            category: 分类
            tags: 标签
            created_by: 导入者
            transcript_format: 转录格式 (auto/txt/srt)

        Returns:
            导入结果
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        file_ext = path.suffix.lstrip(".").lower()
        file_size = path.stat().st_size

        file_id = uuid.uuid4().hex[:12]
        filename = f"{file_id}_{path.name}"

        config = get_config()
        storage_path = Path(config.AUDIO_STORAGE_PATH) / "uploads" / filename
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        import shutil

        shutil.copy2(audio_path, storage_path)

        segments = self._parse_transcript(transcript_text, transcript_format)
        duration = segments[-1]["end_time"] if segments else 0.0

        pool = await init_db_pool()

        row = await pool.fetchrow(
            """
            INSERT INTO audio_files
                (filename, original_name, file_path, duration, format, size_bytes,
                 status, transcription_text, category, tags, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, 'transcribed', $7, $8, $9, $10)
            RETURNING id
            """,
            filename,
            original_name or path.name,
            str(storage_path),
            duration,
            file_ext,
            file_size,
            transcript_text,
            category,
            tags or [],
            created_by,
        )

        audio_id = row["id"]

        for i, seg in enumerate(segments):
            await pool.execute(
                """
                INSERT INTO audio_segments
                    (audio_file_id, segment_index, start_time, end_time, text)
                VALUES ($1, $2, $3, $4, $5)
                """,
                audio_id,
                i,
                seg["start_time"],
                seg["end_time"],
                seg["text"],
            )

        logger.info(
            f"Audio imported with transcript: id={audio_id}, "
            f"segments={len(segments)}, name={original_name}"
        )

        return {
            "audio_id": audio_id,
            "filename": filename,
            "segments_count": len(segments),
            "duration": duration,
        }

    def _parse_transcript(self, text: str, fmt: str = "auto") -> List[Dict[str, Any]]:
        """解析转写文本为分段列表

        Args:
            text: 转写文本
            fmt: 格式 (auto/txt/srt)

        Returns:
            分段列表 [{"start_time": float, "end_time": float, "text": str}]
        """
        if fmt == "auto":
            if "-->" in text:
                fmt = "srt"
            else:
                fmt = "txt"

        if fmt == "srt":
            return self._parse_srt(text)
        else:
            return self._parse_plain_text(text)

    def _parse_srt(self, srt_content: str) -> List[Dict[str, Any]]:
        """解析SRT格式"""
        segments = []
        blocks = srt_content.strip().split("\n\n")

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue

            timestamp_line = lines[1]
            if "-->" not in timestamp_line:
                continue

            start_str, end_str = timestamp_line.split("-->")
            start_time = self._parse_srt_time(start_str.strip())
            end_time = self._parse_srt_time(end_str.strip())
            text = "\n".join(lines[2:]).strip()

            if text:
                segments.append(
                    {
                        "start_time": start_time,
                        "end_time": end_time,
                        "text": text,
                    }
                )

        return segments

    def _parse_srt_time(self, time_str: str) -> float:
        """解析SRT时间戳 (00:01:23,456)"""
        time_str = time_str.replace(",", ".")
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        sec_parts = parts[2].split(".")
        seconds = int(sec_parts[0])
        millis = int(sec_parts[1]) if len(sec_parts) > 1 else 0
        return hours * 3600 + minutes * 60 + seconds + millis / 1000.0

    def _parse_plain_text(self, text: str) -> List[Dict[str, Any]]:
        """解析纯文本为分段（无时间戳，按句子估算）"""
        segments = []
        current_time = 0.0
        avg_char_duration = 0.1  # 每字符约0.1秒

        paragraphs = text.split("\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            start_time = current_time
            end_time = current_time + len(para) * avg_char_duration

            segments.append(
                {
                    "start_time": round(start_time, 3),
                    "end_time": round(end_time, 3),
                    "text": para,
                }
            )
            current_time = end_time

        return segments
