# 数据处理和导入实施指南

**文档版本**: 1.0
**创建日期**: 2026年3月5日
**适用范围**: 传统国学知识库数据处理流程

---

## 📋 目录

1. [快速开始](#快速开始)
2. [环境准备](#环境准备)
3. [数据采集](#数据采集)
4. [格式转换](#格式转换)
5. [文本提取](#文本提取)
6. [数据清洗](#数据清洗)
7. [向量化处理](#向量化处理)
8. [知识库集成](#知识库集成)
9. [质量检查](#质量检查)
10. [故障排除](#故障排除)

---

## 🚀 快速开始

### 1.1 一键启动脚本

```bash
#!/bin/bash
# quick_start.sh - 快速启动数据处理流程

# 设置环境变量
export DATA_ROOT="/data"
export ORIGINAL_DIR="$DATA_ROOT/original"
export PROCESSED_DIR="$DATA_ROOT/processed"
export LOG_DIR="$DATA_ROOT/logs"

# 创建目录
mkdir -p "$ORIGINAL_DIR" "$PROCESSED_DIR" "$LOG_DIR"

# P0: 导入核心数据
echo "开始导入P0核心数据..."
rclone copy openlist:115/中医资料/2000本·珍贵中医古籍善本·全集 \
  "$ORIGINAL_DIR/tcm_ancient_books/" --progress --log-file="$LOG_DIR/rclone_tcm.log"

rclone copy openlist:115/Zhineng/TXT_for_search \
  "$ORIGINAL_DIR/zhineng_txt/" --progress --log-file="$LOG_DIR/rclone_txt.log"

rclone copy openlist:115/Zhineng/音频/带功口令词/ \
  "$ORIGINAL_DIR/zhineng_audio/" --progress --log-file="$LOG_DIR/rclone_audio.log"

echo "✅ P0数据导入完成"
echo "查看日志: tail -f $LOG_DIR/*.log"
```

### 1.2 使用方法

```bash
# 保存脚本
chmod +x quick_start.sh
./quick_start.sh
```

---

## 🔧 环境准备

### 2.1 系统要求

```bash
# 操作系统: Ubuntu 24.04 或类似
# Python: 3.12+
# 磁盘空间: 至少500GB可用空间
# GPU: NVIDIA GPU (可选，推荐用于AI处理)
```

### 2.2 安装依赖

#### 2.2.1 系统级依赖

```bash
#!/bin/bash
# install_system_deps.sh

# 更新系统
sudo apt-get update && sudo apt-get upgrade -y

# 安装基础工具
sudo apt-get install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    tmux \
    unzip \
    p7zip-full

# 安装PDF处理工具
sudo apt-get install -y \
    poppler-utils \
    pypdf \
    python3-pypdf

# 安装图像处理工具
sudo apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    libtesseract-dev

# 安装音频处理工具
sudo apt-get install -y \
    ffmpeg \
    sox \
    libsox-dev

# 安装视频处理工具
sudo apt-get install -y \
    ffmpeg \
    handbrake-cli

# 安装DJVU处理工具
sudo apt-get install -y \
    djvulibre-bin \
    djview

# 安装Python依赖
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-venv \
    build-essential \
    libssl-dev \
    libffi-dev

echo "✅ 系统依赖安装完成"
```

#### 2.2.2 Python依赖

```bash
#!/bin/bash
# install_python_deps.sh

# 创建虚拟环境
python3 -m venv /data/venv
source /data/venv/bin/activate

# 升级pip
pip install --upgrade pip

# 安装核心依赖
pip install -r /home/ai/zhineng-knowledge-system/services/ai_service/requirements.txt

# 安装额外依赖
pip install \
    pypdf \
    pdfplumber \
    pdfminer.six \
    python-docx \
    openpyxl \
    chardet \
    tqdm \
    rich \
    loguru

# 安装OCR依赖
pip install \
    paddleocr \
    paddlepaddle-gpu

# 安装音频处理
pip install \
    pydub \
    librosa \
    soundfile

echo "✅ Python依赖安装完成"
```

### 2.3 创建目录结构

```bash
#!/bin/bash
# setup_directories.sh

export DATA_ROOT="/data"

# 原始数据目录
mkdir -p "$DATA_ROOT/original/tcm_ancient_books"
mkdir -p "$DATA_ROOT/original/zhineng_txt"
mkdir -p "$DATA_ROOT/original/zhineng_audio"
mkdir -p "$DATA_ROOT/original/zhineng_video"
mkdir -p "$DATA_ROOT/original/sikuquanshu"

# 处理后数据目录
mkdir -p "$DATA_ROOT/processed/pdf_text"
mkdir -p "$DATA_ROOT/processed/audio_transcripts"
mkdir -p "$DATA_ROOT/processed/cleaned_text"
mkdir -p "$DATA_ROOT/processed/embeddings"
mkdir -p "$DATA_ROOT/processed/metadata"

# 缓存目录
mkdir -p "$DATA_ROOT/cache/pdf_cache"
mkdir -p "$DATA_ROOT/cache/audio_cache"
mkdir -p "$DATA_ROOT/cache/video_cache"

# 日志目录
mkdir -p "$DATA_ROOT/logs/import"
mkdir -p "$DATA_ROOT/logs/processing"
mkdir -p "$DATA_ROOT/logs/vectorization"

echo "✅ 目录结构创建完成"
```

---

## 📥 数据采集

### 3.1 使用rclone复制数据

#### 3.1.1 基础命令

```bash
# 复制单个目录
rclone copy openlist:115/中医资料/2000本·珍贵中医古籍善本·全集 \
  /data/original/tcm_ancient_books/ --progress

# 查看复制进度
rclone copy openlist:115/Zhineng/TXT_for_search \
  /data/original/zhineng_txt/ --progress --stats 1m

# 限制传输速度 (10MB/s)
rclone copy openlist:115/Zhineng/音频/带功口令词/ \
  /data/original/zhineng_audio/ --progress --bwlimit 10M
```

#### 3.1.2 批量复制脚本

```python
#!/usr/bin/env python3
# batch_import.py

import subprocess
import logging
from pathlib import Path
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/import/batch_import.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 数据源配置
DATA_SOURCES = {
    "P0": [
        {
            "name": "中医古籍善本全集",
            "source": "openlist:115/中医资料/2000本·珍贵中医古籍善本·全集",
            "dest": "/data/original/tcm_ancient_books",
            "priority": "high"
        },
        {
            "name": "智能气功搜索文本",
            "source": "openlist:115/Zhineng/TXT_for_search",
            "dest": "/data/original/zhineng_txt",
            "priority": "high"
        },
        {
            "name": "带功口令词",
            "source": "openlist:115/Zhineng/音频/带功口令词",
            "dest": "/data/original/zhineng_audio",
            "priority": "high"
        }
    ],
    "P1": [
        {
            "name": "四库全书",
            "source": "openlist:115/国学大师/四库全书",
            "dest": "/data/original/sikuquanshu",
            "priority": "medium"
        },
        {
            "name": "视频资料",
            "source": "openlist:115/Zhineng/视频",
            "dest": "/data/original/zhineng_video",
            "priority": "medium"
        }
    ]
}

def rclone_copy(source, dest, name, priority):
    """使用rclone复制数据"""

    # 创建目标目录
    Path(dest).mkdir(parents=True, exist_ok=True)

    # 构建命令
    cmd = [
        "rclone", "copy",
        source, dest,
        "--progress",
        "--transfers", "4",
        "--checkers", "8",
        "--log-file", f"/data/logs/import/{name.replace('/', '_')}.log",
        "--stats", "1m",
        "--stats-unit", "MB"
    ]

    logger.info(f"开始复制: {name} (优先级: {priority})")
    logger.info(f"源: {source}")
    logger.info(f"目标: {dest}")

    start_time = datetime.now()

    try:
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        if result.returncode == 0:
            logger.info(f"✅ 复制成功: {name}")
            logger.info(f"耗时: {duration:.2f}秒")

            # 统计文件数量
            file_count = sum(1 for _ in Path(dest).rglob("*") if _.is_file())
            logger.info(f"文件数量: {file_count}")

            return True
        else:
            logger.error(f"❌ 复制失败: {name}")
            logger.error(f"返回码: {result.returncode}")
            logger.error(f"错误输出: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"❌ 复制异常: {name}, 错误: {e}")
        return False

def main():
    """主函数"""

    logger.info("="*80)
    logger.info("开始批量数据导入")
    logger.info("="*80)

    total_success = 0
    total_failed = 0

    # 按优先级处理
    for priority, sources in DATA_SOURCES.items():
        logger.info(f"\n{'='*80}")
        logger.info(f"处理优先级: {priority}")
        logger.info(f"{'='*80}\n")

        for source_config in sources:
            name = source_config["name"]
            source = source_config["source"]
            dest = source_config["dest"]
            priority_level = source_config["priority"]

            success = rclone_copy(source, dest, name, priority_level)

            if success:
                total_success += 1
            else:
                total_failed += 1

    # 总结
    logger.info(f"\n{'='*80}")
    logger.info("导入完成")
    logger.info(f"{'='*80}")
    logger.info(f"成功: {total_success}")
    logger.info(f"失败: {total_failed}")
    logger.info(f"总计: {total_success + total_failed}")

if __name__ == "__main__":
    main()
```

#### 3.1.3 监控复制进度

```bash
#!/bin/bash
# monitor_progress.sh

# 查看rclone日志
tail -f /data/logs/import/*.log

# 或者使用tmux分屏监控
tmux new-session -d -s 'rclone_monitor' \
  'tail -f /data/logs/import/tcm_ancient.log' \; \
  split-window -h 'tail -f /data/logs/import/zhineng_txt.log' \; \
  split-window -v 'tail -f /data/logs/import/zhineng_audio.log'

# 查看磁盘使用情况
watch -n 5 'df -h /data'
```

### 3.2 验证数据完整性

```python
#!/usr/bin/env python3
# verify_import.py

import hashlib
from pathlib import Path
import json

def calculate_file_hash(file_path, algorithm='md5'):
    """计算文件哈希"""
    hash_func = hashlib.new(algorithm)

    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_func.update(chunk)

    return hash_func.hexdigest()

def scan_directory(directory):
    """扫描目录并记录文件信息"""
    results = []

    for file_path in Path(directory).rglob("*"):
        if file_path.is_file():
            try:
                stat = file_path.stat()

                file_info = {
                    "path": str(file_path),
                    "name": file_path.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "hash_md5": calculate_file_hash(file_path)
                }

                results.append(file_info)

            except Exception as e:
                print(f"警告: 无法处理文件 {file_path}, 错误: {e}")

    return results

def main():
    """主函数"""

    print("开始验证导入数据...")

    directories = [
        "/data/original/tcm_ancient_books",
        "/data/original/zhineng_txt",
        "/data/original/zhineng_audio"
    ]

    for directory in directories:
        print(f"\n扫描目录: {directory}")

        if not Path(directory).exists():
            print(f"⚠️ 目录不存在: {directory}")
            continue

        files = scan_directory(directory)

        print(f"文件数量: {len(files)}")

        total_size = sum(f['size'] for f in files)
        print(f"总大小: {total_size / (1024**3):.2f} GB")

        # 保存验证结果
        output_file = Path(directory) / "verification.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(files, f, ensure_ascii=False, indent=2)

        print(f"✅ 验证结果已保存到: {output_file}")

if __name__ == "__main__":
    main()
```

---

## 🔄 格式转换

### 4.1 DJVU转PDF

#### 4.1.1 转换脚本

```python
#!/usr/bin/env python3
# djvu_to_pdf.py

import subprocess
from pathlib import Path
import logging
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/processing/djvu_to_pdf.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def convert_djvu_to_pdf(djvu_path, pdf_path):
    """将DJVU文件转换为PDF"""

    cmd = [
        "djvulibre-bin",
        "djvu2pdf",
        str(djvu_path),
        str(pdf_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and Path(pdf_path).exists():
            return True
        else:
            logger.error(f"转换失败: {djvu_path}")
            logger.error(f"错误: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"转换异常: {djvu_path}, 错误: {e}")
        return False

def process_directory(input_dir, output_dir):
    """批量处理目录"""

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 查找所有DJVU文件
    djvu_files = list(input_path.rglob("*.djvu"))

    logger.info(f"找到 {len(djvu_files)} 个DJVU文件")

    success_count = 0
    failed_count = 0

    for djvu_file in tqdm(djvu_files, desc="转换DJVU文件"):
        # 保持目录结构
        relative_path = djvu_file.relative_to(input_path)
        pdf_file = output_path / relative_path.with_suffix('.pdf')
        pdf_file.parent.mkdir(parents=True, exist_ok=True)

        # 转换
        if convert_djvu_to_pdf(djvu_file, pdf_file):
            success_count += 1
        else:
            failed_count += 1

    logger.info(f"转换完成: 成功 {success_count}, 失败 {failed_count}")

def main():
    """主函数"""

    logger.info("开始DJVU到PDF转换")

    process_directory(
        "/data/original/guji",
        "/data/processed/pdf_converted"
    )

if __name__ == "__main__":
    main()
```

### 4.2 视频转码

#### 4.2.1 转码脚本

```python
#!/usr/bin/env python3
# video_transcode.py

import subprocess
from pathlib import Path
import logging
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/processing/video_transcode.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def transcode_video(input_file, output_file):
    """使用ffmpeg转码视频"""

    cmd = [
        "ffmpeg",
        "-i", str(input_file),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-y",
        str(output_file)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and Path(output_file).exists():
            return True
        else:
            logger.error(f"转码失败: {input_file}")
            logger.error(f"错误: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"转码异常: {input_file}, 错误: {e}")
        return False

def process_directory(input_dir, output_dir):
    """批量处理目录"""

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 查找所有视频文件
    video_extensions = ['.mpg', '.mpg', '.rm', '.rmvb', '.avi', '.mkv']
    video_files = []

    for ext in video_extensions:
        video_files.extend(input_path.rglob(f"*{ext}"))

    logger.info(f"找到 {len(video_files)} 个视频文件")

    success_count = 0
    failed_count = 0

    for video_file in tqdm(video_files, desc="转码视频文件"):
        # 保持目录结构
        relative_path = video_file.relative_to(input_path)
        output_file = output_path / relative_path.with_suffix('.mp4')
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 转码
        if transcode_video(video_file, output_file):
            success_count += 1
        else:
            failed_count += 1

    logger.info(f"转码完成: 成功 {success_count}, 失败 {failed_count}")

def main():
    """主函数"""

    logger.info("开始视频转码")

    process_directory(
        "/data/original/zhineng_video",
        "/data/processed/video_converted"
    )

if __name__ == "__main__":
    main()
```

---

## 📝 文本提取

### 5.1 PDF文本提取

```python
#!/usr/bin/env python3
# pdf_text_extractor.py

import pypdf
from pathlib import Path
import logging
from tqdm import tqdm
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/processing/pdf_extraction.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path):
    """从PDF提取文本"""

    text = ""

    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)

            for page in pdf_reader.pages:
                page_text = page.extract_text()
                text += page_text + "\n"

        return text

    except Exception as e:
        logger.error(f"提取失败: {pdf_path}, 错误: {e}")
        return None

def process_pdf_directory(input_dir, output_dir):
    """批量处理PDF目录"""

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 查找所有PDF文件
    pdf_files = list(input_path.rglob("*.pdf"))

    logger.info(f"找到 {len(pdf_files)} 个PDF文件")

    results = []
    success_count = 0
    failed_count = 0

    for pdf_file in tqdm(pdf_files, desc="提取PDF文本"):
        # 提取文本
        text = extract_text_from_pdf(pdf_file)

        if text and len(text) > 100:  # 过滤过短的文本
            # 保存文本
            relative_path = pdf_file.relative_to(input_path)
            text_file = output_path / relative_path.with_suffix('.txt')
            text_file.parent.mkdir(parents=True, exist_ok=True)

            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(text)

            # 获取PDF信息
            with open(pdf_file, 'rb') as f:
                pdf_reader = pypdf.PdfReader(f)
                page_count = len(pdf_reader.pages)

            results.append({
                "pdf_file": str(pdf_file),
                "text_file": str(text_file),
                "char_count": len(text),
                "page_count": page_count,
                "size_mb": pdf_file.stat().st_size / (1024*1024)
            })

            success_count += 1
        else:
            failed_count += 1

    # 保存结果摘要
    summary_file = output_path / "extraction_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"提取完成: 成功 {success_count}, 失败 {failed_count}")
    logger.info(f"摘要已保存到: {summary_file}")

def main():
    """主函数"""

    logger.info("开始PDF文本提取")

    process_pdf_directory(
        "/data/processed/pdf_converted",
        "/data/processed/pdf_text"
    )

if __name__ == "__main__":
    main()
```

### 5.2 音频转文字 (Paraformer)

```python
#!/usr/bin/env python3
# audio_transcriber.py

from funasr import AutoModel
import torch
from pathlib import Path
import logging
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/processing/audio_transcription.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 检查GPU可用性
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"使用设备: {device}")

# 加载Paraformer模型
logger.info("正在加载Paraformer模型...")
model = AutoModel(
    model="paraformer-zh",
    batch_size_s=300,
    device=device
)
logger.info("模型加载完成")

def transcribe_audio(audio_path):
    """转写音频文件"""

    try:
        res = model.generate(
            input=str(audio_path),
            batch_size_s=300,
            cache={},
            language="zh",  # 中文
            use_itn=True,
        )

        return res[0]["text"]

    except Exception as e:
        logger.error(f"转写失败: {audio_path}, 错误: {e}")
        return None

def process_audio_directory(input_dir, output_dir):
    """批量处理音频目录"""

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 查找所有音频文件
    audio_files = list(input_path.rglob("*.mp3"))

    logger.info(f"找到 {len(audio_files)} 个音频文件")

    success_count = 0
    failed_count = 0

    for audio_file in tqdm(audio_files, desc="转写音频文件"):
        # 转写音频
        text = transcribe_audio(audio_file)

        if text and len(text) > 10:  # 过滤过短的文本
            # 保存转写文本
            relative_path = audio_file.relative_to(input_path)
            text_file = output_path / relative_path.with_suffix('.txt')
            text_file.parent.mkdir(parents=True, exist_ok=True)

            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(text)

            logger.info(f"✅ 转写完成: {audio_file.name}")
            success_count += 1
        else:
            logger.warning(f"⚠️ 转写结果为空: {audio_file.name}")
            failed_count += 1

    logger.info(f"转写完成: 成功 {success_count}, 失败 {failed_count}")

def main():
    """主函数"""

    logger.info("开始音频转写")

    process_audio_directory(
        "/data/original/zhineng_audio",
        "/data/processed/audio_transcripts"
    )

if __name__ == "__main__":
    main()
```

---

## 🧹 数据清洗

### 6.1 清洗脚本

```python
#!/usr/bin/env python3
# data_cleaner.py

import re
from pathlib import Path
import logging
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/processing/cleaning.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def clean_text(text):
    """清洗文本"""

    # 移除多余空白
    text = re.sub(r'\n\s*\n', '\n\n', text)  # 多个空行变两个
    text = re.sub(r' +', ' ', text)  # 多个空格变一个
    text = re.sub(r'\t+', ' ', text)  # 制表符变空格

    # 移除页码
    text = re.sub(r'\n\s*\d+\s*\n', '\n', text)

    # 移除页眉页脚
    text = re.sub(r'\n\s*第\s*\d+\s*页\s*\n', '\n', text)

    # 移除特殊字符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # 规范化标点
    text = re.sub(r'，', '，', text)
    text = re.sub(r'。', '。', text)
    text = re.sub(r'、', '、', text)

    # 移除重复段落
    paragraphs = text.split('\n')
    unique_paragraphs = []
    for para in paragraphs:
        if para.strip() and para not in unique_paragraphs:
            unique_paragraphs.append(para)

    text = '\n'.join(unique_paragraphs)

    return text

def process_text_directory(input_dir, output_dir):
    """批量清洗文本"""

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 查找所有文本文件
    text_files = list(input_path.rglob("*.txt"))

    logger.info(f"找到 {len(text_files)} 个文本文件")

    success_count = 0
    failed_count = 0

    for text_file in tqdm(text_files, desc="清洗文本"):
        try:
            # 读取文本
            with open(text_file, 'r', encoding='utf-8') as f:
                text = f.read()

            # 清洗文本
            cleaned_text = clean_text(text)

            # 保存清洗后的文本
            relative_path = text_file.relative_to(input_path)
            cleaned_file = output_path / relative_path
            cleaned_file.parent.mkdir(parents=True, exist_ok=True)

            with open(cleaned_file, 'w', encoding='utf-8') as f:
                f.write(cleaned_text)

            success_count += 1

        except Exception as e:
            logger.error(f"清洗失败: {text_file}, 错误: {e}")
            failed_count += 1

    logger.info(f"清洗完成: 成功 {success_count}, 失败 {failed_count}")

def main():
    """主函数"""

    logger.info("开始数据清洗")

    process_text_directory(
        "/data/processed/pdf_text",
        "/data/processed/cleaned_text"
    )

if __name__ == "__main__":
    main()
```

---

## 🔢 向量化处理

### 7.1 向量化脚本

```python
#!/usr/bin/env python3
# vectorizer.py

from sentence_transformers import SentenceTransformer
from pathlib import Path
import numpy as np
import json
import logging
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/vectorization/vectorization.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 加载BGE-M3模型
logger.info("正在加载BGE-M3模型...")
model = SentenceTransformer('BAAI/bge-m3')
logger.info("模型加载完成")

def chunk_text(text, chunk_size=512, overlap=50):
    """将文本分块"""

    chunks = []

    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i+chunk_size]
        if len(chunk) > 50:  # 过滤过短的块
            chunks.append(chunk)

    return chunks

def vectorize_chunks(chunks):
    """向量化文本块"""

    embeddings = model.encode(
        chunks,
        show_progress_bar=False,
        batch_size=32,
        normalize_embeddings=True
    )

    return embeddings

def process_text_directory(input_dir, output_dir):
    """批量向量化"""

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 查找所有文本文件
    text_files = list(input_path.rglob("*.txt"))

    logger.info(f"找到 {len(text_files)} 个文本文件")

    results = []

    for text_file in tqdm(text_files, desc="向量化文本"):
        try:
            # 读取文本
            with open(text_file, 'r', encoding='utf-8') as f:
                text = f.read()

            # 分块
            chunks = chunk_text(text)
            if not chunks:
                continue

            # 向量化
            embeddings = vectorize_chunks(chunks)

            # 保存嵌入
            relative_path = text_file.relative_to(input_path)
            embedding_file = output_path / relative_path.with_suffix('.npy')
            embedding_file.parent.mkdir(parents=True, exist_ok=True)

            np.save(embedding_file, embeddings)

            # 保存块文本
            chunks_file = output_path / f"{text_file.stem}_chunks.json"
            with open(chunks_file, 'w', encoding='utf-8') as f:
                json.dump(chunks, f, ensure_ascii=False)

            # 记录元数据
            results.append({
                "text_file": str(text_file),
                "embedding_file": str(embedding_file),
                "chunks_file": str(chunks_file),
                "chunk_count": len(chunks),
                "embedding_dim": embeddings.shape[1]
            })

        except Exception as e:
            logger.error(f"向量化失败: {text_file}, 错误: {e}")

    # 保存结果摘要
    summary_file = output_path / "vectorization_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"向量化完成: 处理 {len(results)} 个文件")
    logger.info(f"摘要已保存到: {summary_file}")

def main():
    """主函数"""

    logger.info("开始向量化处理")

    process_text_directory(
        "/data/processed/cleaned_text",
        "/data/processed/embeddings"
    )

if __name__ == "__main__":
    main()
```

---

## 📚 知识库集成

### 8.1 导入Milvus

```python
#!/usr/bin/env python3
# import_to_milvus.py

from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, connections, utility
import numpy as np
import json
from pathlib import Path
import logging
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/vectorization/milvus_import.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 连接Milvus
connections.connect(host="localhost", port="19530")

COLLECTION_NAME = "tcm_knowledge_base"

def create_collection():
    """创建Milvus集合"""

    if utility.has_collection(COLLECTION_NAME):
        logger.info(f"集合 {COLLECTION_NAME} 已存在")
        return Collection(COLLECTION_NAME)

    # 定义字段
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="domain", dtype=DataType.VARCHAR, max_length=255),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024)
    ]

    # 创建schema
    schema = CollectionSchema(
        fields,
        description="中医知识库",
        enable_dynamic_field=True
    )

    # 创建集合
    collection = Collection(
        name=COLLECTION_NAME,
        schema=schema
    )

    # 创建索引
    index_params = {
        "index_type": "HNSW",
        "metric_type": "COSINE",
        "params": {
            "M": 16,
            "efConstruction": 256
        }
    }

    collection.create_index(
        field_name="embedding",
        index_params=index_params
    )

    logger.info(f"集合 {COLLECTION_NAME} 创建成功")

    return collection

def import_embeddings(embeddings_dir, domain):
    """导入嵌入向量"""

    collection = create_collection()
    embeddings_path = Path(embeddings_dir)

    # 查找所有嵌入文件
    embedding_files = list(embeddings_path.rglob("*.npy"))

    logger.info(f"找到 {len(embedding_files)} 个嵌入文件")

    total_chunks = 0

    for embedding_file in tqdm(embedding_files, desc="导入嵌入向量"):
        try:
            # 加载嵌入
            embeddings = np.load(embedding_file)

            # 加载块文本
            chunks_file = embedding_file.with_name(f"{embedding_file.stem}_chunks.json")
            with open(chunks_file, 'r', encoding='utf-8') as f:
                chunks = json.load(f)

            # 准备数据
            data = [
                chunks,
                [str(embedding_file)] * len(chunks),
                [domain] * len(chunks),
                embeddings
            ]

            # 插入Milvus
            collection.insert(data)

            total_chunks += len(chunks)

        except Exception as e:
            logger.error(f"导入失败: {embedding_file}, 错误: {e}")

    # 刷新数据
    collection.flush()

    logger.info(f"导入完成: 总共 {total_chunks} 个向量")

    # 加载集合
    collection.load()

    logger.info("集合已加载，可以开始查询")

def main():
    """主函数"""

    logger.info("开始导入Milvus")

    # 导入中医古籍
    import_embeddings("/data/processed/embeddings/tcm_ancient", "中医古籍")

    # 导入智能气功
    import_embeddings("/data/processed/embeddings/zhineng", "智能气功")

if __name__ == "__main__":
    main()
```

---

## ✅ 质量检查

### 9.1 数据质量检查脚本

```python
#!/usr/bin/env python3
# quality_checker.py

from pathlib import Path
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def check_data_quality(directory):
    """检查数据质量"""

    dir_path = Path(directory)

    # 统计文件
    files = list(dir_path.rglob("*"))
    files = [f for f in files if f.is_file()]

    # 统计不同类型文件
    file_types = {}
    for file in files:
        ext = file.suffix.lower()
        file_types[ext] = file_types.get(ext, 0) + 1

    # 计算总大小
    total_size = sum(f.stat().st_size for f in files)

    # 输出报告
    print(f"\n{'='*60}")
    print(f"数据质量检查报告: {directory}")
    print(f"{'='*60}")
    print(f"文件总数: {len(files)}")
    print(f"总大小: {total_size / (1024**3):.2f} GB")
    print(f"\n文件类型分布:")
    for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ext}: {count}")

def main():
    """主函数"""

    # 检查原始数据
    check_data_quality("/data/original")

    # 检查处理后数据
    check_data_quality("/data/processed")

if __name__ == "__main__":
    main()
```

---

## 🔧 故障排除

### 10.1 常见问题

#### 10.1.1 rclone连接失败

**问题**: rclone无法连接到openlist

**解决方案**:
```bash
# 检查Alist服务状态
ps aux | grep alist

# 重启Alist服务
pkill -f "alist server"
alist server start

# 测试rclone连接
rclone lsd openlist:
```

#### 10.1.2 DJVU转换失败

**问题**: DJVU文件无法转换为PDF

**解决方案**:
```bash
# 重新安装DJVU工具
sudo apt-get remove --purge djvulibre-bin
sudo apt-get install djvulibre-bin

# 单独测试转换
djvu2pdf test.djvu test.pdf
```

#### 10.1.3 内存不足

**问题**: 处理大量数据时内存不足

**解决方案**:
```python
# 分批处理
def process_in_batches(files, batch_size=100):
    for i in range(0, len(files), batch_size):
        batch = files[i:i+batch_size]
        yield batch

# 使用生成器
for batch in process_in_batches(files):
    process_batch(batch)
    # 清理内存
    import gc
    gc.collect()
```

---

## 📊 附录

### A. 完整流程图

```
原始数据 (Openlist)
    ↓
rclone复制
    ↓
格式转换 (DJVU→PDF, 视频→MP4)
    ↓
文本提取 (PDF→TXT, 音频→TXT)
    ↓
数据清洗 (去重、格式化)
    ↓
向量化 (BGE-M3)
    ↓
Milvus索引
    ↓
Elasticsearch全文索引
    ↓
知识库集成
```

### B. 环境变量配置

```bash
# .env配置
DATA_ROOT=/data
LOG_DIR=/data/logs
CACHE_DIR=/data/cache
EMBEDDING_DIM=1024
CHUNK_SIZE=512
CHUNK_OVERLAP=50

# Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Elasticsearch配置
ES_HOST=localhost
ES_PORT=9200
```

### C. 配套脚本列表

| 脚本名称 | 功能 | 优先级 |
|---------|------|--------|
| quick_start.sh | 快速启动 | 高 |
| batch_import.py | 批量导入 | 高 |
| djvu_to_pdf.py | DJVU转PDF | 中 |
| video_transcode.py | 视频转码 | 中 |
| pdf_text_extractor.py | PDF文本提取 | 高 |
| audio_transcriber.py | 音频转写 | 高 |
| data_cleaner.py | 数据清洗 | 高 |
| vectorizer.py | 向量化 | 高 |
| import_to_milvus.py | 导入Milvus | 高 |
| quality_checker.py | 质量检查 | 中 |

---

**文档版本**: 1.0
**最后更新**: 2026年3月5日
**维护者**: AI Assistant
