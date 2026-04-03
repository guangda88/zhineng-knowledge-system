# 双团队并行工作分析

**日期**: 2026-03-31
**项目**: 灵知系统技术质量提升

---

## 📊 依赖关系分析

### 团队A: 文字数据处理
- ✅ 检索系统优化（正则检索、意图识别）
- ✅ 推理路由优化
- ✅ 书籍电子版功能

### 团队B: 音频处理
- ✅ ASR引擎集成（Whisper/FasterWhisper）
- ✅ 音频转写标注系统
- ✅ 标注界面开发

---

## 🔗 依赖关系图

```
                    ┌─────────────────────────────────────┐
                    │          共享基础依赖               │
                    │  - 数据库Schema                      │
                    │  - API Gateway                      │
                    │  - 通用工具类(LLM wrapper)          │
                    │  - 部署配置                         │
                    └─────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
        ┌───────────────────────┐       ┌───────────────────────┐
        │    团队A (文字)       │       │    团队B (音频)       │
        ├───────────────────────┤       ├───────────────────────┤
        │ 1. 正则检索           │       │ 1. ASR引擎集成        │
        │ 2. 意图识别           │       │ 2. 转写标注API        │
        │ 3. 推理路由优化       │       │ 3. 标注界面开发       │
        │ 4. 书籍电子版         │       │ 4. 模型微调           │
        └───────────────────────┘       └───────────────────────┘
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      ▼
                    ┌─────────────────────────────────────┐
                    │         后期集成点                   │
                    │  - 多模态融合检索                   │
                    │  - 音频内容进入推理系统             │
                    │  - 统一的标注平台                  │
                    └─────────────────────────────────────┘
```

---

## ✅ 并行可行性评估

| 维度 | 团队A (文字) | 团队B (音频) | 依赖关系 |
|------|-------------|-------------|---------|
| **代码库** | backend/services/retrieval/ | backend/services/annotation/ | 🟢 无冲突 |
| **数据库** | documents表 | annotations表 | 🟢 独立表 |
| **API路由** | /api/v1/search, /reason | /api/v1/annotation | 🟢 不同路径 |
| **依赖包** | sentence-transformers, jieba | whisper, torch | 🟡 CPU资源竞争 |
| **测试** | tests/test_retrieval.py | tests/test_annotation.py | 🟢 独立测试 |

**结论**: ✅ **高度可并行** - 代码、数据库、API均无冲突

---

## 🚨 关键依赖与阻塞点

### 阶段0: 共享基础准备 (必须先完成)
```
时间: Day 1-2
负责人: 架构师 + 2个团队Tech Lead

✅ 任务清单:
1. 数据库Schema锁定
   - documents表 (已有)
   - books表 (已有)
   - annotations表 (需创建)
   - transcription_tasks表 (需创建)

2. 依赖包管理
   - requirements.txt更新
   - 确认whisper安装不冲突

3. 开发环境标准化
   - Docker配置更新
   - 共享开发文档
```

### 阶段1: 独立开发期 (可完全并行)
```
时间: Day 3-14 (2周)
状态: 团队A和团队B完全独立工作

团队A里程碑:
✅ Day 3-5:  正则检索 + 书籍电子版字段
✅ Day 6-10: 意图识别
✅ Day 11-14: 推理路由优化

团队B里程碑:
✅ Day 3-9:  ASR引擎集成 (Whisper)
✅ Day 10-12: 转写标注API完善
✅ Day 13-14: 简单标注界面原型
```

### 阶段2: 联合开发期 (需要协调)
```
时间: Day 15-21 (1周)
状态: 团队间有接口对接

⚠️ 关键集成点:
1. 音频内容进入检索系统 (Day 15-17)
   - 团队B提供: 转写文本数据
   - 团队A提供: 文本向量化接口

2. 音频内容进入推理系统 (Day 18-21)
   - 团队B提供: 音频元数据
   - 团队A提供: 推理路由扩展

3. 统一标注平台 (Day 20-21)
   - 团队A/B共同: 前端界面整合
```

### 阶段3: 测试与优化 (并行 + 联合)
```
时间: Day 22-28 (1周)
状态: 独立测试 + 集成测试

团队A: 文字检索/推理测试
团队B: 音频转写测试
联合: 多模态融合测试
```

---

## 📋 并行工作清单

### 团队A: 文字数据处理 (14天)

#### Sprint 1 (Day 1-5): 基础功能
**Owner**: Senior Dev A
- [ ] Day 1-2: 数据库Migration (书籍电子版字段)
  ```sql
  ALTER TABLE books ADD COLUMN ebook_url VARCHAR(500);
  ALTER TABLE books ADD COLUMN ebook_format VARCHAR(20);
  ALTER TABLE books ADD COLUMN ebook_source VARCHAR(100);
  ```
- [ ] Day 3-4: 正则检索实现
  - 新增 `RegexRetriever` 类
  - 集成到 `HybridRetriever`
  - API: `/api/v1/search/regex`
- [ ] Day 5: 单元测试
  - `tests/test_retrieval/test_regex.py`

#### Sprint 2 (Day 6-10): 意图识别
**Owner**: ML Engineer A
- [ ] Day 6-7: 意图分类器
  - `IntentAnalyzer` 类
  - 支持5种意图类型
  - 训练数据准备
- [ ] Day 8-9: 查询重写
  - `QueryRewriter` 类
  - 同义词扩展
  - 错别字纠正
- [ ] Day 10: 测试与优化
  - 准确率评估

#### Sprint 3 (Day 11-14): 推理路由
**Owner**: Senior Dev B
- [ ] Day 11-12: 智能路由器
  - `IntelligentRouter` 类
  - 性能追踪机制
- [ ] Day 13: 动态权重调整
  - 基于反馈优化
- [ ] Day 14: 集成测试

---

### 团队B: 音频处理 (14天)

#### Sprint 1 (Day 1-2): 基础准备
**Owner**: DevOps + Audio Engineer
- [ ] Day 1: 环境搭建
  ```bash
  # 安装依赖
  pip install faster-whisper
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
  ```
- [ ] Day 2: 数据库表创建
  ```sql
  CREATE TABLE transcription_tasks (
      id SERIAL PRIMARY KEY,
      task_id VARCHAR(100) UNIQUE,
      audio_path TEXT,
      original_transcript TEXT,
      corrected_transcript TEXT,
      status VARCHAR(20),
      engine VARCHAR(50),
      created_at TIMESTAMP DEFAULT NOW()
  );
  ```

#### Sprint 2 (Day 3-9): ASR引擎集成 ⚡ **最关键**
**Owner**: Audio Engineer + ML Engineer B
- [ ] Day 3-5: Whisper集成
  ```python
  class WhisperEngine:
      def __init__(self, model_size="medium"):
          from faster_whisper import WhisperModel
          self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

      async def transcribe(self, audio_path: str, language: str = "zh"):
          segments, info = self.model.transcribe(audio_path, language=language)
          return TranscriptionResult(segments, info)
  ```
- [ ] Day 6-7: 说话人分离 (可选)
  - pyannote.audio集成
  - 或简单的能量阈值法
- [ ] Day 8-9: 时间戳对齐
  - 精确到词级时间戳
  - 便于标注界面定位

#### Sprint 3 (Day 10-14): 标注系统完善
**Owner**: Frontend Dev + Backend Dev B
- [ ] Day 10-11: API完善
  - 移除 `NotImplementedError`
  - 实际转写功能集成
- [ ] Day 12-13: 标注界面
  ```html
  <!-- 简易标注界面 -->
  <div id="annotation-workspace">
      <audio controls></audio>
      <div id="original-text"></div>
      <div id="correction-area"></div>
      <button>提交校正</button>
  </div>
  ```
- [ ] Day 14: 测试
  - 端到端测试

---

## 🤝 协调机制

### 每日同步
```yaml
时间: 每天上午 9:30 (15分钟)
参与: 两个Tech Lead + 架构师
内容:
  - 昨日完成情况
  - 今日计划
  - 阻塞问题
```

### 每周集成
```yaml
时间: 每周五下午
内容:
  - 代码合并到 develop 分支
  - 集成测试
  - 演示Demo
```

### 接口约定文档
```yaml
位置: docs/API_INTERFACE_CONTRACT.md
更新频率: 每次接口变更时立即更新
包含:
  - API端点定义
  - 请求/响应格式
  - 错误码规范
  - 数据格式约定
```

---

## ⚠️ 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **CPU资源竞争** | ASR和Embedding同时运行卡死 | 高 | 🔴 分时段运行，或增加GPU |
| **数据库Schema变更冲突** | 回滚浪费时间 | 中 | 🟡 阶段0锁定Schema，变更走RFC |
| **API接口不一致** | 集成失败 | 中 | 🟡 接口约定文档 + Mock测试 |
| **Whisper模型下载慢** | 阻塞团队B工作 | 低 | 🟢 预先下载，或使用镜像源 |
| **音频数据不足** | 测试覆盖不足 | 中 | 🟡 准备公开数据集 |

---

## 📈 资源需求

### 人力
```
团队A (文字): 3人
  - Senior Dev A (全栈) - Tech Lead
  - ML Engineer A (NLP/检索)
  - Junior Dev A (测试/文档)

团队B (音频): 3人
  - Audio Engineer (ASR专家) - Tech Lead
  - ML Engineer B (语音/深度学习)
  - Frontend Dev (标注界面)

共享:
  - 架构师 (30%时间)
  - DevOps (20%时间)
```

### 硬件
```
开发环境:
  - CPU: 16核+ (Whisper需要)
  - 内存: 32GB+
  - 存储: 500GB SSD

可选（加速）:
  - GPU: NVIDIA RTX 3060+ (12GB VRAM)
    - Whisper推理速度提升10x
    - Embedding生成加速
```

---

## 🎯 成功指标

### 团队A指标
- [ ] 正则检索准确率 > 95%
- [ ] 意图识别准确率 > 85%
- [ ] 推理路由自动化率 > 80%
- [ ] 书籍电子版覆盖率 > 30%

### 团队B指标
- [ ] ASR字错误率 (WER) < 10%
- [ ] 音频处理速度 > 1.0x 实时
- [ ] 标注界面响应时间 < 200ms
- [ ] 支持2种ASR引擎切换

### 集成指标
- [ ] 多模态检索准确率 > 90%
- [ ] 音频内容可检索率 = 100%
- [ ] 端到端测试通过率 > 95%

---

## 📅 时间线总览

```
Week 1 (Day 1-7)
  Team A: ████████░░░░░░░░░░░ 正则检索 + 电子版
  Team B: ████████░░░░░░░░░░░ ASR集成
  Shared: ████░░░░░░░░░░░░░░░ 基础准备

Week 2 (Day 8-14)
  Team A: ████████████████░░░ 意图识别 + 推理路由
  Team B: ████████████████░░░ 标注系统 + 界面
  Shared: ░░░░░░░░░░░░░░░░░░░░ (独立工作)

Week 3 (Day 15-21)
  Team A: ██████░░░░░░░░░░░░░ 集成音频检索
  Team B: ██████░░░░░░░░░░░░░ 集成推理系统
  Shared: ████████████░░░░░░░░ 接口对接

Week 4 (Day 22-28)
  Team A: ████████░░░░░░░░░░░ 测试 + 优化
  Team B: ████████░░░░░░░░░░░ 测试 + 优化
  Shared: ████████████░░░░░░░░ 集成测试

Total: 28天 (4周)
```

---

## ✅ 启动检查清单

在启动双团队并行工作前，确认以下事项：

### 环境准备
- [ ] Docker镜像更新（包含所有依赖）
- [ ] 开发数据库准备（包含新表）
- [ ] 测试音频数据准备（至少10个文件）
- [ ] 测试文本数据准备（至少100条）

### 文档准备
- [ ] API接口约定文档
- [ ] 数据库Schema文档
- [ ] 开发环境搭建指南
- [ ] 测试用例模板

### 流程准备
- [ ] Git分支策略确定
- [ ] Code Review规则确定
- [ ] CI/CD流程配置
- [ ] 每日同步会议链接

### 团队准备
- [ ] 所有开发者环境搭建完成
- [ ] 任务分配明确
- [ ] Tech Lead培训完成
- [ ] 风险预案讨论完成

---

**结论**: ✅ **强烈建议双团队并行**

**理由**:
1. 依赖关系少，可并行度高
2. 总工期从 34天 → 21天 (节省38%)
3. 两个团队可以互相激励
4. 提前暴露集成问题

**条件**: 必须先完成"阶段0: 共享基础准备"(2天)
