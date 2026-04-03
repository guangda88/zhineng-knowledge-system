# 阿里云听悟 - API调用指南

**目的**: 通过API获取音频和转录文字

---

## 🔑 API访问准备

### 1. 获取AccessKey

```bash
# 登录阿里云控制台
# 访问 https://ram.console.aliyun.com/manage/ak
# 创建AccessKey
# 记录 AccessKey ID 和 AccessKey Secret
```

### 2. 安装SDK

```bash
pip install aliyun-python-sdk-core
pip install alibabacloud-tingwu20230930
```

---

## 📡 API调用示例

### 获取文件夹下的任务列表

```python
# scripts/fetch_from_tingwu.py
from alibabacloud_tingwu20230930.client import Client as TingwuClient
from alibabacloud_core.models import Config
import json

def create_tingwu_client(access_key_id: str, access_key_secret: str) -> TingwuClient:
    """创建听悟客户端"""
    config = Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        region_id='cn-hangzhou'
    )

    return TingwuClient(config)

def get_folder_tasks(client: TingwuClient, folder_id: str = '265086'):
    """获取文件夹下的任务列表

    Args:
        client: 听悟客户端
        folder_id: 文件夹ID

    Returns:
        任务列表
    """
    # 调用API
    response = client.list_tasks(
        folder_id=folder_id,
        page_size=100
    )

    return response.body

def get_task_detail(client: TingwuClient, task_id: str):
    """获取任务详情

    Args:
        client: 听悟客户端
        task_id: 任务ID

    Returns:
        任务详情（包含转录结果）
    """
    response = client.get_task_detail(
        task_id=task_id
    )

    return response.body

def download_transcript(client: TingwuClient, task_id: str, output_file: str):
    """下载转录文字

    Args:
        client: 听悟客户端
        task_id: 任务ID
        output_file: 输出文件路径
    """
    # 获取任务详情
    detail = get_task_detail(client, task_id)

    # 提取转录文字
    transcript = detail.result.transcript

    # 保存到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(transcript)

    print(f"转录文字已保存到: {output_file}")

def download_audio(audio_url: str, output_file: str):
    """下载音频文件

    Args:
        audio_url: 音频文件URL
        output_file: 输出文件路径
    """
    import requests

    response = requests.get(audio_url, stream=True)
    response.raise_for_status()

    with open(output_file, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"音频文件已保存到: {output_file}")

# ============================================
# 使用示例
# ============================================

if __name__ == "__main__":
    # 配置
    ACCESS_KEY_ID = "your_access_key_id"
    ACCESS_KEY_SECRET = "your_access_key_secret"
    FOLDER_ID = "265086"
    OUTPUT_DIR = "./data/from_tingwu"

    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 创建客户端
    client = create_tingwu_client(ACCESS_KEY_ID, ACCESS_KEY_SECRET)

    # 获取任务列表
    tasks = get_folder_tasks(client, FOLDER_ID)

    print(f"找到 {len(tasks)} 个任务")

    # 遍历任务
    for task in tasks:
        task_id = task.task_id
        task_name = task.task_name
        status = task.status

        print(f"处理任务: {task_name} ({task_id}) - 状态: {status}")

        # 只下载已完成的任务
        if status != 'COMPLETED':
            print(f"  跳过（未完成）")
            continue

        # 下载转录文字
        transcript_file = f"{OUTPUT_DIR}/{task_name}.txt"
        download_transcript(client, task_id, transcript_file)

        # 下载音频文件（如果有URL）
        if hasattr(task, 'audio_url') and task.audio_url:
            audio_file = f"{OUTPUT_DIR}/{task_name}.mp3"
            download_audio(task.audio_url, audio_file)

        print(f"  ✓ 完成")
```

---

## 🚀 运行脚本

```bash
# 1. 配置AccessKey
export ALIYUN_ACCESS_KEY_ID="your_access_key_id"
export ALIYUN_ACCESS_KEY_SECRET="your_access_key_secret"

# 2. 运行脚本
python scripts/fetch_from_tingwu.py
```

---

## 📋 API限制

| 项目 | 限制 |
|------|------|
| QPS | 10次/秒 |
| 并发数 | 5个 |
| 文件大小 | 单个≤2GB |
| 时长 | 最长12小时 |

---

## ⚠️ 注意事项

1. **安全**: 不要将AccessKey硬编码在代码中
2. **权限**: 确保AccessKey有听悟服务的访问权限
3. **费用**: API调用可能产生费用，请查看阿里云定价
4. **合规**: 遵守阿里云服务条款

---

**文档状态**: ✅ 完成

**下一步**: 配置AccessKey并运行脚本
