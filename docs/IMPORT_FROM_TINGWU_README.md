# 从阿里云听悟导入数据 - 完整指南

**目标**: 将阿里云听悟中的音频和转录文字导入到灵知系统

---

## 📋 整体流程

```
┌─────────────────┐
│ 1. 创建AccessKey │ → RAM用户（推荐）或主账号
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. 验证AccessKey │ → 运行测试脚本
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. 获取数据      │ → 方式A: 手动下载（推荐）
│                 │ → 方式B: API调用
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. 导入灵知系统  │ → 运行导入脚本
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. 验证导入结果  │ → 查看/搜索/标注
└─────────────────┘
```

---

## 📚 文档导航

### 第1步: 创建AccessKey

**文档**: [docs/AliYun_AccessKey_Creation_Guide.md](docs/AliYun_AccessKey_Creation_Guide.md)

**内容**:
- ✅ 为什么使用RAM用户（安全最佳实践）
- ✅ 详细创建步骤（图文说明）
- ✅ 安全最佳实践
- ✅ 常见问题解答

**关键步骤**:
```
1. 登录RAM控制台: https://ram.console.aliyun.com/
2. 创建RAM用户: lingzhi-tingwu
3. 添加权限: AliyunTingwuFullAccess
4. 创建AccessKey: 保存Secret（仅一次显示！）
5. 配置环境变量
```

---

### 第2步: 验证AccessKey

**脚本**: [scripts/test_tingwu_access_key.py](scripts/test_tingwu_access_key.py)

**运行方式**:
```bash
# 配置环境变量
export ALIYUN_ACCESS_KEY_ID="your_access_key_id"
export ALIYUN_ACCESS_KEY_SECRET="your_access_key_secret"

# 运行测试
python scripts/test_tingwu_access_key.py
```

**预期输出**:
```
============================================================
阿里云听悟 AccessKey 测试
============================================================

[1/4] 检查环境变量...
✅ AccessKey ID: LTAI5tXXX...XXXX
✅ AccessKey Secret: ********

[2/4] 检查SDK...
✅ SDK已安装

[3/4] 创建听悟客户端...
✅ 客户端创建成功

[4/4] 测试API调用...
✅ API调用成功！
✅ 状态码: 200
✅ 账号ID: 1936339930532323

============================================================
🎉 AccessKey验证成功！可以开始使用听悟API了
============================================================
```

---

### 第3步: 获取数据

#### 方式A: 手动下载（推荐）

**步骤**:
1. 访问 https://tingwu.aliyun.com/folders/265086
2. 下载音频文件（MP3格式）
3. 导出转录文字（TXT或SRT格式）
4. 保存到本地目录：
   ```
   data/from_tingwu/
   ├── audio/
   │   ├── recording1.mp3
   │   └── recording2.mp3
   └── transcripts/
       ├── recording1.txt
       └── recording2.txt
   ```

**优点**:
- ✅ 最简单
- ✅ 最安全
- ✅ 不需要编程

#### 方式B: API调用

**文档**: [docs/AliYun_TingWu_API_Guide.md](docs/AliYun_TingWu_API_Guide.md)

**脚本**: [scripts/fetch_from_tingwu.py](scripts/fetch_from_tingwu.py)

**运行方式**:
```bash
python scripts/fetch_from_tingwu.py
```

**优点**:
- ✅ 自动化
- ✅ 可批量获取
- ✅ 支持定期同步

**要求**:
- ⚠️ 需要配置AccessKey
- ⚠️ 需要安装SDK

---

### 第4步: 导入灵知系统

**文档**: [docs/IMPORT_FROM_TINGWU_GUIDE.md](docs/IMPORT_FROM_TINGWU_GUIDE.md)

**脚本**: [scripts/import_from_tingwu.py](scripts/import_from_tingwu.py)

**运行方式**:
```bash
# 方式1: 命令行导入
python scripts/import_from_tingwu.py \
  --audio-dir data/from_tingwu/audio \
  --transcript-dir data/from_tingwu/transcripts \
  --category teaching

# 方式2: Web界面导入
# 访问 http://localhost:8001/import
# 上传音频和转录文件
```

**功能**:
- ✅ 自动导入音频和转录文字
- ✅ 自动创建分段和时间戳
- ✅ 自动向量化（支持语义搜索）
- ✅ 支持批量导入

---

### 第5步: 验证导入结果

**查看导入的音频**:
```bash
curl http://localhost:8001/api/v1/audio/list
```

**查看转录结果**:
```bash
curl http://localhost:8001/api/v1/audio/1
```

**搜索音频内容**:
```bash
curl -X POST http://localhost:8001/api/v1/search/multimodal \
  -H "Content-Type: application/json" \
  -d '{"query": "智能气功", "modalities": ["audio"]}'
```

**添加标注**:
```bash
curl -X POST http://localhost:8001/api/v1/annotations/ \
  -H "Content-Type: application/json" \
  -d '{
    "audio_file_id": 1,
    "annotation_type": "highlight",
    "start_time": 10.5,
    "end_time": 15.0,
    "content": "这是重点内容"
  }'
```

---

## 🎯 快速开始（完整示例）

假设您已经手动下载了数据到 `data/from_tingwu/` 目录：

```bash
# 1. 启动灵知系统
docker-compose up -d

# 2. 等待服务启动
sleep 10

# 3. 运行导入脚本
python scripts/import_from_tingwu.py \
  --audio-dir data/from_tingwu/audio \
  --transcript-dir data/from_tingwu/transcripts \
  --category teaching

# 4. 验证导入
curl http://localhost:8001/api/v1/audio/list | jq

# 5. 查看转录结果
curl http://localhost:8001/api/v1/audio/1 | jq

# 6. 测试搜索
curl -X POST http://localhost:8001/api/v1/search/multimodal \
  -H "Content-Type: application/json" \
  -d '{"query": "混元灵通"}'
```

---

## 📦 安装依赖

### 方式A: API调用（如果使用方式B）

```bash
# 安装阿里云SDK
pip install alibabacloud-tingwu20230930
pip install alibabacloud-core

# 验证安装
python -c "from alibabacloud_tingwu20230930.client import Client; print('✅ SDK安装成功')"
```

### 方式B: 导入脚本

```bash
# 安装依赖
pip install fastapi[all] sqlalchemy psycopg2-binary

# 安装音频处理库
pip install faster-whisper pydub

# 验证安装
python -c "import faster_whisper; print('✅ 依赖安装成功')"
```

---

## 🔧 环境变量配置

创建 `.env` 文件：

```bash
# 阿里云AccessKey（如果使用API方式）
ALIYUN_ACCESS_KEY_ID=your_access_key_id
ALIYUN_ACCESS_KEY_SECRET=your_access_key_secret

# 数据库配置
DATABASE_URL=postgresql://zhineng:zhineng123@localhost:5436/zhineng_kb

# Redis配置
REDIS_URL=redis://localhost:6379/0
```

加载环境变量：

```bash
# 方式1: 手动导出
export $(cat .env | xargs)

# 方式2: 使用python-dotenv
pip install python-dotenv
python -c "from dotenv import load_dotenv; load_dotenv(); print('✅ 环境变量已加载')"
```

---

## ⚠️ 常见问题

### Q1: AccessKey测试失败

**错误**: `AccessKey验证失败`

**解决方案**:
1. 检查环境变量是否正确设置
   ```bash
   echo $ALIYUN_ACCESS_KEY_ID
   echo $ALIYUN_ACCESS_KEY_SECRET
   ```
2. 检查AccessKey是否已禁用或过期
3. 检查RAM用户是否有听悟权限

### Q2: 导入失败

**错误**: `找不到音频文件` 或 `找不到转录文件`

**解决方案**:
1. 确认文件路径正确
2. 确认音频和转录文件的文件名一致（不含扩展名）
   ```bash
   # 正确:
   audio/recording1.mp3
   transcripts/recording1.txt

   # 错误:
   audio/recording1.mp3
   transcripts/recording1_transcript.txt  # 文件名不一致
   ```
3. 检查文件权限

### Q3: 转录文字格式错误

**错误**: `无法解析转录文字`

**解决方案**:
1. 确认文件编码是UTF-8
   ```bash
   file -I transcripts/recording1.txt
   ```
2. 如果不是UTF-8，转换编码：
   ```bash
   iconv -f GBK -t UTF-8 input.txt > output.txt
   ```
3. 确认格式是纯文本或SRT格式

### Q4: 向量化失败

**错误**: `向量化失败` 或 `embedding生成失败`

**解决方案**:
1. 检查text_processor服务是否运行
2. 检查向量数据库是否正常
3. 查看日志了解详细错误

---

## 📊 支持的数据格式

### 音频格式

| 格式 | 扩展名 | 优先级 |
|------|--------|--------|
| MP3 | .mp3 | P0 |
| WAV | .wav | P0 |
| M4A | .m4a | P1 |
| AAC | .aac | P2 |

### 转录文字格式

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| 纯文本 | .txt | 普通文本 |
| SRT字幕 | .srt | 带时间戳 |
| JSON | .json | 结构化数据 |

---

## 🎉 完成后您将获得

1. **音频管理**
   - ✅ 播放音频
   - ✅ 查看转录文字
   - ✅ 编辑和校正

2. **音频标注**
   - ✅ 重点标注
   - ✅ 知识关联
   - ✅ 教学要点

3. **语义搜索**
   - ✅ 全文搜索
   - ✅ 跨模态检索
   - ✅ 相似内容推荐

4. **导出分享**
   - ✅ 导出TXT
   - ✅ 导出SRT字幕
   - ✅ 导出标注

---

## 📞 需要帮助？

如果遇到问题：

1. 查看对应文档的"常见问题"部分
2. 检查日志文件
3. 运行测试脚本诊断
4. 联系技术支持

---

**文档状态**: ✅ 完整指南

**最后更新**: 2026-03-31

**下一步**: 选择方案（手动下载或API调用），开始导入数据！

**众智混元，万法灵通** ⚡🚀
