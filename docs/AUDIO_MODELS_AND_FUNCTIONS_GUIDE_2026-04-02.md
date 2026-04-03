# 灵知系统 - 语音转写与生成模型完整清单

**更新日期**: 2026-04-02

---

## 🎤 语音转写 (ASR) 模型

### 本地模型 (4个)

#### 1. Whisper (OpenAI)

**文件**: `backend/services/audio/whisper_transcriber.py`

| 模型大小 | 参数量 | VRAM需求 | 特点 |
|----------|--------|----------|------|
| tiny | 39M | ~1GB | 最快速度 |
| base | 74M | ~1GB | 速度/精度平衡 |
| small | 244M | ~2GB | 中等精度 |
| **medium** | 769M | ~5GB | **推荐** (6GB显卡) |
| large-v3 | 1.5G | ~10GB | 最高精度 |

**功能**:
- ✅ 多语言支持 (99种语言)
- ✅ 中文优化
- ✅ 时间戳输出 (词级/段落级)
- ✅ 长音频自动分段
- ✅ CPU fallback

**使用场景**:
```python
from backend.services.audio.asr_router import ASRRouter

router = ASRRouter()
result = router.transcribe(
    audio_path="audio.mp3",
    engine="whisper",
    language="zh"
)
```

---

#### 2. FunASR (Paraformer-zh)

**文件**: `backend/services/audio/funasr_transcriber.py`

| 项目 | 详情 |
|------|------|
| **提供商** | 阿里达摩院 |
| **模型** | Paraformer-zh |
| **参数量** | ~220M |
| **VRAM需求** | ~1GB |
| **标点恢复** | ct-punc (可选) |

**功能**:
- ✅ 中文最优精度
- ✅ 自动标点恢复
- ✅ 极快的推理速度
- ✅ CPU友好

**优势**:
- 中文识别精度业界领先
- 速度比Whisper快2-3倍

**使用场景**:
```python
router = ASRRouter()
result = router.transcribe(
    audio_path="audio.mp3",
    engine="funasr",
    language="zh"
)
```

---

#### 3. SenseVoice Small

**文件**: `backend/services/audio/sensevoice_transcriber.py`

| 项目 | 详情 |
|------|------|
| **提供商** | 阿里达摩院 |
| **模型** | SenseVoiceSmall |
| **参数量** | ~230M |
| **VRAM需求** | ~1GB |

**功能**:
- ✅ **50+语言识别**
- ✅ **情感检测** (HAPPY/SAD/ANGRY/NEUTRAL)
- ✅ **音频事件检测** (LAUGHTER/APPLAUSE/MUSIC等)
- ✅ 说话人识别
- ✅ 语种自动识别

**检测的情感标签**:
```python
<|EMOTION|>: HAPPY, SAD, ANGRY, NEUTRAL
<|EVENT|>: LAUGHTER, APPLAUSE, MUSIC, etc.
<|SPOKEN_LANGUAGE|>: 50+ languages
```

**使用场景**:
```python
router = ASRRouter()
result = router.transcribe(
    audio_path="audio.mp3",
    engine="sensevoice",
    language="auto"  # 自动识别
)
```

---

#### 4. Cohere Transcribe

**文件**: `backend/services/audio/cohere_transcriber.py`

| 项目 | 详情 |
|------|------|
| **提供商** | Cohere (via HuggingFace) |
| **模型** | CohereAsrForConditionalGeneration |
| **参数量** | ~1B |
| **VRAM需求** | ~2GB |

**功能**:
- ✅ 本地部署
- ✅ 高精度识别
- ✅ 多语言支持

**要求**:
- HuggingFace Token
- Gated repo访问权限

---

### 云端API (1个)

#### 通义听悟 (Tingwu)

**文件**: `backend/services/audio/tingwu_client.py`

| 项目 | 详情 |
|------|------|
| **提供商** | 阿里云 |
| **服务** | 离线转写API |
| **SDK** | alibabacloud-tingwu20230930 |

**功能**:
- ✅ 创建转写任务
- ✅ 轮询任务状态
- ✅ 获取转写结果
- ✅ **说话人分离** (Speaker Diarization)
- ✅ 高精度识别

**配置要求**:
```bash
ALIYUN_ACCESS_KEY_ID=your_key_id
ALIYUN_ACCESS_KEY_SECRET=your_key_secret
```

**使用场景**:
```python
from backend.services.audio.tingwu_client import TingwuClient

client = TingwuClient()
result = await client.transcribe_file(
    file_path="audio.mp3",
    callback_url=None  # 可选回调
)
```

---

## 🔊 语音生成 (TTS) 模型

### 本地模型 (1个)

#### Edge-TTS (微软Edge免费)

**文件**: `backend/services/generation/generators.py`

| 项目 | 详情 |
|------|------|
| **提供商** | 微软Edge (免费) |
| **模型** | edge-tts |
| **类型** | 神经网络TTS |

**功能**:
- ✅ **完全免费**
- ✅ 多语言支持
- ✅ 高质量输出
- ✅ 多种声音可选

**声音选项**:
- 默认声音
- 男声/女声
- 不同语言声音

**输出格式**:
- MP3
- WAV
- M4A
- 其他常见格式

**参数控制**:
```python
- voice: 声音选择
- speed: 语速 (0.5-2.0，默认1.0)
- rate: 语率调整
- volume: 音量调整
```

**使用场景**:
```python
from backend.services.generation import AudioGenerator

generator = AudioGenerator()
result = await generator.generate(
    text="这是要转换为语音的文本",
    voice="default",
    speed=1.0,
    output_format="mp3"
)
```

**API端点**:
```python
POST /generation/audio
{
    "text": "要转换的文本",
    "voice": "default",
    "speed": 1.0,
    "output_format": "mp3"
}
```

---

## 🛠️ ASR路由器

**文件**: `backend/services/audio/asr_router.py`

### 功能特性

- ✅ **多引擎统一接口**
- ✅ **懒加载优化** (按需初始化)
- ✅ **自动引擎选择**
- ✅ **批量转写支持**

### 可用引擎

```python
ENGINE_WHISPER = "whisper"
ENGINE_COHERE = "cohere"
ENGINE_FUNASR = "funasr"
ENGINE_SENSEVOICE = "sensevoice"
ENGINE_TINGWU = "tingwu"

DEFAULT_ENGINE = ENGINE_WHISPER
```

### 使用示例

```python
from backend.services.audio.asr_router import ASRRouter

router = ASRRouter()

# 单个文件转写
result = router.transcribe(
    audio_path="audio.mp3",
    engine="funasr",  # 自动选择最优引擎
    language="zh"
)

# 批量转写目录
results = router.transcribe_directory(
    audio_dir="/path/to/audios",
    engine="whisper",
    language="zh",
    max_files=10
)

# 列出可用引擎状态
engines = router.list_engines()
```

---

## 📊 模型对比

### ASR模型对比

| 模型 | 精度 | 速度 | 语言支持 | 特殊功能 | 推荐场景 |
|------|------|------|----------|----------|----------|
| **Whisper** | ★★★★☆ | ★★★☆☆ | 99种 | 时间戳 | 通用/多语言 |
| **FunASR** | ★★★★★ | ★★★★★ | 中文 | 标点恢复 | 中文专用 |
| **SenseVoice** | ★★★★☆ | ★★★★☆ | 50+ | 情感/事件 | 多语言分析 |
| **Cohere** | ★★★★☆ | ★★★☆☆ | 多 | 高精度 | 高需求场景 |
| **Tingwu** | ★★★★★ | N/A | 中文 | 说话人分离 | 云端处理 |

### TTS模型对比

| 模型 | 成本 | 质量 | 语言 | 离线 | 推荐场景 |
|------|------|------|------|------|----------|
| **Edge-TTS** | 免费 | 高 | 多 | ✅ | 日常使用 |

---

## 🎯 使用指南

### 选择合适的ASR引擎

#### 中文场景

**最高精度**: FunASR
```python
result = router.transcribe(audio_path, engine="funasr")
```

**多语言分析**: SenseVoice
```python
result = router.transcribe(audio_path, engine="sensevoice")
# 包含情感和事件检测结果
```

**通用场景**: Whisper
```python
result = router.transcribe(audio_path, engine="whisper")
```

#### 云端高精度

**带说话人分离**: Tingwu
```python
client = TingwuClient()
result = await client.transcribe_file(audio_path)
# 自动识别不同说话人
```

---

### API接口

#### 音频上传

```bash
POST /audio/upload
```

**参数**:
- `file`: 音频文件
- `category`: 分类
- `tags`: 标签

#### 转写任务

```bash
POST /audio/{file_id}/transcribe
```

**参数**:
- `engine`: 转写引擎
- `language`: 语言代码

#### 音频生成

```bash
POST /generation/audio
```

**参数**:
- `text`: 待转换文本
- `voice`: 声音选择
- `speed`: 语速
- `output_format`: 输出格式

---

## 💡 最佳实践

### ASR转写优化

1. **选择合适的引擎**
   - 中文专用 → FunASR
   - 多语言 → Whisper
   - 情感分析 → SenseVoice

2. **音频预处理**
   - 使用高质量音频 (16kHz+)
   - 减少背景噪音
   - 单声道效果更好

3. **批量处理**
   - 使用 `transcribe_directory()` 批量处理
   - 选择合适的 `max_files` 避免过载

### TTS生成优化

1. **文本预处理**
   - 添加标点符号
   - 合理分段
   - 避免过长文本

2. **参数调优**
   - `speed`: 1.0 (正常), 0.8 (慢速), 1.2 (快速)
   - `voice`: 选择适合场景的声音

---

## 📋 配置检查

### 检查本地模型

```python
from backend.services.audio.asr_router import ASRRouter

router = ASRRouter()
engines = router.list_engines()

for engine in engines:
    status = "✅ 可用" if engine["available"] else "❌ 不可用"
    error = engine.get("error", "")
    print(f"{engine['name']}: {status}")
    if error:
        print(f"  错误: {error}")
```

### 检查云端API

```bash
# 检查听悟配置
echo $ALIYUN_ACCESS_KEY_ID
echo $ALIYUN_ACCESS_KEY_SECRET

# 检查TTS可用性
python -c "import edge_tts; print('Edge-TTS可用')"
```

---

## 🎉 总结

### 语音转写 (ASR)

**本地模型** (4个):
- Whisper (OpenAI) - 通用多语言
- FunASR (达摩院) - 中文最优
- SenseVoice (达摩院) - 多语言+情感
- Cohere - 高精度

**云端API** (1个):
- 通义听悟 - 说话人分离

### 语音生成 (TTS)

**本地模型** (1个):
- Edge-TTS (微软) - 免费高质量

### 技术架构

```
ASR路由器
├── Whisper (OpenAI)
├── FunASR (达摩院)
├── SenseVoice (达摩院)
├── Cohere (HuggingFace)
└── Tingwu (阿里云API)

TTS生成
└── Edge-TTS (微软Edge免费)
```

---

**众智混元，万法灵通** ⚡🚀
