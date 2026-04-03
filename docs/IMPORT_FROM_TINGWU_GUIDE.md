# 导入阿里云听悟数据到灵知系统

**目的**: 将从阿里云听悟下载的音频和文字导入到灵知系统

---

## 📁 准备数据

### 目录结构

```
data/from_tingwu/
├── audio/              # 音频文件
│   ├── recording1.mp3
│   └── recording2.mp3
└── transcripts/        # 转录文字
    ├── recording1.txt
    └── recording2.txt
```

---

## 🔄 导入脚本

### 方式1: 命令行导入

```bash
# scripts/import_from_tingwu.py
import sys
import os
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.audio_importer import AudioImporter
from backend.database import get_db

async def import_from_tingwu(
    audio_dir: str,
    transcript_dir: str,
    category: str = "teaching"
):
    """从听悟目录导入数据

    Args:
        audio_dir: 音频文件目录
        transcript_dir: 转录文字目录
        category: 分类（teaching/course/practice/meeting）
    """
    db = get_db()

    # 创建导入器
    importer = AudioImporter(db)

    # 扫描音频文件
    audio_path = Path(audio_dir)
    transcript_path = Path(transcript_dir)

    audio_files = list(audio_path.glob("*.mp3"))
    print(f"找到 {len(audio_files)} 个音频文件")

    # 导入每个音频
    for audio_file in audio_files:
        # 对应的转录文件
        transcript_file = transcript_path / f"{audio_file.stem}.txt"

        if not transcript_file.exists():
            print(f"⚠️  跳过 {audio_file.name}: 缺少转录文件")
            continue

        print(f"导入: {audio_file.name}")

        # 读取转录文字
        with open(transcript_file, 'r', encoding='utf-8') as f:
            transcript = f.read()

        # 导入数据
        result = await importer.import_audio_with_transcript(
            audio_file=str(audio_file),
            transcript=transcript,
            title=audio_file.stem,
            category=category
        )

        print(f"  ✓ 音频ID: {result['audio_id']}")
        print(f"  ✓ 分段数: {result['segments_count']}")

    print(f"\n导入完成！")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="导入听悟数据")
    parser.add_argument("--audio-dir", required=True, help="音频文件目录")
    parser.add_argument("--transcript-dir", required=True, help="转录文字目录")
    parser.add_argument("--category", default="teaching", help="分类")

    args = parser.parse_args()

    asyncio.run(import_from_tingwu(
        args.audio_dir,
        args.transcript_dir,
        args.category
    ))
```

### 方式2: Web界面导入

```python
# backend/api/v1/import.py
from fastapi import APIRouter, UploadFile, BackgroundTasks
from typing import List

router = APIRouter(prefix="/import", tags=["import"])

@router.post("/from-tingwu")
async def import_from_tingwu(
    audio_files: List[UploadFile],
    transcript_files: List[UploadFile],
    category: str = "teaching",
    background_tasks: BackgroundTasks = None
):
    """从听悟导入数据

    Args:
        audio_files: 音频文件列表
        transcript_files: 转录文字文件列表
        category: 分类
    """
    results = []

    # 匹配音频和转录文件
    file_pairs = []
    for audio in audio_files:
        # 查找对应的转录文件
        stem = Path(audio.filename).stem
        transcript = next(
            (t for t in transcript_files if Path(t.filename).stem == stem),
            None
        )

        if not transcript:
            continue

        file_pairs.append((audio, transcript))

    print(f"找到 {len(file_pairs)} 对文件")

    # 导入每一对文件
    for audio, transcript in file_pairs:
        # 保存文件
        audio_path = await _save_audio_file(audio)
        transcript_path = await _save_transcript_file(transcript)

        # 读取转录文字
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript_text = f.read()

        # 创建导入任务
        background_tasks.add_task(
            _import_audio_with_transcript,
            audio_path,
            transcript_text,
            audio.filename,
            category
        )

        results.append({
            "audio_file": audio.filename,
            "transcript_file": transcript.filename,
            "status": "queued"
        })

    return {
        "total": len(file_pairs),
        "results": results
    }

async def _import_audio_with_transcript(
    audio_path: str,
    transcript: str,
    title: str,
    category: str
):
    """后台导入任务"""
    from backend.services.audio_importer import AudioImporter
    from backend.database import get_db

    db = get_db()
    importer = AudioImporter(db)

    result = await importer.import_audio_with_transcript(
        audio_file=audio_path,
        transcript=transcript,
        title=title,
        category=category
    )

    print(f"导入完成: {title} (音频ID: {result['audio_id']})")
```

---

## 🎯 导入服务实现

```python
# backend/services/audio_importer.py
from faster_whisper import WhisperModel
from pathlib import Path
import asyncio

class AudioImporter:
    """音频导入器"""

    def __init__(self, db):
        self.db = db
        self.whisper = None  # 如果需要重新转写

    async def import_audio_with_transcript(
        self,
        audio_file: str,
        transcript: str,
        title: str,
        category: str = "teaching"
    ) -> dict:
        """导入音频和转录文字

        Args:
            audio_file: 音频文件路径
            transcript: 转录文字
            title: 标题
            category: 分类

        Returns:
            导入结果
        """
        # 1. 获取音频时长
        duration = await self._get_audio_duration(audio_file)

        # 2. 创建音频记录
        audio_record = await self.db.insert(audio_files, {
            "file_name": Path(audio_file).name,
            "file_path": audio_file,
            "title": title,
            "category": category,
            "duration": duration,
            "status": "completed",  # 已转录
            "transcript": transcript,
            "language": "zh",
            "upload_ip": "127.0.0.1",
            "uploaded_by": "import"
        })

        # 3. 分段处理转录文字
        segments = await self._parse_transcript(
            transcript,
            audio_record["id"]
        )

        # 4. 保存分段
        for seg in segments:
            await self.db.insert(audio_segments, {
                "audio_file_id": audio_record["id"],
                "text": seg["text"],
                "start_time": seg["start_time"],
                "end_time": seg["end_time"],
                "confidence": 1.0  # 听悟的转录通常很准确
            })

        # 5. 触发向量化（与文字工程流集成）
        await self._vectorize_transcript(
            audio_record["id"],
            segments
        )

        return {
            "audio_id": audio_record["id"],
            "title": title,
            "segments_count": len(segments),
            "duration": duration
        }

    async def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        from pydub import AudioSegment

        audio = AudioSegment.from_mp3(audio_path)
        return len(audio) / 1000.0  # 转换为秒

    async def _parse_transcript(
        self,
        transcript: str,
        audio_id: int
    ) -> list:
        """解析转录文字为分段

        Args:
            transcript: 转录文字
            audio_id: 音频ID

        Returns:
            分段列表
        """
        segments = []

        # 尝试解析SRT格式
        if "-->" in transcript:
            segments = self._parse_srt(transcript)
        else:
            # 纯文本，按段落分割
            segments = self._parse_plain_text(transcript)

        return segments

    def _parse_srt(self, srt_content: str) -> list:
        """解析SRT格式"""
        segments = []
        lines = srt_content.strip().split("\n\n")

        for block in lines:
            lines_block = block.split("\n")
            if len(lines_block) < 3:
                continue

            # 解析时间戳
            timestamp_line = lines_block[1]
            if "-->" not in timestamp_line:
                continue

            start_str, end_str = timestamp_line.split("-->")
            start_time = self._parse_srt_time(start_str.strip())
            end_time = self._parse_srt_time(end_str.strip())

            # 解析文本
            text = "\n".join(lines_block[2:])

            segments.append({
                "start_time": start_time,
                "end_time": end_time,
                "text": text.strip()
            })

        return segments

    def _parse_srt_time(self, time_str: str) -> float:
        """解析SRT时间戳

        格式: 00:01:23,456
        """
        time_str = time_str.replace(",", ".")
        parts = time_str.split(":")

        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_parts = parts[2].split(".")
        seconds = int(seconds_parts[0])
        millis = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0

        return hours * 3600 + minutes * 60 + seconds + millis / 1000.0

    def _parse_plain_text(self, text: str) -> list:
        """解析纯文本（按段落分割）"""
        segments = []
        paragraphs = text.split("\n\n")

        current_time = 0.0
        avg_duration = 5.0  # 假设每段5秒

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 估算时间（没有实际时间戳）
            start_time = current_time
            end_time = current_time + avg_duration

            # 按句子细分
            sentences = para.split("。")
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                segments.append({
                    "start_time": start_time,
                    "end_time": end_time,
                    "text": sentence + "。"
                })

                current_time = end_time
                end_time = current_time + avg_duration

        return segments

    async def _vectorize_transcript(self, audio_id: int, segments: list):
        """向量化转录文字（与文字工程流集成）

        Args:
            audio_id: 音频ID
            segments: 分段列表
        """
        try:
            from backend.services.text_processor import TextProcessor

            processor = TextProcessor()

            # 为每个分段生成向量
            for segment in segments:
                embedding = await processor.generate_embedding(segment["text"])

                # 更新分段
                await self.db.execute(
                    """UPDATE audio_segments
                       SET embedding = $1
                       WHERE text = $2
                       AND audio_file_id = $3
                    """,
                    embedding,
                    segment["text"],
                    audio_id
                )

            print(f"✓ 音频 {audio_id} 向量化完成")

        except Exception as e:
            print(f"⚠️  音频 {audio_id} 向量化失败: {e}")
```

---

## 🚀 使用方法

### 命令行导入

```bash
# 准备数据目录
mkdir -p data/from_tingwu/audio
mkdir -p data/from_tingwu/transcripts

# 将下载的文件放入对应目录

# 运行导入脚本
python scripts/import_from_tingwu.py \
  --audio-dir data/from_tingwu/audio \
  --transcript-dir data/from_tingwu/transcripts \
  --category teaching
```

### Web界面导入

```bash
# 1. 启动服务
docker-compose up -d

# 2. 访问导入页面
open http://localhost:8001/import

# 3. 上传音频和转录文件
# 4. 点击"导入"按钮
```

---

## 📋 支持的格式

### 音频格式
- MP3
- WAV
- M4A
- AAC

### 转录文字格式
- 纯文本（.txt）
- SRT字幕（.srt）
- 带时间戳的文本

---

## ⚠️ 注意事项

1. **文件名匹配**: 音频和转录文件的文件名（不含扩展名）必须相同
2. **编码格式**: 转录文字文件必须使用UTF-8编码
3. **音频时长**: 确保音频文件完整，未损坏
4. **分类选择**: 根据内容选择合适的分类（teaching/course/practice/meeting）

---

**文档状态**: ✅ 完成

**下一步**: 准备数据并运行导入脚本
