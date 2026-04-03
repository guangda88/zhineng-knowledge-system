#!/usr/bin/env python3
"""从通义听悟批量下载音频 + 转写结果

用法:
    # 从 task ID 文件下载
    python scripts/download_from_tingwu.py --task-ids task_ids.txt

    # 直接指定 task IDs (逗号分隔)
    python scripts/download_from_tingwu.py --task-ids id1,id2,id3

    # 指定下载目录和并发数
    python scripts/download_from_tingwu.py --task-ids task_ids.txt \
        --audio-dir /data/audio/raw --transcript-dir /data/audio/transcripts \
        --concurrency 5

    # 仅下载转写结果（不下载音频）
    python scripts/download_from_tingwu.py --task-ids task_ids.txt --transcripts-only

    # 跳过已下载的文件
    python scripts/download_from_tingwu.py --task-ids task_ids.txt --skip-existing

前置条件:
    - 设置环境变量: ALIYUN_ACCESS_KEY_ID 和 ALIYUN_ACCESS_KEY_SECRET
    - 或者在 .env 中配置
    - 安装依赖: pip install alibabacloud-tingwu20230930

获取 task ID 列表的方法:
    听悟 OpenAPI 没有列表接口，需要手动获取 task ID:
    1. 登录 https://tingwu.aliyun.com
    2. 进入文件夹页面 (如 /folders/265086)
    3. 打开浏览器开发者工具 (F12) -> Network 标签
    4. 刷新页面，找到请求路径含 "task" 或 "list" 的 XHR 请求
    5. 从响应中提取所有 TaskId 字段
    6. 保存到文件，每行一个 task ID

    或者直接在控制台页面逐页查看，从 URL 中提取 task ID。
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_AUDIO_DIR = "/data/audio/raw"
DEFAULT_TRANSCRIPT_DIR = "/data/audio/transcripts"
MAX_CONCURRENCY = 5
GET_TASK_INFO_QPS = 100
DOWNLOAD_TIMEOUT = 600
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5


def load_task_ids(source: str) -> list[str]:
    """加载 task ID 列表"""
    source = source.strip()
    if "," in source:
        ids = [tid.strip() for tid in source.split(",") if tid.strip()]
    else:
        p = Path(source)
        if p.is_file():
            ids = []
            for line in p.read_text(encoding="utf-8").splitlines():
                tid = line.strip()
                if tid and not tid.startswith("#"):
                    ids.append(tid)
        else:
            ids = [source]

    if not ids:
        print("错误: 未找到有效的 task ID")
        sys.exit(1)

    return ids


def sanitize_filename(name: str, max_len: int = 200) -> str:
    """清理文件名"""
    keepchars = (" ", "-", "_", "(", ")", "（", "）", "．", ".", "·")
    cleaned = "".join(c if c.isalnum() or c in keepchars else "_" for c in name)
    return cleaned[:max_len]


class TingwuDownloader:
    """听悟音频 + 转写下载器"""

    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        audio_dir: str,
        transcript_dir: str,
        concurrency: int = MAX_CONCURRENCY,
        transcripts_only: bool = False,
        skip_existing: bool = False,
    ):
        self._access_key_id = access_key_id
        self._access_key_secret = access_key_secret
        self._audio_dir = Path(audio_dir)
        self._transcript_dir = Path(transcript_dir)
        self._concurrency = min(concurrency, MAX_CONCURRENCY)
        self._transcripts_only = transcripts_only
        self._skip_existing = skip_existing
        self._client = None
        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._stats = {"downloaded": 0, "skipped": 0, "failed": 0, "bytes": 0}

        self._audio_dir.mkdir(parents=True, exist_ok=True)
        self._transcript_dir.mkdir(parents=True, exist_ok=True)

    def _init_client(self):
        """初始化听悟 SDK 客户端"""
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tingwu20230930.client import Client as TingwuClient

        config = open_api_models.Config(
            access_key_id=self._access_key_id,
            access_key_secret=self._access_key_secret,
            region_id="cn-hangzhou",
        )
        self._client = TingwuClient(config)
        logger.info("听悟 SDK 客户端初始化成功")

    async def _get_task_info(self, task_id: str) -> Optional[dict]:
        """调用 GetTaskInfo 获取任务详情"""
        try:
            response = await asyncio.to_thread(
                self._client.get_task_info_with_options,
                task_id,
                None, None, None,
            )

            if response.status_code != 200 or not response.body:
                logger.error(f"GetTaskInfo 失败 [{task_id}]: HTTP {response.status_code}")
                return None

            data = response.body.data
            body = {
                "task_id": data.task_id,
                "task_status": (data.task_status or "UNKNOWN"),
            }

            if hasattr(data, "output_mp3_path") and data.output_mp3_path:
                body["audio_url"] = data.output_mp3_path

            if hasattr(data, "result") and data.result:
                result = data.result
                if hasattr(result, "transcription") and result.transcription:
                    body["transcription_url"] = result.transcription

            if hasattr(data, "error_message") and data.error_message:
                body["error_message"] = data.error_message

            return body

        except Exception as e:
            logger.error(f"GetTaskInfo 异常 [{task_id}]: {e}")
            return None

    async def _download_file(
        self,
        url: str,
        save_path: Path,
        desc: str = "",
    ) -> bool:
        """下载文件，支持大文件分块和重试"""
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
                ) as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            logger.error(
                                f"下载失败 [{desc}]: HTTP {resp.status} (尝试 {attempt}/{RETRY_ATTEMPTS})"
                            )
                            if attempt < RETRY_ATTEMPTS:
                                await asyncio.sleep(RETRY_DELAY * attempt)
                            continue

                        total_size = resp.content_length or 0
                        tmp_path = save_path.with_suffix(save_path.suffix + ".tmp")
                        downloaded = 0

                        with open(tmp_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(1024 * 1024):
                                f.write(chunk)
                                downloaded += len(chunk)

                        tmp_path.rename(save_path)

                        size_mb = downloaded / 1024 / 1024
                        logger.info(f"  ✓ {desc}: {size_mb:.1f}MB -> {save_path.name}")
                        self._stats["bytes"] += downloaded
                        return True

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(
                    f"下载异常 [{desc}] (尝试 {attempt}/{RETRY_ATTEMPTS}): {e}"
                )
                if attempt < RETRY_ATTEMPTS:
                    await asyncio.sleep(RETRY_DELAY * attempt)

            except Exception as e:
                logger.error(f"下载严重错误 [{desc}]: {e}")
                break

        return False

    async def _process_task(self, task_id: str, index: int, total: int):
        """处理单个 task: 获取信息 -> 下载音频 + 转写"""
        async with self._semaphore:
            prefix = f"[{index}/{total}]"
            logger.info(f"{prefix} 处理 task: {task_id}")

            task_info = await self._get_task_info(task_id)
            if not task_info:
                self._stats["failed"] += 1
                return

            status = task_info.get("task_status", "UNKNOWN")
            if status not in ("COMPLETED", "SUCCEEDED"):
                error = task_info.get("error_message", "")
                logger.error(f"{prefix} task 状态={status}, 跳过 (error: {error})")
                self._stats["failed"] += 1
                return

            audio_url = task_info.get("audio_url")
            transcription_url = task_info.get("transcription_url")

            if not audio_url and not transcription_url:
                logger.error(f"{prefix} 无下载链接，跳过")
                self._stats["failed"] += 1
                return

            base_name = task_id

            if transcription_url:
                transcript_path = self._transcript_dir / f"{base_name}.json"
                if self._skip_existing and transcript_path.exists():
                    logger.info(f"  跳过已存在: {transcript_path.name}")
                else:
                    ok = await self._download_file(
                        transcription_url, transcript_path, f"转写 {task_id[:12]}..."
                    )
                    if ok:
                        base_name = self._extract_name_from_transcript(
                            transcript_path, task_id
                        )
                    elif not self._transcripts_only:
                        self._stats["failed"] += 1
                        return

            if not self._transcripts_only and audio_url:
                audio_path = self._audio_dir / f"{base_name}.mp3"
                if self._skip_existing and audio_path.exists():
                    logger.info(f"  跳过已存在: {audio_path.name}")
                else:
                    ok = await self._download_file(
                        audio_url, audio_path, f"音频 {task_id[:12]}..."
                    )
                    if not ok:
                        self._stats["failed"] += 1
                        return

            self._stats["downloaded"] += 1

    def _extract_name_from_transcript(self, json_path: Path, fallback: str) -> str:
        """尝试从转写 JSON 中提取原始文件名作为更友好的文件名"""
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            return fallback

        segments = data.get("Sentences", [])
        if not segments:
            return fallback

        first_text = segments[0].get("Text", "")[:30].strip()
        if first_text:
            return sanitize_filename(first_text)

        return fallback

    async def run(self, task_ids: list[str]):
        """批量下载"""
        if not self._client:
            self._init_client()

        total = len(task_ids)
        logger.info(f"开始下载 {total} 个任务的音频 + 转写")
        logger.info(f"  音频目录: {self._audio_dir}")
        logger.info(f"  转写目录: {self._transcript_dir}")
        logger.info(f"  并发数: {self._concurrency}")
        if self._transcripts_only:
            logger.info("  模式: 仅转写 (不下载音频)")
        if self._skip_existing:
            logger.info("  跳过已存在文件")

        start = time.time()
        tasks = [
            self._process_task(tid, i + 1, total)
            for i, tid in enumerate(task_ids)
        ]
        await asyncio.gather(*tasks)

        elapsed = time.time() - start
        total_mb = self._stats["bytes"] / 1024 / 1024

        print(f"\n{'='*60}")
        print(f"下载完成")
        print(f"  成功: {self._stats['downloaded']}")
        print(f"  跳过: {self._stats['skipped']}")
        print(f"  失败: {self._stats['failed']}")
        print(f"  总大小: {total_mb:.1f}MB ({total_mb/1024:.2f}GB)")
        print(f"  耗时: {elapsed:.1f}s")
        print(f"{'='*60}")

        manifest = {
            "download_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tasks": total,
            "downloaded": self._stats["downloaded"],
            "failed": self._stats["failed"],
            "total_bytes": self._stats["bytes"],
            "task_ids": task_ids,
        }
        manifest_path = self._audio_dir.parent / "download_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        logger.info(f"下载清单已保存: {manifest_path}")


async def main():
    parser = argparse.ArgumentParser(
        description="从通义听悟批量下载音频 + 转写结果",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--task-ids", required=True,
        help="task ID 文件路径 或 逗号分隔的 task ID 列表",
    )
    parser.add_argument(
        "--audio-dir", default=DEFAULT_AUDIO_DIR,
        help=f"音频保存目录 (默认: {DEFAULT_AUDIO_DIR})",
    )
    parser.add_argument(
        "--transcript-dir", default=DEFAULT_TRANSCRIPT_DIR,
        help=f"转写保存目录 (默认: {DEFAULT_TRANSCRIPT_DIR})",
    )
    parser.add_argument(
        "--concurrency", type=int, default=3,
        help=f"并发下载数 (默认: 3, 最大: {MAX_CONCURRENCY})",
    )
    parser.add_argument(
        "--transcripts-only", action="store_true",
        help="仅下载转写结果，不下载音频文件",
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="跳过已存在的文件",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅验证 task IDs，不下载",
    )
    args = parser.parse_args()

    key_id = os.environ.get("ALIYUN_ACCESS_KEY_ID")
    key_secret = os.environ.get("ALIYUN_ACCESS_KEY_SECRET")

    if not key_id or not key_secret:
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k == "ALIYUN_ACCESS_KEY_ID" and not key_id:
                        key_id = v
                    elif k == "ALIYUN_ACCESS_KEY_SECRET" and not key_secret:
                        key_secret = v

    if not key_id or not key_secret:
        print("错误: 需要设置 ALIYUN_ACCESS_KEY_ID 和 ALIYUN_ACCESS_KEY_SECRET")
        print("  方式1: 环境变量")
        print("  方式2: 在 .env 文件中添加")
        print("  方式3: export ALIYUN_ACCESS_KEY_ID=xxx ALIYUN_ACCESS_KEY_SECRET=xxx")
        sys.exit(1)

    task_ids = load_task_ids(args.task_ids)
    print(f"加载了 {len(task_ids)} 个 task ID")

    if args.dry_run:
        print("task IDs:")
        for i, tid in enumerate(task_ids, 1):
            print(f"  {i}. {tid}")
        print("\n[dry-run] 未实际下载")
        return

    downloader = TingwuDownloader(
        access_key_id=key_id,
        access_key_secret=key_secret,
        audio_dir=args.audio_dir,
        transcript_dir=args.transcript_dir,
        concurrency=args.concurrency,
        transcripts_only=args.transcripts_only,
        skip_existing=args.skip_existing,
    )
    await downloader.run(task_ids)


if __name__ == "__main__":
    asyncio.run(main())
