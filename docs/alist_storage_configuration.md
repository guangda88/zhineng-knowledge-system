# Alist存储配置说明文档

**文档版本**: 1.0
**配置日期**: 2026年3月5日
**Alist版本**: v3.57.0

---

## 📋 存储配置概览

### 配置状态

| 存储源 | 挂载点 | 驱动 | 状态 | rclone访问 | Alist API |
|--------|---------|------|------|-----------|----------|
| **百度云9080** | /百度云9080 | BaiduNetdisk | ✅ work | ❌ 不可访问 | ✅ 可访问 |
| **百度云2362** | /百度云2362 | BaiduNetdisk | ✅ work | ❌ 不可访问 | ✅ 可访问 |
| **阿里云盘** | /阿里云盘 | AliyundriveOpen | ✅ work | ✅ 可访问 | ✅ 可访问 |
| **豆包** | /豆包 | Doubao | ✅ work | ✅ 可访问 | ✅ 可访问 |
| **一刻相册** | /一刻相册 | BaiduPhoto | ✅ work | ❌ 已禁用 | - |
| **夸克** | /夸克 | Quark | ✅ work | ✅ 可访问 | ✅ 可访问 |
| **115** | /115 | 115 Open | ✅ work | ✅ 可访问 | ✅ 可访问 |

**存储总数**: 7个
**可用存储**: 6个（一刻相册已禁用）
**rclone完全可用**: 5个

---

## 🔐 访问凭据

### Alist Web界面

```
URL: http://localhost:5244
用户名: admin
密码: admin123
```

### rclone配置

```ini
[openlist]
type = webdav
url = http://127.0.0.1:2455/dav/
user = adminliuqing
pass = xEH-d2hl9aCoDFLhkjcOQHVsECt7t4LvO_tlCXA
```

---

## 📊 详细配置信息

### 1. 百度云9080

**基本信息**:
- ID: 1
- 挂载点: /百度云9080
- 驱动: BaiduNetdisk
- 状态: work
- 缓存过期: 26小时
- 修改时间: 2026-03-05T16:28:09

**访问方式**:
- rclone: ❌ 失败
- Alist API: ✅ 成功（42个文件/目录）

**主要数据**:
```
/ZNQG - 智能气功资料库
/电子书籍 - 大量电子书
/传统文化学习 - 传统文化资料
/医学电子书 - 医学资料
```

**说明**:
百度云通过rclone的WebDAV协议访问受限，但可以通过Alist API正常访问。

---

### 2. 百度云2362

**基本信息**:
- ID: 2
- 挂载点: /百度云2362
- 驱动: BaiduNetdisk
- 状态: work
- 缓存过期: 30小时
- 修改时间: 2026-03-05T16:28:10

**访问方式**:
- rclone: ❌ 失败
- Alist API: ✅ 成功（10个文件/目录）

**主要数据**:
```
/ZNQG370G - 智能气功资料
/来自：AI笔记 - 气功相关笔记
/家家族谱 - 族谱资料
/三花聚顶小站资源 - 气功资源
```

**说明**:
百度云通过rclone的WebDAV协议访问受限，但可以通过Alist API正常访问。

---

### 3. 阿里云盘

**基本信息**:
- ID: 3
- 挂载点: /阿里云盘
- 驱动: AliyundriveOpen
- 状态: work
- 缓存过期: 30小时
- 修改时间: 2026-03-05T16:28:10

**访问方式**:
- rclone: ✅ 成功
- Alist API: ✅ 成功（4个目录）

**主要数据**:
```
/ZNQG - 智能气功
/lanpoyun - 蓝朋云
/国学大师离线版 - 国学精选
/来自分享 - 共享资源
```

**rclone测试**:
```bash
rclone lsd openlist:阿里云盘
# ✅ 成功显示4个目录
```

---

### 4. 豆包

**基本信息**:
- ID: 4
- 挂载点: /豆包
- 驱动: Doubao
- 状态: work
- 缓存过期: 30小时
- 修改时间: 2026-03-05T16:28:11

**访问方式**:
- rclone: ✅ 成功
- Alist API: ✅ 成功

**主要数据**:
```
/Anytxt - 文本搜索工具
/OpenList - OpenList源码
/对话上传 - 对话记录
/我的会议纪要 - 会议记录
/我的创作 - 创作文件
/我的应用 - 应用文件
/我的文档 - 文档资料
/测试文件 - 测试数据
```

**rclone测试**:
```bash
rclone lsd openlist:豆包
# ✅ 成功显示8个目录
```

---

### 5. 一刻相册

**基本信息**:
- ID: 5
- 挂载点: /一刻相册
- 驱动: BaiduPhoto
- 状态: work
- 禁用: ✅ 是
- 缓存过期: 30小时
- 修改时间: 2026-03-05T16:28:11

**访问方式**:
- rclone: ❌ 已禁用
- Alist API: ❌ 已禁用

**说明**:
一刻相册已被手动禁用，可能用于特殊用途。

---

### 6. 夸克

**基本信息**:
- ID: 6
- 挂载点: /夸克
- 驱动: Quark
- 状态: work
- 缓存过期: 30小时
- 修改时间: 2026-03-05T16:28:12

**访问方式**:
- rclone: ✅ 成功
- Alist API: ✅ 成功

**主要数据**:
```
/夸克精选壁纸 - 壁纸资源
/来自：分享 - 共享资源
```

**rclone测试**:
```bash
rclone lsd openlist:夸克
# ✅ 成功显示2个目录
```

---

### 7. 115网盘

**基本信息**:
- ID: 7
- 挂载点: /115
- 驱动: 115 Open
- 状态: work
- 缓存过期: 30小时
- 修改时间: 2026-03-05T16:28:13

**访问方式**:
- rclone: ✅ 成功
- Alist API: ✅ 成功（16个目录）

**主要数据**:
```
/Zhineng - 智能气功完整资料
/中医资料 - 中医古籍和资料
/国学大师 - 四库全书系列
/More - 其他资源
/Space-per - 空间预留
/ZNQG新整理20251225 - 智能气功新整理
/书画学习 - 书画资料
/云下载 - 云下载文件
/门诊视频 - 门诊视频
```

**rclone测试**:
```bash
rclone lsd openlist:115
# ✅ 成功显示16个目录
```

**数据规模**:
- 智能气功: 约42,192文件
- 中医资料: 14个主要目录
- 国学大师: 四库全书系列
- 视频: 约270GB

---

## 🔑 配置备份

### 备份文件位置

```
/home/ai/zhineng-knowledge-system/docs/alist_storages_backup.json
```

### 备份内容

备份文件包含所有7个存储的完整配置信息，包括：
- 挂载点
- 驱动类型
- 认证信息（Token、Cookie等）
- 缓存配置
- 访问权限

**安全提示**:
- 备份文件包含敏感的认证信息
- 请妥善保管，不要泄露
- 建议加密存储

---

## 📝 访问方式总结

### rclone访问（推荐用于可访问的存储）

#### 可访问的存储

```bash
# 115网盘
rclone copy openlist:115/Zhineng /data/original/zhineng/ --progress
rclone copy openlist:115/中医资料 /data/original/tcm/ --progress
rclone copy openlist:115/国学大师 /data/original/guoxue/ --progress

# 阿里云盘
rclone copy openlist:阿里云盘/国学大师离线版 /data/original/guoxue_offline/ --progress

# 豆包
rclone copy openlist:豆包/我的文档 /data/original/doubao/ --progress

# 夸克
rclone copy openlist:夸克 /data/original/quark/ --progress
```

#### 不可访问的存储（百度云）

百度云盘无法通过rclone的WebDAV协议访问，需要使用以下方式之一：

---

## 🔧 百度云访问方案

### 方案1: 通过Alist API访问（推荐）

#### Python脚本示例

```python
#!/usr/bin/env python3
# alist_downloader.py

import requests
import os
from pathlib import Path
from tqdm import tqdm

# Alist配置
BASE_URL = "http://localhost:5244"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    """登录Alist"""
    login_data = {"username": USERNAME, "password": PASSWORD}
    response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
    return response.json().get('data', {}).get('token')

def list_files(token, path):
    """列出目录文件"""
    headers = {"Authorization": token}

    response = requests.get(
        f"{BASE_URL}/api/fs/list",
        headers=headers,
        params={
            "path": path,
            "password": "",
            "page": 1,
            "per_page": 0,
            "refresh": False
        }
    )

    if response.status_code == 200:
        result = response.json()
        if result.get('code') == 200:
            return result.get('data', {}).get('content', [])

    return []

def download_file(token, file_info, dest_dir):
    """下载文件"""
    headers = {"Authorization": token}

    file_path = file_info['name']
    file_size = file_info['size']

    # 获取下载链接
    response = requests.post(
        f"{BASE_URL}/api/fs/get",
        headers=headers,
        json={
            "path": file_info['path'],
            "password": ""
        }
    )

    if response.status_code != 200:
        return False

    download_url = response.json().get('data', {}).get('raw_url')
    if not download_url:
        return False

    # 下载文件
    dest_file = Path(dest_dir) / file_path
    dest_file.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(download_url, stream=True) as r:
        r.raise_for_status()
        total_size = int(r.headers.get('content-length', 0))

        with open(dest_file, 'wb') as f:
            for chunk in tqdm(
                r.iter_content(chunk_size=8192),
                total=total_size // 8192 + 1,
                desc=file_path
            ):
                f.write(chunk)

    return True

def download_directory(token, source_path, dest_dir):
    """递归下载目录"""
    files = list_files(token, source_path)

    print(f"处理目录: {source_path} ({len(files)} 个文件)")

    for file_info in files:
        if file_info['is_dir']:
            # 递归处理子目录
            sub_dir = file_info['path']
            relative_path = sub_dir.replace(source_path, '').lstrip('/')
            sub_dest = Path(dest_dir) / relative_path
            download_directory(token, sub_dir, str(sub_dest))
        else:
            # 下载文件
            download_file(token, file_info, dest_dir)

def main():
    """主函数"""
    # 登录
    token = login()
    if not token:
        print("登录失败")
        return

    print("登录成功\n")

    # 下载百度云9080的ZNQG
    print("开始下载百度云9080/ZNQG...")
    download_directory(token, "/百度云9080/ZNQG", "/data/original/baidu_9080_znqg")

    # 下载百度云2362的ZNQG370G
    print("\n开始下载百度云2362/ZNQG370G...")
    download_directory(token, "/百度云2362/ZNQG370G", "/data/original/baidu_2362_znqg")

if __name__ == "__main__":
    main()
```

使用方法：
```bash
python3 alist_downloader.py
```

---

### 方案2: 通过Alist Web界面下载

1. 访问 http://localhost:5244
2. 登录（admin / admin123）
3. 浏览到需要的文件
4. 选中文件，点击下载

**适用场景**:
- 少量文件下载
- 手动操作
- 临时需求

---

## 📊 数据访问优先级

### rclone可访问的存储（P0优先级）

| 存储源 | 数据价值 | 优先级 | 数据量 |
|--------|---------|--------|--------|
| **115/Zhineng** | ⭐⭐⭐⭐⭐ | P0 | 42,192文件 |
| **115/中医资料** | ⭐⭐⭐⭐⭐ | P0 | 14目录, 139GB |
| **115/国学大师** | ⭐⭐⭐⭐⭐ | P1 | 四库全书系列 |
| **阿里云盘/国学大师离线版** | ⭐⭐⭐⭐ | P1 | 国学精选 |
| **豆包/我的文档** | ⭐⭐⭐ | P2 | 文档资料 |
| **夸克** | ⭐⭐ | P3 | 壁纸等 |

### 需要通过Alist API访问的存储（特殊处理）

| 存储源 | 数据价值 | 访问方式 | 数据量 |
|--------|---------|---------|--------|
| **百度云9080/ZNQG** | ⭐⭐⭐⭐⭐ | Alist API | 47,413条记录 |
| **百度云2362/ZNQG370G** | ⭐⭐⭐⭐⭐ | Alist API | 36,680条记录 |

---

## 🚀 快速开始指南

### 1. 使用rclone访问可用存储

```bash
# 复制智能气功数据
rclone copy openlist:115/Zhineng /data/original/zhineng/ --progress

# 复制中医资料
rclone copy openlist:115/中医资料 /data/original/tcm/ --progress

# 复制国学大师
rclone copy openlist:115/国学大师 /data/original/guoxue/ --progress
```

### 2. 使用Alist API访问百度云

```bash
# 运行下载脚本
python3 /home/ai/zhineng-knowledge-system/scripts/alist_downloader.py
```

### 3. 查看存储配置

```bash
# 查看备份文件
cat /home/ai/zhineng-knowledge-system/docs/alist_storages_backup.json | jq '.'
```

---

## ⚠️ 注意事项

### 1. 百度云访问限制

**问题**:
- rclone无法通过WebDAV协议访问百度云
- 原因：百度云的WebDAV支持有限

**解决方案**:
- 使用Alist API访问
- 或使用Alist Web界面手动下载

### 2. Token有效期

**说明**:
- 百度云的AccessToken和RefreshToken会过期
- 需要定期更新

**更新方法**:
1. 重新获取Token
2. 通过Alist Web界面更新配置
3. 或通过Alist API更新

### 3. 缓存策略

**配置**:
- 百度云9080: 26小时
- 百度云2362: 30小时
- 其他存储: 30小时

**说明**:
- 缓存可以提高访问速度
- 缓存过期后会重新获取
- 可根据需要调整

---

## 🔄 配置恢复

### 从备份恢复

如果配置丢失，可以从备份恢复：

```python
#!/usr/bin/env python3
# restore_storages.py

import requests
import json

# 读取备份
with open('docs/alist_storages_backup.json', 'r') as f:
    backup_data = json.load(f)

# 登录
base_url = "http://localhost:5244"
login_data = {"username": "admin", "password": "admin123"}
response = requests.post(f"{base_url}/api/auth/login", json=login_data)
token = response.json().get('data', {}).get('token')

headers = {"Authorization": token}

# 恢复存储配置
for storage in backup_data['content']:
    print(f"恢复存储: {storage['mount_path']}")

    response = requests.post(
        f"{base_url}/api/admin/storage/create",
        headers=headers,
        json=storage
    )

    if response.status_code == 200:
        print(f"  ✅ 成功")
    else:
        print(f"  ❌ 失败: {response.text}")

print("\n恢复完成，请重启Alist服务")
```

---

## 📞 技术支持

### 相关文档

- Alist官方文档: https://alist.nn.ci/zh/
- rclone文档: https://rclone.org/
- 项目文档: /home/ai/zhineng-knowledge-system/docs/

### 常见问题

**Q: 如何查看Alist日志？**
```bash
tail -f /home/ai/alist-data/log/log.log
```

**Q: 如何重启Alist服务？**
```bash
pkill -f "alist server"
alist server start
```

**Q: 如何检查存储状态？**
```bash
# 通过Alist Web界面
访问 http://localhost:5244，点击"管理" > "存储"

# 或通过API
python3 << 'EOF'
import requests

base_url = "http://localhost:5244"
login_data = {"username": "admin", "password": "admin123"}
response = requests.post(f"{base_url}/api/auth/login", json=login_data)
token = response.json().get('data', {}).get('token')

headers = {"Authorization": token}
storage_response = requests.get(f"{base_url}/api/admin/storage/list", headers=headers)

for storage in storage_response.json()['data']['content']:
    print(f"{storage['mount_path']}: {storage.get('status')}")
EOF
```

---

## ✅ 配置检查清单

配置完成后，请逐项检查：

- [ ] 所有7个存储配置已保存
- [ ] 配置备份文件已生成
- [ ] 115网盘可以通过rclone访问
- [ ] 阿里云盘可以通过rclone访问
- [ ] 豆包可以通过rclone访问
- [ ] 夸克可以通过rclone访问
- [ ] 百度云9080可以通过Alist API访问
- [ ] 百度云2362可以通过Alist API访问
- [ ] Alist Web界面可以正常登录
- [ ] 所有存储状态显示为"work"

---

**文档版本**: 1.0
**最后更新**: 2026年3月5日
**维护者**: AI Assistant
