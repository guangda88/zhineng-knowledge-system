# 文字+音频双工程流快速开始

**5分钟上手** - 2026-03-31

---

## 🎯 核心概念

```
文字处理工程流（团队A） + 音频处理工程流（团队B）
    ↓                           ↓
文本解析、检索、问答        音频转写、标注、语音
    └───────────┬───────────┘
                ↓
        多模态统一API
                ↓
           用户使用
```

---

## 📋 工程流分工

### 团队A: 文字处理（20天）

| 任务 | 时间 | 交付物 |
|------|------|--------|
| 文本解析和分块 | 3天 | 文本解析器 |
| 向量嵌入生成 | 2天 | 嵌入生成器 |
| 语义检索实现 | 3天 | 检索API |
| RAG问答管道 | 4天 | 问答API |
| 文本标注系统 | 3天 | 标注界面 |
| 测试和文档 | 3天 | 完整文档 |

### 团队B: 音频处理（28天）

| 任务 | 时间 | 交付物 |
|------|------|--------|
| Whisper集成 | 2天 | 转写引擎 |
| 音频转写服务 | 3天 | 转写API |
| 音频数据模型 | 2天 | 数据表 |
| **音频标注系统** | **5天** | **标注API** |
| **波形可视化+编辑器** | **3天** | **标注UI** |
| 导出功能 | 2天 | 多格式导出 |
| 向量化集成 | 2天 | 跨模态检索 |
| 测试和文档 | 3天 | 完整文档 |
| 缓冲 | 2天 | 意外问题 |
| **总计** | **10项任务** | **28天** |

---

## 🚀 立即开始

### Day 1: 环境准备

**团队A（文字）**:
```bash
# 安装依赖
pip install sentence-transformers jieba regex psycopg2-binary

# 验证安装
python -c "import sentence_transformers; print('✅ 文字环境就绪')"
```

**团队B（音频）**:
```bash
# 安装依赖
pip install faster-whisper torch torchaudio av pydub

# 验证安装
python -c "import whisper; print('✅ 音频环境就绪')"
```

**协调器**:
```bash
# 初始化数据库
docker-compose up -d postgres

# 创建数据表
psql -U zhineng -d lingzhi_db <<EOF
-- 文本表
CREATE TABLE textbook_blocks (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(1024)
);

-- 音频表
CREATE TABLE audio_segments (
    id SERIAL PRIMARY KEY,
    audio_file_path VARCHAR(500),
    transcript TEXT
);

-- 跨模态关联表
CREATE TABLE multimodal_annotations (
    id SERIAL PRIMARY KEY,
    text_block_id INTEGER REFERENCES textbook_blocks(id),
    audio_segment_id INTEGER REFERENCES audio_segments(id)
);
EOF
```

### Day 2: 接口规范定义

**统一API规范**（协调器主导）:

```yaml
# api_spec.yaml
openapi: 3.0.0
info:
  title: 灵知系统多模态API
  version: 1.0.0

paths:
  /api/v1/text/search:
    post:
      summary: 文本语义检索
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                query: {type: string}
                top_k: {type: integer, default: 5}
      responses:
        200:
          description: 检索结果

  /api/v1/audio/transcribe:
    post:
      summary: 音频转写
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                audio_file:
                  type: string
                  format: binary
      responses:
        200:
          description: 转写结果

  /api/v1/multimodal/search:
    post:
      summary: 跨模态检索
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                query: {type: string}
                modalities:
                  type: array
                  items:
                    type: string
                    enum: [text, audio]
      responses:
        200:
          description: 跨模态检索结果
```

### Day 3-16: 并行开发

**团队A分支**:
```bash
git checkout develop
git checkout -b team-a-text-processing
```

**团队B分支**:
```bash
git checkout develop
git checkout -b team-b-audio-processing
```

**每日站会**（10:00，10分钟）:
```bash
# 团队A
昨天: 完成文本解析器
今天: 开始向量嵌入生成
阻塞: 无

# 团队B
昨天: Whisper环境配置完成
今天: 实现转写服务
阻塞: GPU资源不足

# 协调器
跟进: GPU资源已申请
通知: 数据库Schema已更新
```

**每周集成**（周五16:00）:
```bash
# 1. 合并到develop
git checkout develop
git merge team-a-text-processing
git merge team-b-audio-processing

# 2. 集成测试
pytest tests/test_integration.py -v

# 3. 问题修复
git commit -m "fix: 集成问题修复"
```

### Day 17-23: 集成优化

**协调器主导**:
```bash
# 1. 统一数据模型
python scripts/unify_data_model.py

# 2. 跨模态检索实现
# backend/api/v1/multimodal.py
@router.post("/search")
async def search_multimodal(query: str, modalities: List[str]):
    # 调用文字检索
    text_results = await text_search(query)

    # 调用音频检索
    audio_results = await audio_search(query)

    # 结果融合
    merged = merge_results(text_results, audio_results)
    return merged
```

### Day 24-28: 部署验证

```bash
# 1. 部署到测试环境
docker-compose -f docker-compose.test.yml up -d

# 2. 端到端测试
pytest tests/test_e2e.py -v

# 3. 生产部署
docker-compose up -d
```

---

## 📊 质量检查

### 团队A检查点

| 检查点 | 标准 | 命令 |
|--------|------|------|
| 文本解析 | >95%准确率 | pytest tests/test_text_parser.py |
| 向量嵌入 | 1024维 | pytest tests/test_embeddings.py |
| 检索准确率 | >75% | pytest tests/test_retrieval.py |
| 问答准确率 | >70% | pytest tests/test_rag.py |
| 测试覆盖 | >70% | pytest --cov --cov-fail-under=70 |

### 团队B检查点

| 检查点 | 标准 | 命令 |
|--------|------|------|
| 转写准确率 | WER<15% | pytest tests/test_asr.py |
| 转写速度 | RTF<1 | pytest tests/test_transcribe_speed.py |
| 音频播放 | <500ms延迟 | pytest tests/test_audio_player.py |
| 测试覆盖 | >70% | pytest --cov --cov-fail-under=70 |

---

## ✅ 检查清单

### Sprint 1 (Day 3-9)
- [ ] 团队A: 文本可检索
- [ ] 团队B: 音频可转写
- [ ] 集成: 数据互通

### Sprint 2 (Day 10-16)
- [ ] 团队A: 问答系统可用
- [ ] 团队B: 音频标注可用
- [ ] 集成: 端到端测试通过

### 集成阶段 (Day 17-23)
- [ ] 跨模态检索可用
- [ ] 测试覆盖率>70%
- [ ] 文档完整

### 部署阶段 (Day 24-28)
- [ ] 部署到生产
- [ ] 监控就绪
- [ ] 用户测试通过

---

## 🔄 协作提示

### DO ✅

- ✅ 每日站会同步进度
- ✅ 接口变更及时通知
- ✅ 定期集成测试
- ✅ 遵循统一数据模型
- ✅ 代码注释清晰

### DON'T ❌

- ❌ 擅自修改公共接口
- ❌ 延迟集成到最后
- ❌ 忽略对方需求
- ❌ 修改数据模型不同步
- ❌ 跳过集成测试

---

## 📞 沟通渠道

- **每日站会**: 10:00，10分钟
- **每周集成**: 周五16:00，1小时
- **即时沟通**: Slack/钉钉群
- **文档共享**: GitHub Wiki
- **问题跟踪**: GitHub Issues

---

**下一步**: 阅读 [DUAL_WORKFLOW_TEXT_AUDIO_PLAN.md](./DUAL_WORKFLOW_TEXT_AUDIO_PLAN.md)
