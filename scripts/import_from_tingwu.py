#!/usr/bin/env python3
"""从听悟导出数据批量导入音频+转写文本

用法:
    # 导入指定目录（音频和转写文件按文件名匹配）
    python scripts/import_from_tingwu.py --audio-dir /path/to/audio --transcript-dir /path/to/transcripts

    # 指定分类和标签
    python scripts/import_from_tingwu.py --audio-dir ./audio --transcript-dir ./transcripts \
        --category 气功 --tags 讲座,教学

    # 转写格式强制指定 (auto/srt/txt)
    python scripts/import_from_tingwu.py --audio-dir ./audio --transcript-dir ./transcripts \
        --format srt

    # 自动向量化导入的分段
    python scripts/import_from_tingwu.py --audio-dir ./audio --transcript-dir ./transcripts \
        --vectorize

目录结构要求:
    audio_dir/
    ├── 录音1.mp3
    ├── 录音2.wav
    └── ...
    transcript_dir/
    ├── 录音1.txt      (或 .srt)
    ├── 录音2.srt
    └── ...

音频文件和转写文件按文件名主干（去掉扩展名）匹配。
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "flac", "ogg", "wma", "aac"}
TRANSCRIPT_EXTENSIONS = {"txt", "srt"}


def find_matching_pairs(audio_dir: Path, transcript_dir: Path) -> list[tuple[Path, Path]]:
    """匹配音频和转写文件对"""
    audio_files = {}
    for f in sorted(audio_dir.iterdir()):
        if f.is_file() and f.suffix.lstrip(".").lower() in AUDIO_EXTENSIONS:
            audio_files[f.stem] = f

    pairs = []
    for stem, audio_path in audio_files.items():
        for ext in TRANSCRIPT_EXTENSIONS:
            transcript_path = transcript_dir / f"{stem}.{ext}"
            if transcript_path.exists():
                pairs.append((audio_path, transcript_path))
                break

    return pairs


async def import_one(
    audio_path: Path,
    transcript_path: Path,
    category: str | None,
    tags: list[str] | None,
    fmt: str,
    vectorize: bool,
) -> dict:
    """导入单个音频+转写对"""
    from backend.services.audio import AudioService

    service = AudioService()

    transcript_text = transcript_path.read_text(encoding="utf-8")
    detected_fmt = (
        fmt if fmt != "auto" else ("srt" if transcript_path.suffix.lower() == ".srt" else "auto")
    )

    result = await service.import_with_transcript(
        audio_path=str(audio_path),
        transcript_text=transcript_text,
        original_name=audio_path.name,
        category=category,
        tags=tags,
        transcript_format=detected_fmt,
    )

    if vectorize:
        await service.vectorize_segments(result["audio_id"])

    return result


async def main():
    parser = argparse.ArgumentParser(description="从听悟导出数据批量导入")
    parser.add_argument("--audio-dir", required=True, help="音频文件目录")
    parser.add_argument("--transcript-dir", required=True, help="转写文件目录")
    parser.add_argument("--category", default=None, help="分类 (气功/中医/儒家)")
    parser.add_argument("--tags", default=None, help="标签，逗号分隔")
    parser.add_argument(
        "--format",
        default="auto",
        choices=["auto", "srt", "txt"],
        help="转写格式 (默认auto自动检测)",
    )
    parser.add_argument("--vectorize", action="store_true", help="导入后自动向量化分段")
    parser.add_argument("--dry-run", action="store_true", help="仅显示匹配结果，不实际导入")
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    transcript_dir = Path(args.transcript_dir)

    if not audio_dir.is_dir():
        print(f"错误: 音频目录不存在: {audio_dir}")
        sys.exit(1)
    if not transcript_dir.is_dir():
        print(f"错误: 转写目录不存在: {transcript_dir}")
        sys.exit(1)

    pairs = find_matching_pairs(audio_dir, transcript_dir)

    if not pairs:
        print("未找到匹配的音频-转写文件对")
        sys.exit(0)

    print(f"找到 {len(pairs)} 个匹配对:")
    for audio_path, transcript_path in pairs:
        size_mb = audio_path.stat().st_size / 1024 / 1024
        print(f"  {audio_path.name} ({size_mb:.1f}MB) <-> {transcript_path.name}")

    if args.dry_run:
        print("\n[dry-run] 未实际导入")
        return

    tags = args.tags.split(",") if args.tags else None

    success = 0
    failed = 0
    total_segs = 0
    start_time = time.time()

    for i, (audio_path, transcript_path) in enumerate(pairs, 1):
        print(f"\n[{i}/{len(pairs)}] 导入: {audio_path.name}")
        try:
            result = await import_one(
                audio_path,
                transcript_path,
                args.category,
                tags,
                args.format,
                args.vectorize,
            )
            success += 1
            total_segs += result["segments_count"]
            vec_status = " + 向量化" if args.vectorize else ""
            print(
                f"  ✓ audio_id={result['audio_id']}, "
                f"segments={result['segments_count']}, "
                f"duration={result['duration']:.1f}s{vec_status}"
            )
        except Exception as e:
            failed += 1
            print(f"  ✗ 失败: {e}")

    elapsed = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"导入完成: 成功={success}, 失败={failed}, 总分段={total_segs}")
    print(f"耗时: {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
