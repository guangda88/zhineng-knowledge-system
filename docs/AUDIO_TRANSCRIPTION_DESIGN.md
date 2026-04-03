# 灵知系统 - 离线音频转写功能设计

**版本**: v1.0.0
**日期**: 2026-03-31
**核心功能**: 录音文件离线转写
**参考**: 阿里云听悟 - 录音文件识别

---

## 🎯 功能定位

### 核心场景

灵知系统的音频转写主要用于：

| 场景 | 说明 | 优先级 |
|------|------|--------|
| **功法教学录音** | 老师/专家的功法指导录音 | P0 |
| **课程录音** | 理论课、实践课录音 | P0 |
| **学员练习录音** | 学员练习过程中的录音记录 | P1 |
| **会议记录** | 研讨会、讨论会录音 | P2 |

### 与阿里云听悟的对比

| 特性 | 阿里云听悟 | 灵知系统 | 说明 |
|------|-----------|---------|------|
| **音频时长** | 最长12小时 | 最长12小时 | 相同 |
| **并发处理** | 支持批量 | 支持批量 | 相同 |
| **转写引擎** | 自研模型 | faster-whisper | 开源方案 |
| **说话人分离** | ✅ 支持 | P1 支持 | 可选功能 |
| **摘要总结** | ✅ 支持 | P1 支持 | DeepSeek实现 |
| **部署方式** | 云API | 本地部署 | 隐私保护 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────┐
│              音频转写系统架构                     │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─────────────┐      ┌──────────────┐         │
│  │  音频上传    │─────▶│  文件队列     │         │
│  │  (Web UI)   │      │  (Redis)     │         │
│  └─────────────┘      └──────┬───────┘         │
│                              │                  │
│                              ▼                  │
│                      ┌───────────────┐          │
│                      │  转写Worker   │          │
│                      │  (异步任务)   │          │
│                      └───────┬───────┘          │
│                              │                  │
│              ┌───────────────┼───────────────┐  │
│              ▼               ▼               ▼  │
│      ┌───────────┐   ┌───────────┐   ┌──────────┐│
│      │Whisper引擎 │   │ 分段处理   │   │ 结果入库  ││
│      │(faster)   │   │(长音频)   │   │ (Postgres)││
│      └───────────┘   └───────────┘   └──────────┘│
│                              │                  │
│                              ▼                  │
│                      ┌───────────────┐          │
│                      │  转写结果     │          │
│                      │  - 文本       │          │
│                      │  - 时间戳     │          │
│                      │  - 说话人     │          │
│                      └───────────────┘          │
│                              │                  │
│                              ▼                  │
│                      ┌───────────────┐          │
│                      │  后续处理     │          │
│                      │  - 向量化     │          │
│                      │  - 标注       │          │
│                      │  - 检索       │          │
│                      └───────────────┘          │
└─────────────────────────────────────────────────┘
```

---

## 📋 核心功能设计

### 1. 音频上传与预处理

#### 1.1 支持的音频格式

| 格式 | 扩展名 | 优先级 | 说明 |
|------|--------|--------|------|
| MP3 | .mp3 | P0 | 最常用 |
| WAV | .wav | P0 | 无损格式 |
| M4A | .m4a | P1 | Apple设备 |
| AAC | .aac | P2 | 高压缩 |
| FLAC | .flac | P2 | 无损 |
| OGG | .ogg | P3 | 开源格式 |

#### 1.2 音频限制

```yaml
最小时长: 1秒
最大时长: 12小时 (43200秒)
最大文件: 2GB
采样率: 8kHz - 48kHz (自动转16kHz)
声道: 单声道/立体声 (自动转单声道)
```

#### 1.3 上传接口

```python
# backend/api/v1/audio.py
from fastapi import UploadFile, BackgroundTasks
from typing import Optional

@router.post("/upload")
async def upload_audio(
    audio: UploadFile,
    title: str,
    category: str,  # teaching, course, practice, meeting
    description: Optional[str] = None,
    background_tasks: BackgroundTasks = None
):
    """上传音频文件

    Args:
        audio: 音频文件
        title: 标题
        category: 分类
        description: 描述

    Returns:
        Dict: {
            "audio_id": 123,
            "status": "queued",
            "estimated_time": 180  # 预计转写时间（秒）
        }
    """
    # 1. 验证文件
    if not await _validate_audio_file(audio):
        raise HTTPException(400, "不支持的音频格式")

    # 2. 保存文件
    file_path = await _save_audio_file(audio)

    # 3. 创建音频记录
    audio_record = await db.insert(audio_files, {
        "file_name": audio.filename,
        "file_path": file_path,
        "title": title,
        "category": category,
        "description": description,
        "duration": await _get_audio_duration(file_path),
        "status": "queued"
    })

    # 4. 添加到转写队列
    background_tasks.add_task(
        process_transcription,
        audio_record["id"]
    )

    return {
        "audio_id": audio_record["id"],
        "status": "queued",
        "estimated_time": _estimate_time(file_path)
    }
```

### 2. 异步转写处理

#### 2.1 转写Worker

```python
# backend/workers/transcription_worker.py
from faster_whisper import WhisperModel
import asyncio
from concurrent.futures import ThreadPoolExecutor

class TranscriptionWorker:
    """转写Worker"""

    def __init__(self):
        # 初始化模型（使用faster-whisper，比原版快4倍）
        self.model = WhisperModel(
            "large-v3",  # 或 "base", "small", "medium"
            device="cpu",  # 或 "cuda" 如果有GPU
            compute_type="int8"  # 或 "float16" 如果有GPU
        )
        self.executor = ThreadPoolExecutor(max_workers=2)

    async def process(self, audio_id: int):
        """处理音频转写

        Args:
            audio_id: 音频ID
        """
        try:
            # 1. 获取音频记录
            audio = await db.get_by_id(audio_files, audio_id)

            # 2. 更新状态
            await db.update(audio_files, audio_id, {
                "status": "processing",
                "progress": 0
            })

            # 3. 检查音频时长
            if audio["duration"] > 3600:
                # 长音频，分段处理
                result = await self._transcribe_long_audio(audio)
            else:
                # 短音频，直接处理
                result = await self._transcribe_audio(audio)

            # 4. 保存结果
            await self._save_result(audio_id, result)

            # 5. 更新状态
            await db.update(audio_files, audio_id, {
                "status": "completed",
                "progress": 100
            })

        except Exception as e:
            # 错误处理
            await db.update(audio_files, audio_id, {
                "status": "failed",
                "error_message": str(e)
            })
            raise

    async def _transcribe_audio(self, audio: dict) -> dict:
        """转写音频"""
        # 在线程池中执行（CPU密集型）
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._transcribe_sync,
            audio["file_path"]
        )

    def _transcribe_sync(self, audio_path: str) -> dict:
        """同步转写（在线程池中执行）"""
        segments, info = self.model.transcribe(
            audio_path,
            language="zh",  # 中文
            vad_filter=True,  # 语音活动检测
            word_timestamps=True,  # 返回词级时间戳
            hotwords=["智能气功", "混元", "灵通"]  # 热词
        )

        results = []
        full_text = []

        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue

            result = {
                "text": text,
                "start": segment.start,
                "end": segment.end,
                "confidence": 1 - segment.no_speech_prob,
                "words": [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "probability": word.probability
                    }
                    for word in segment.words
                ]
            }

            results.append(result)
            full_text.append(text)

        return {
            "text": "".join(full_text),
            "segments": results,
            "language": info.language,
            "duration": info.duration
        }

    async def _transcribe_long_audio(self, audio: dict) -> dict:
        """转写长音频（分段处理）"""
        from pydub import AudioSegment
import os

        # 1. 加载音频
        audio_segment = AudioSegment.from_mp3(audio["file_path"])

        # 2. 按小时分段
        chunk_duration = 3600 * 1000  # 1小时（毫秒）
        chunk_paths = []

        for i, start in enumerate(range(0, len(audio_segment), chunk_duration)):
            end = min(start + chunk_duration, len(audio_segment))
            chunk = audio_segment[start:end]

            chunk_path = f"/tmp/audio_{audio['id']}_chunk_{i}.mp3"
            chunk.export(chunk_path, format="mp3")
            chunk_paths.append(chunk_path)

        # 3. 转写每一段
        all_results = []
        time_offset = 0

        for i, chunk_path in enumerate(chunk_paths):
            # 更新进度
            progress = int((i + 1) / len(chunk_paths) * 100)
            await db.update(audio_files, audio["id"], {
                "progress": progress
            })

            # 转写当前段
            result = await self._transcribe_sync(chunk_path)

            # 调整时间偏移
            for segment in result["segments"]:
                segment["start"] += time_offset
                segment["end"] += time_offset

            all_results.extend(result["segments"])
            time_offset = result["duration"]

            # 删除临时文件
            os.remove(chunk_path)

        # 4. 合并结果
        return {
            "text": "".join([s["text"] for s in all_results]),
            "segments": all_results,
            "language": "zh",
            "duration": time_offset
        }

    async def _save_result(self, audio_id: int, result: dict):
        """保存转写结果"""
        # 1. 保存音频记录
        await db.update(audio_files, audio_id, {
            "transcript": result["text"],
            "language": result["language"]
        })

        # 2. 保存分段结果
        for segment in result["segments"]:
            await db.insert(audio_segments, {
                "audio_file_id": audio_id,
                "text": segment["text"],
                "start_time": segment["start"],
                "end_time": segment["end"],
                "confidence": segment["confidence"],
                "word_timestamps": json.dumps(segment["words"])
            })

        # 3. 触发后续处理（向量生成等）
        await _trigger_post_processing(audio_id, result)
```

### 3. 转写结果查询

#### 3.1 查询接口

```python
@router.get("/audio/{audio_id}")
async def get_transcription(audio_id: int):
    """获取转写结果

    Returns:
        Dict: {
            "audio_id": 123,
            "status": "completed",
            "progress": 100,
            "duration": 180.5,
            "text": "完整转写文本...",
            "segments": [...]
        }
    """
    audio = await db.get_by_id(audio_files, audio_id)

    if not audio:
        raise HTTPException(404, "音频不存在")

    # 获取分段
    segments = await db.select(
        audio_segments,
        where={"audio_file_id": audio_id},
        order_by="start_time"
    )

    return {
        "audio_id": audio_id,
        "status": audio["status"],
        "progress": audio.get("progress", 0),
        "duration": audio["duration"],
        "text": audio.get("transcript", ""),
        "segments": segments,
        "error_message": audio.get("error_message")
    }

@router.get("/audio/{audio_id}/status")
async def get_transcription_status(audio_id: int):
    """获取转写状态（实时进度）"""
    audio = await db.get_by_id(audio_files, audio_id)

    return {
        "audio_id": audio_id,
        "status": audio["status"],
        "progress": audio.get("progress", 0),
        "estimated_time_remaining": _calculate_remaining(audio)
    }
```

#### 3.2 WebSocket实时推送

```python
# backend/api/v1/websocket.py
from fastapi import WebSocket

@router.websocket("/ws/transcription/{audio_id}")
async def transcription_websocket(websocket: WebSocket, audio_id: int):
    """转写进度WebSocket推送"""
    await websocket.accept()

    try:
        while True:
            # 获取当前状态
            audio = await db.get_by_id(audio_files, audio_id)

            # 推送进度
            await websocket.send_json({
                "status": audio["status"],
                "progress": audio.get("progress", 0),
                "text_preview": audio.get("transcript", "")[-500:]  # 最后500字符
            })

            # 如果完成或失败，退出
            if audio["status"] in ["completed", "failed"]:
                break

            # 等待1秒
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
```

### 4. 转写结果编辑

#### 4.1 文本编辑

```python
@router.put("/audio/{audio_id}/transcript")
async def update_transcript(
    audio_id: int,
    transcript: str
):
    """更新转写文本（手动编辑）"""
    await db.update(audio_files, audio_id, {
        "transcript": transcript,
        "edited_at": datetime.now()
    })

    return {"success": True}
```

#### 4.2 分段编辑

```python
@router.put("/audio/segment/{segment_id}")
async def update_segment(
    segment_id: int,
    text: str,
    start_time: float = None,
    end_time: float = None
):
    """更新分段"""
    update_data = {"text": text}
    if start_time is not None:
        update_data["start_time"] = start_time
    if end_time is not None:
        update_data["end_time"] = end_time

    await db.update(audio_segments, segment_id, update_data)

    return {"success": True}
```

### 5. 转写结果导出

```python
@router.get("/audio/{audio_id}/export")
async def export_transcript(
    audio_id: int,
    format: str = "txt"  # txt, srt, docx
):
    """导出转写结果

    Args:
        audio_id: 音频ID
        format: 导出格式 (txt/srt/docx)
    """
    audio = await db.get_by_id(audio_files, audio_id)
    segments = await db.select(
        audio_segments,
        where={"audio_file_id": audio_id},
        order_by="start_time"
    )

    if format == "txt":
        return _export_txt(audio, segments)
    elif format == "srt":
        return _export_srt(audio, segments)
    elif format == "docx":
        return _export_docx(audio, segments)
    else:
        raise HTTPException(400, "不支持的格式")

def _export_srt(audio, segments):
    """导出SRT字幕格式"""
    srt_content = []

    for i, segment in enumerate(segments, 1):
        # 序号
        srt_content.append(str(i))

        # 时间戳
        start = _format_srt_time(segment["start_time"])
        end = _format_srt_time(segment["end_time"])
        srt_content.append(f"{start} --> {end}")

        # 文本
        srt_content.append(segment["text"])

        # 空行
        srt_content.append("")

    return "\n".join(srt_content)

def _format_srt_time(seconds: float) -> str:
    """格式化为SRT时间戳"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
```

---

## 📊 数据库设计

```sql
-- 音频文件表
CREATE TABLE audio_files (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    title VARCHAR(500),
    category VARCHAR(50),  -- teaching, course, practice, meeting
    description TEXT,
    duration FLOAT,  -- 时长（秒）
    format VARCHAR(20),
    file_size BIGINT,

    -- 转写相关
    status VARCHAR(50) DEFAULT 'queued',  -- queued, processing, completed, failed
    progress INTEGER DEFAULT 0,  -- 0-100
    transcript TEXT,  -- 完整转写文本
    language VARCHAR(10),

    -- 元数据
    upload_ip VARCHAR(50),
    uploaded_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,

    -- 错误信息
    error_message TEXT
);

-- 音频分段表
CREATE TABLE audio_segments (
    id SERIAL PRIMARY KEY,
    audio_file_id INTEGER REFERENCES audio_files(id) ON DELETE CASCADE,

    -- 时间信息
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    duration FLOAT,

    -- 文本信息
    text TEXT NOT NULL,
    confidence FLOAT,

    -- 详细时间戳
    word_timestamps JSONB,  -- 词级时间戳

    -- 说话人信息（可选，P1功能）
    speaker VARCHAR(100),

    created_at TIMESTAMP DEFAULT NOW()
);

-- 转写任务队列表（使用Redis，这里仅作记录）
CREATE TABLE transcription_jobs (
    id SERIAL PRIMARY KEY,
    audio_file_id INTEGER REFERENCES audio_files(id),
    status VARCHAR(50) DEFAULT 'pending',
    worker_id VARCHAR(100),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_audio_files_status ON audio_files(status);
CREATE INDEX idx_audio_files_category ON audio_files(category);
CREATE INDEX idx_audio_segments_audio_id ON audio_segments(audio_file_id);
CREATE INDEX idx_audio_segments_time ON audio_segments(start_time, end_time);

-- 全文搜索
CREATE INDEX idx_audio_segments_text ON audio_segments USING gin(to_tsvector('chinese', text));
```

---

## 🎨 前端界面设计

### 音频上传页面

```javascript
// frontend/pages/audio-upload.html
class AudioUploadPage {
    constructor() {
        this.setupDropzone();
        this.setupWebSocket();
    }

    setupDropzone() {
        const dropzone = new Dropzone('#audio-upload', {
            url: '/api/v1/audio/upload',
            maxFilesize: 2048,  // 2GB
            acceptedFiles: 'audio/*',
            dictDefaultMessage: '拖拽音频文件到此处，或点击上传'
        });

        dropzone.on('success', (file, response) => {
            this.showProgress(response.audio_id);
        });
    }

    setupWebSocket() {
        this.ws = new WebSocket(`ws://${location.host}/ws/transcription/${audioId}`);

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.updateProgress(data);
        };
    }

    updateProgress(data) {
        // 更新进度条
        document.getElementById('progress').style.width = `${data.progress}%`;

        // 更新预览文本
        document.getElementById('text-preview').textContent = data.text_preview;

        // 完成时跳转
        if (data.status === 'completed') {
            location.href = `/audio/${audioId}`;
        }
    }
}
```

### 转写结果查看页面

```javascript
// frontend/pages/audio-view.html
class AudioViewer {
    constructor(audioId) {
        this.audioId = audioId;
        this.loadTranscript();
        this.setupAudioPlayer();
    }

    async loadTranscript() {
        const response = await fetch(`/api/v1/audio/${this.audioId}`);
        this.data = await response.json();

        this.renderTranscript();
        this.setupSearch();
    }

    renderTranscript() {
        const container = document.getElementById('segments');

        this.data.segments.forEach((segment, index) => {
            const div = document.createElement('div');
            div.className = 'segment';
            div.innerHTML = `
                <div class="timestamp">
                    ${this.formatTime(segment.start_time)} - ${this.formatTime(segment.end_time)}
                </div>
                <div class="text" contenteditable="true">${segment.text}</div>
            `;

            div.addEventListener('click', () => {
                this.audioPlayer.seekTo(segment.start_time);
            });

            container.appendChild(div);
        });
    }

    setupSearch() {
        const searchInput = document.getElementById('search');

        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            const segments = document.querySelectorAll('.segment');

            segments.forEach(segment => {
                const text = segment.textContent.toLowerCase();
                if (text.includes(query)) {
                    segment.style.display = 'block';
                    segment.classList.add('highlight');
                } else {
                    segment.style.display = query ? 'none' : 'block';
                    segment.classList.remove('highlight');
                }
            });
        });
    }

    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
}
```

---

## 🔄 与文字工程流的集成

### 转写文本向量化

```python
# backend/workers/vectorization_worker.py
async def vectorize_transcript(audio_id: int):
    """将转写文本向量化（与文字工程流集成）"""

    # 1. 获取转写结果
    audio = await db.get_by_id(audio_files, audio_id)
    segments = await db.select(
        audio_segments,
        where={"audio_file_id": audio_id}
    )

    # 2. 分块并生成向量
    from backend.services.text_processor import TextProcessor

    processor = TextProcessor()

    for segment in segments:
        # 生成向量
        embedding = await processor.generate_embedding(segment["text"])

        # 保存向量
        await db.update(audio_segments, segment["id"], {
            "embedding": embedding
        })

    # 3. 更新音频记录
    await db.update(audio_files, audio_id, {
        "vectorized": True,
        "vectorized_at": datetime.now()
    })
```

### 跨模态检索

```python
@router.post("/search/multimodal")
async def search_multimodal(query: str):
    """跨模态检索（文字 + 音频）"""

    results = {
        "text": [],  # 文字检索结果
        "audio": []  # 音频检索结果
    }

    # 1. 文字检索（团队A）
    text_results = await text_search_service.search(query)
    results["text"] = text_results

    # 2. 音频检索（搜索转写文本）
    audio_results = await db.query("""
        SELECT
            af.id,
            af.title,
            af.transcript,
            ts_rank(cd.text_vector, query) AS rank
        FROM audio_files af
        CROSS JOIN to_tsquery('chinese', $1) query
        WHERE af.transcript IS NOT NULL
          AND af.status = 'completed'
          AND af.transcript @@ query
        ORDER BY rank DESC
        LIMIT 10
    """, query)

    results["audio"] = audio_results

    # 3. 结果融合
    merged = merge_results_rrf(results["text"], results["audio"])

    return merged
```

---

## 📈 性能优化

### 1. 音频预处理

```python
# backend/services/audio_preprocessor.py
class AudioPreprocessor:
    """音频预处理器"""

    async def preprocess(self, input_path: str) -> str:
        """预处理音频

        1. 转换为MP3格式
        2. 统一采样率为16kHz
        3. 转为单声道
        4. 标准化音量
        """
        from pydub import AudioSegment

        # 加载音频
        audio = AudioSegment.from_file(input_path)

        # 转单声道
        if audio.channels > 1:
            audio = audio.set_channels(1)

        # 统一采样率
        audio = audio.set_frame_rate(16000)

        # 标准化音量
        audio = audio.normalize()

        # 导出
        output_path = input_path.replace('.mp3', '_processed.mp3')
        audio.export(output_path, format="mp3", bitrate="64k")

        return output_path
```

### 2. 缓存策略

```python
# 转写结果缓存
@lru_cache(maxsize=100)
async def get_transcription(audio_id: int):
    """获取转写结果（带缓存）"""
    # Redis缓存
    cached = await redis.get(f"transcription:{audio_id}")
    if cached:
        return json.loads(cached)

    # 数据库查询
    audio = await db.get_by_id(audio_files, audio_id)

    # 写缓存（1小时）
    await redis.setex(
        f"transcription:{audio_id}",
        3600,
        json.dumps(audio)
    )

    return audio
```

### 3. 并发控制

```python
# backend/workers/worker_pool.py
class WorkerPool:
    """Worker池（控制并发转写数量）"""

    def __init__(self, max_workers=2):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

    async def submit(self, audio_id: int):
        """提交转写任务"""
        async with self.semaphore:
            worker = TranscriptionWorker()
            await worker.process(audio_id)
```

---

## ✅ 实施计划（更新双工程流）

### 团队B: 音频处理工程流（20天）

| 任务ID | 任务 | 时间 | 交付物 |
|--------|------|------|--------|
| **B-1** | faster-whisper集成 | 2天 | 转写引擎 |
| **B-2** | 音频上传和预处理 | 2天 | 上传API |
| **B-3** | 异步转写Worker | 3天 | 转写服务 |
| **B-4** | 长音频分段处理 | 2天 | 分段逻辑 |
| **B-5** | 转写结果查询和展示 | 2天 | 查询API + UI |
| **B-6** | WebSocket实时进度 | 1天 | 实时推送 |
| **B-7** | 转写结果编辑 | 2天 | 编辑功能 |
| **B-8** | 导出功能(TXT/SRT) | 1天 | 导出API |
| **B-9** | 向量化集成 | 2天 | 与文字流集成 |
| **B-10** | 测试和文档 | 3天 | 完整文档 |
| **缓冲** | 意外问题 | 2天 | - |
| **总计** | **10项任务** | **22天** | - |

---

## 📊 成功标准

| 指标 | 目标 | 验收方式 |
|------|------|----------|
| 转写准确率 | WER < 15% | 测试集验证 |
| 转写速度 | RTF < 0.25 | 1小时音频<15分钟 |
| 支持时长 | 最长12小时 | 长音频测试 |
| 并发处理 | 同时2个文件 | 并发测试 |
| 结果编辑 | 支持在线编辑 | 功能测试 |
| 导出功能 | TXT/SRT格式 | 格式验证 |

---

## 🎯 与阿里云听悟对比

| 特性 | 阿里云听悟 | 灵知系统 |
|------|-----------|---------|
| **部署** | 云服务 | 本地部署 |
| **成本** | 按量付费 | 一次性成本 |
| **隐私** | 数据上传云端 | 数据本地 |
| **定制** | 标准服务 | 可深度定制 |
| **集成** | API调用 | 深度集成 |

---

**文档状态**: ✅ **设计完成**

**版本**: v1.0.0

**下一步**: 开始Sprint 1开发

**众智混元，万法灵通** ⚡🚀
