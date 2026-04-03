# LingFlow 双团队并行工作流

## 📋 概述

本目录包含3个LingFlow工作流，用于管理灵知系统的技术质量提升工作：

```
.lingflow/workflows/
├── team_a_text_processing.yaml         # 团队A: 文字数据处理
├── team_b_audio_processing.yaml        # 团队B: 音频处理
├── parallel_teams_coordinator.yaml     # 协调器: 管理双团队并行
└── README.md                            # 本文件
```

---

## 🚀 快速启动

### 前置条件

```bash
# 1. 确认LingFlow已安装
which lingflow

# 2. 确认项目环境就绪
cd /home/ai/zhineng-knowledge-system
docker-compose ps
```

### 启动工作流

```bash
# 方式1: 启动协调器（推荐，会自动启动两个团队）
lingflow run .lingflow/workflows/parallel_teams_coordinator.yaml

# 方式2: 分别启动（用于调试）
lingflow run .lingflow/workflows/team_a_text_processing.yaml &
lingflow run .lingflow/workflows/team_b_audio_processing.yaml &
```

---

## 📊 工作流说明

### 1. 团队A - 文字数据处理

**工期**: 14天
**团队**: 3人
**目标**: 提升文字检索和推理质量

**主要任务**:
- ✅ 正则检索器 (RegexRetriever)
- ✅ 书籍电子版字段
- ✅ 意图识别 (IntentAnalyzer)
- ✅ 查询重写 (QueryRewriter)
- ✅ 智能路由 (IntelligentRouter)
- ✅ 性能追踪 (PerformanceTracker)

**启动方式**:
```bash
lingflow run .lingflow/workflows/team_a_text_processing.yaml
```

---

### 2. 团队B - 音频处理

**工期**: 14天
**团队**: 3人
**目标**: 实现音频转写和标注

**主要任务**:
- ✅ ASR引擎集成 (Whisper)
- ✅ 转写标注系统
- ✅ 标注界面开发
- ✅ ASR性能追踪
- ✅ 说话人分离 (可选)

**关键路径**: ASR引擎集成 (Day 3-9) - 必须优先完成

**启动方式**:
```bash
lingflow run .lingflow/workflows/team_b_audio_processing.yaml
```

---

### 3. 协调器 - 并行管理

**工期**: 28天
**角色**: 架构师 + Tech Leads
**目标**: 协调两个团队的工作

**主要阶段**:
- **阶段0** (Day 1-2): 共享基础准备
- **阶段1** (Day 3-14): 独立开发期监控
- **阶段2** (Day 15-21): 联合开发期
- **阶段3** (Day 22-28): 测试与优化

**启动方式**:
```bash
lingflow run .lingflow/workflows/parallel_teams_coordinator.yaml
```

---

## 🔄 工作流程

### 时间线总览

```
Week 1 (Day 1-7)
  Phase 0: 基础准备
  Team A: 正则检索 + 电子版
  Team B: ASR集成启动

Week 2 (Day 8-14)
  Phase 1: 独立开发
  Team A: 意图识别 + 推理路由
  Team B: 标注系统

Week 3 (Day 15-21)
  Phase 2: 联合开发
  Integration: 音频内容进入检索/推理

Week 4 (Day 22-28)
  Phase 3: 测试优化
  Final: 端到端测试 + 文档
```

### 协调机制

**每日同步** (9:30, 15分钟)
```bash
# 自动检查
lingflow check --workflow parallel_teams_coordinator
```

**每周集成** (周五下午)
```bash
# 代码合并
git checkout develop
git merge feature/team-a-text-processing
git merge feature/team-b-audio-processing

# 集成测试
lingflow test --integration
```

---

## 📂 目录结构

```
zhineng-knowledge-system/
├── .lingflow/
│   └── workflows/
│       ├── team_a_text_processing.yaml
│       ├── team_b_audio_processing.yaml
│       ├── parallel_teams_coordinator.yaml
│       └── README.md
├── backend/
│   ├── services/
│   │   ├── retrieval/         # 团队A: 检索系统
│   │   ├── intent/            # 团队A: 意图识别
│   │   ├── reasoning/         # 团队A: 推理系统
│   │   ├── asr/               # 团队B: ASR引擎
│   │   └── annotation/        # 团队B: 标注系统
│   ├── api/v1/
│   │   ├── search.py          # 团队A: 检索API
│   │   ├── reasoning.py       # 团队A: 推理API
│   │   └── annotation.py      # 团队B: 标注API
│   └── migrations/            # 数据库迁移
├── frontend/
│   └── annotation.html        # 团队B: 标注界面
├── docs/
│   ├── API_INTERFACE_CONTRACT.md  # 接口约定
│   ├── DATABASE_SCHEMA_LOCKED.md  # Schema锁定
│   └── PARALLEL_TEAMS_FINAL_REPORT.md
└── tests/
    ├── test_retrieval/        # 团队A测试
    ├── test_intent/           # 团队A测试
    ├── test_asr/              # 团队B测试
    └── integration/           # 集成测试
```

---

## 🎯 成功指标

### 团队A指标
- [ ] 正则检索准确率 > 95%
- [ ] 意图识别准确率 > 85%
- [ ] 推理路由自动化率 > 80%
- [ ] 书籍电子版覆盖率 > 30%

### 团队B指标
- [ ] ASR字错误率 (WER) < 15%
- [ ] 音频处理速度 > 1.0x 实时
- [ ] 标注界面响应时间 < 200ms
- [ ] 支持2种ASR引擎切换

### 集成指标
- [ ] 多模态检索准确率 > 90%
- [ ] 音频内容可检索率 = 100%
- [ ] 端到端测试通过率 > 95%

---

## ⚠️ 常见问题

### Q: 如何查看工作流进度？

```bash
# 查看所有工作流状态
lingflow status

# 查看特定工作流
lingflow status --workflow team_a_text_processing

# 查看实时日志
lingflow logs --workflow team_b_audio_processing --follow
```

### Q: 如何处理工作流失败？

```bash
# 1. 查看失败原因
lingflow logs --workflow <name> --tail 100

# 2. 修复问题后重试
lingflow retry --workflow <name>

# 3. 或回滚到上一个任务
lingflow rollback --workflow <name> --task <task_id>
```

### Q: 如何修改工作流配置？

```bash
# 1. 编辑YAML文件
vim .lingflow/workflows/team_a_text_processing.yaml

# 2. 验证语法
lingflow validate .lingflow/workflows/team_a_text_processing.yaml

# 3. 应用变更
lingflow run .lingflow/workflows/team_a_text_processing.yaml
```

---

## 📞 联系方式

**架构师**: - 负责协调工作流
**团队A Tech Lead**: - 负责文字数据处理
**团队B Tech Lead**: - 负责音频处理
**DevOps**: - 负责环境和部署

---

## 📚 相关文档

- [LingFlow 使用指南](https://github.com/your-org/LingFlow)
- [API接口约定](../docs/API_INTERFACE_CONTRACT.md)
- [数据库Schema](../docs/DATABASE_SCHEMA_LOCKED.md)
- [并行工作分析](../PARALLEL_TEAMS_ANALYSIS.md)

---

**最后更新**: 2026-03-31
**版本**: 1.0.0
