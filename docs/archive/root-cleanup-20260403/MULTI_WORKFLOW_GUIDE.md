# 灵知系统 - 多工作流并行执行指南

**版本**: 1.0.0
**日期**: 2026-03-31
**状态**: ✅ 已完成创建，待审核

---

## 📋 文档概述

本指南是灵知系统技术质量提升项目的**多工作流并行执行**的权威文档。

**适用场景**:
- 需要多个团队并行工作
- 有明确的依赖关系和集成点
- 需要协调和监控机制

**相关文档**:
- [详细分析](PARALLEL_TEAMS_ANALYSIS.md) - 依赖关系和技术方案
- [启动指南](LINGFLOW_PARALLEL_TEAMS_SUMMARY.md) - 快速启动指南
- [工作流目录](.lingflow/workflows/README.md) - 工作流配置说明

---

## 🎯 项目目标

### 核心目标
在**28天内**完成两大技术领域的质量提升：
1. **文字数据处理** (团队A) - 检索、推理优化
2. **音频处理** (团队B) - ASR、标注系统

### 成功指标
```
技术指标:
  - 检索准确率: 85% → >90%
  - ASR字错误率: <15%
  - 推理响应时间: <150ms
  - 测试覆盖率: >75%

功能指标:
  - 团队A交付: 5个核心功能
  - 团队B交付: 4个核心功能
  - 集成交付: 2个多模态功能

效率指标:
  - 工期: 28天 (单团队需23-34天)
  - 节省: 0-6天 (0-18%)
  - 说明: 节省时间取决于实际进度和任务优先级
```

---

## 🏗️ 架构设计

### 三层工作流架构

```
┌─────────────────────────────────────────────────────────┐
│           协调器工作流 (Coordinator)                     │
│  - 管理共享依赖                                          │
│  - 监控进度和风险                                        │
│  - 协调集成测试                                          │
│  - 工期: 28天                                           │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌──────────────────────┐      ┌──────────────────────┐
│   团队A工作流         │      │   团队B工作流         │
│   (Text Processing)  │      │   (Audio Processing)  │
│                      │      │                      │
│  - 正则检索          │      │  - ASR引擎集成        │
│  - 意图识别          │      │  - 转写标注系统       │
│  - 推理路由优化      │      │  - 标注界面           │
│                      │      │                      │
│  工期: 14天          │      │  工期: 14天           │
│  团队: 3人           │      │  团队: 3人            │
└──────────────────────┘      └──────────────────────┘
```

### 依赖关系矩阵

| 维度 | 团队A | 团队B | 协调器 |
|------|-------|-------|--------|
| **代码库** | backend/services/retrieval/ | backend/services/asr/ | docs/, migrations/ |
| **数据库表** | reasoning_performance | transcription_tasks | 共享Schema |
| **API路由** | /api/v1/search, /reason | /api/v1/annotation | 集成API |
| **依赖包** | sentence-transformers, jieba | faster-whisper, torch | 无冲突 |
| **测试** | tests/test_retrieval/ | tests/test_asr/ | tests/integration/ |

**并行度评分**: ⭐⭐⭐⭐⭐ (5/5) - 高度可并行

---

## 📅 工作流详细说明

### 1. 协调器工作流

**文件**: `.lingflow/workflows/parallel_teams_coordinator.yaml`
**工期**: 28天
**角色**: 架构师 + Tech Leads

#### 阶段划分

```yaml
阶段0: 共享基础准备 (Day 1-2)
  任务:
    - 锁定数据库Schema
    - 验证依赖包兼容性
    - 创建API接口约定文档
    - 设置Git分支策略

  产出:
    ✅ DATABASE_SCHEMA_LOCKED.md
    ✅ API_INTERFACE_CONTRACT.md
    ✅ 依赖检查报告

阶段1: 独立开发期监控 (Day 3-14)
  任务:
    - 每日同步检查 (自动化)
    - 每周集成测试
    - 资源使用监控

  产出:
    ✅ 每日状态报告
    ✅ 每周集成报告

阶段2: 联合开发期 (Day 15-21)
  任务:
    - 音频内容进入检索系统
    - 音频内容进入推理系统
    - 集成API开发

  产出:
    ✅ 多模态检索API
    ✅ 音频推理API

阶段3: 测试与优化 (Day 22-28)
  任务:
    - 端到端测试
    - 性能优化
    - 文档完善

  产出:
    ✅ 测试报告
    ✅ 性能报告
    ✅ 最终文档
```

#### 关键功能

**自动化监控**:
```yaml
daily_sync_check:
  interval: 86400  # 每24小时
  tasks:
    - 检查Git状态
    - 检查Docker资源
    - 生成状态报告
```

**风险告警**:
```yaml
risk_monitoring:
  - risk: "CPU资源竞争"
    indicator: "docker_cpu_usage > 90%"
    alert_to: ["#devops", "#team-a", "#team-b"]

  - risk: "API接口不一致"
    indicator: "api_integration_tests_fails > 3"
    alert_to: ["#team-a", "#team-b"]
```

---

### 2. 团队A工作流 (文字数据处理)

**文件**: `.lingflow/workflows/team_a_text_processing.yaml`
**工期**: 14天
**团队**: 3人 (Senior Dev + ML Engineer + Junior Dev)

#### Sprint划分

**Sprint 1 (Day 1-5): 基础功能**
```
任务:
  1. 数据库迁移 - 添加书籍电子版字段
  2. 实现正则检索器 (RegexRetriever)
  3. 集成到混合检索系统
  4. 创建正则检索API
  5. 单元测试

产出:
  ✅ RegexRetriever类
  ✅ books表新增3个字段
  ✅ POST /api/v1/search/regex

验收标准:
  - 正则检索准确率 > 95%
  - 测试覆盖率 > 80%
```

**Sprint 2 (Day 6-10): 意图识别**
```
任务:
  1. 准备意图识别训练数据
  2. 实现意图分析器 (IntentAnalyzer)
  3. 实现查询重写器 (QueryRewriter)
  4. 集成到检索系统
  5. 单元测试

产出:
  ✅ IntentAnalyzer类
  ✅ QueryRewriter类
  ✅ 5种意图类型支持

验收标准:
  - 意图识别准确率 > 85%
  - 测试覆盖率 > 75%
```

**Sprint 3 (Day 11-14): 推理路由**
```
任务:
  1. 实现智能路由器 (IntelligentRouter)
  2. 实现性能追踪器 (PerformanceTracker)
  3. 集成到推理API
  4. 集成测试

产出:
  ✅ IntelligentRouter类
  ✅ PerformanceTracker类
  ✅ 推理性能数据表

验收标准:
  - 路由自动化率 > 80%
  - 测试覆盖率 > 70%
```

#### 交付清单

```
✅ backend/services/retrieval/regex.py
✅ backend/services/intent/intent_analyzer.py
✅ backend/services/intent/query_rewriter.py
✅ backend/services/reasoning/router.py
✅ backend/services/reasoning/performance_tracker.py
✅ backend/api/v1/search.py (新增正则检索端点)
✅ backend/api/v1/reasoning.py (新增智能路由)
✅ backend/migrations/add_ebook_fields.sql
✅ tests/test_retrieval/test_regex.py
✅ tests/test_intent/test_analyzer.py
✅ tests/test_reasoning/test_router.py
```

---

### 3. 团队B工作流 (音频处理)

**文件**: `.lingflow/workflows/team_b_audio_processing.yaml`
**工期**: 14天
**团队**: 3人 (Audio Engineer + ML Engineer + Frontend Dev)

#### Sprint划分

**Sprint 0 (Day 1-2): 环境搭建**
```
任务:
  1. 安装音频处理依赖 (faster-whisper, torch)
  2. 创建转写标注相关数据表
  3. 预下载Whisper模型
  4. 准备测试音频数据

产出:
  ✅ Python依赖安装完成
  ✅ 3张数据表创建
  ✅ Whisper medium模型下载
  ✅ 测试音频就位

关键路径:
  ⚡ 模型下载可能耗时较长 (15分钟)
```

**Sprint 1 (Day 3-9): ASR引擎集成** ⚡ **关键路径**
```
任务:
  1. 实现WhisperEngine类
  2. 实现说话人分离 (可选)
  3. 集成到TranscriptionAnnotator
  4. 创建ASR性能追踪
  5. 集成测试

产出:
  ✅ WhisperEngine类
  ✅ TranscriptionAnnotator完善
  ✅ ASRPerformanceTracker类

验收标准:
  - WER < 15%
  - 实时率 < 2.0x

关键路径:
  ⚡⚡⚡ 必须优先完成，阻塞所有后续工作
```

**Sprint 2 (Day 10-14): 标注系统**
```
任务:
  1. 增强转写标注API
  2. 创建音频标注前端界面
  3. 前后端集成
  4. E2E测试

产出:
  ✅ 标注API端点
  ✅ annotation.html
  ✅ annotation.js

验收标准:
  - 标注界面响应时间 < 200ms
  - E2E测试通过率 > 90%
```

#### 交付清单

```
✅ backend/services/asr/whisper_engine.py
✅ backend/services/asr/speaker_diarization.py (可选)
✅ backend/services/asr/performance_tracker.py
✅ backend/services/annotation/transcription_annotator.py (完善)
✅ backend/api/v1/annotation.py (增强)
✅ frontend/annotation.html
✅ frontend/js/annotation.js
✅ backend/migrations/create_transcription_tables.sql
✅ tests/test_asr/test_whisper_engine.py
✅ tests/test_annotation/test_e2e_workflow.py
```

---

## 🔄 协调机制

### 每日同步 (Daily Sync)

```yaml
时间: 每天 9:30 AM
时长: 15分钟
参与者:
  - Team A Tech Lead
  - Team B Tech Lead
  - 架构师

议程:
  1. 昨日完成情况 (3分钟)
  2. 今日计划 (5分钟)
  3. 阻塞问题 (7分钟)

产出:
  - 每日状态报告
  - 阻塞问题清单
  - 需要协调的事项
```

### 每周集成 (Weekly Integration)

```yaml
时间: 每周五下午 3:00 PM
时长: 60分钟
参与者: 全员

议程:
  1. 代码合并到develop分支 (15分钟)
  2. 集成测试执行 (20分钟)
  3. Demo演示 (15分钟)
  4. 下周计划 (10分钟)

产出:
  - 集成测试报告
  - Demo录像
  - 下周任务清单
```

### 接口变更流程

```yaml
触发条件:
  - 需要修改API接口
  - 需要修改数据表结构
  - 需要更改共享依赖

流程:
  1. 更新 docs/API_INTERFACE_CONTRACT.md
  2. 提交PR到工作流仓库
  3. 通知对方团队
  4. 在每日同步会议确认
  5. 双方Tech Lead批准
  6. 合并变更

时间要求:
  - 至少提前1天通知
  - 重大变更提前1周
```

---

## ⚠️ 风险管理

### 关键风险识别

#### 风险1: CPU资源竞争 (高)

**描述**: Whisper和Embedding同时运行会竞争CPU资源

**影响**:
- 系统响应变慢
- 超时错误增加
- 开发效率下降

**概率**: 高

**缓解措施**:
```
方案1: 分时段运行 (推荐)
  - 团队A: 9:00-12:00 (Embedding密集)
  - 团队B: 13:00-18:00 (ASR密集)

方案2: 增加GPU加速
  - 成本: ~$500/月 (云GPU)
  - 加速: Whisper 10x, Embedding 5x

方案3: 使用独立服务器
  - 将ASR服务部署到独立机器
  - 成本: ~$200/月
```

**监控指标**:
```bash
# 检查CPU使用率
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}"

# 告警阈值
if cpu_usage > 90%:
    alert("#devops", "#team-a", "#team-b")
```

---

#### 风险2: ASR引擎集成失败 (高)

**描述**: Whisper模型下载失败或集成不顺利

**影响**:
- 阻塞团队B所有后续工作
- 延误整个项目进度

**概率**: 中

**缓解措施**:
```
方案1: 预先下载模型
  - 在阶段0完成下载
  - 验证模型可用性
  - 准备备用源

方案2: 使用备用ASR引擎
  - PaddleSpeech (国产化)
  - Whisper tiny模型 (更快但准确率低)

方案3: 云服务API
  - OpenAI Whisper API
  - Google Cloud Speech-to-Text
  - Azure Speech Services
```

**监控指标**:
```bash
# 检查模型文件
ls -lh ~/.cache/huggingface/hub/

# 测试模型可用性
python3 -c "from faster_whisper import WhisperModel; print('OK')"
```

---

#### 风险3: 数据库Schema冲突 (中)

**描述**: 两个团队同时修改数据库结构导致冲突

**影响**:
- 数据迁移失败
- 数据不一致
- 回滚浪费时间

**概率**: 中

**缓解措施**:
```
方案1: 阶段0锁定Schema
  - 明确所有表结构
  - 任何变更需RFC流程
  - 需要架构师+2个Tech Lead批准

方案2: 使用Migration脚本
  - 所有变更通过SQL脚本
  - 脚本经过测试环境验证
  - 保留回滚脚本

方案3: 独立开发数据库
  - 每个团队使用独立数据库
  - 集成时再合并
```

**监控指标**:
```sql
-- 检查表结构变化
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
```

---

## 📊 监控和报告

### 实时监控

```bash
# 查看所有工作流状态
lingflow status

# 查看特定工作流
lingflow status --workflow team_a_text_processing

# 查看实时日志
lingflow logs --workflow team_b_audio_processing --follow

# 查看Docker资源使用
docker stats --no-stream
```

### 每周报告模板

```markdown
# 第N周工作进度报告

## 团队A进度
- 完成任务: X/Y
- 测试通过率: XX%
- 阻塞问题: [...]

## 团队B进度
- 完成任务: X/Y
- ASR性能: WER=XX%, 实时率=X.Xx
- 阻塞问题: [...]

## 集成状态
- 接口对接: XX%
- 集成测试: 通过XX/XX

## 风险和问题
- 当前风险: [...]
- 需要协调: [...]

## 下周计划
- 团队A: [...]
- 团队B: [...]
- 集成: [...]
```

---

## 🚀 启动检查清单

### 环境准备

- [ ] Docker Compose运行中
  ```bash
  docker-compose ps
  ```

- [ ] PostgreSQL数据库就绪
  ```bash
  docker-compose exec postgres pg_isready -U lingzhi
  ```

- [ ] LingFlow已安装
  ```bash
  which lingflow
  lingflow --version
  ```

- [ ] 工作流文件已创建
  ```bash
  ls -lh .lingflow/workflows/*.yaml
  ```

### 文件准备

- [ ] 测试音频数据已准备
  ```bash
  ls -lh data/audio/test/
  # 需要至少4个测试文件
  ```

- [ ] 启动脚本有执行权限
  ```bash
  ls -l start_parallel_workflows.sh
  ```

- [ ] API接口约定文档已创建
  ```bash
  ls -l docs/API_INTERFACE_CONTRACT.md
  ```

### 团队准备

- [ ] 所有开发者环境搭建完成
- [ ] Tech Lead培训完成
- [ ] 风险预案讨论完成
- [ ] 沟通渠道建立 (Slack/钉钉)

---

## 📞 联系方式和职责

### 核心团队

```
架构师:
  职责: 总协调、技术决策、风险把控
  参与: 所有阶段
  时间: 50%

团队A Tech Lead:
  职责: 文字数据处理技术方向
  参与: 团队A所有Sprint
  时间: 100%

团队B Tech Lead:
  职责: 音频处理技术方向
  参与: 团队B所有Sprint
  时间: 100%

DevOps:
  职责: 环境搭建、资源管理、监控告警
  参与: 阶段0 + 持续运维
  时间: 30%
```

### 沟通渠道

```
每日同步: Slack #daily-sync
每周集成: Slack #weekly-integration
风险告警: Slack #alerts
技术讨论: Slack #tech-discussion
文档协作: Google Docs / Notion
```

---

## 📈 成功标准

### 必须达成 (P0)

- [ ] 团队A: 所有Sprint测试通过率 > 90%
- [ ] 团队B: ASR WER < 15%
- [ ] 集成: 端到端测试100%通过
- [ ] 性能: 所有响应时间达标
- [ ] 工期: 28天内完成

### 期望达成 (P1)

- [ ] 团队A: 意图识别准确率 > 85%
- [ ] 团队B: 实时率 < 2.0x
- [ ] 集成: 多模态检索准确率 > 90%
- [ ] 测试: 覆盖率 > 75%

### 加分项 (P2)

- [ ] 团队B: 说话人分离功能
- [ ] 集成: 音频自动索引
- [ ] 优化: 缓存热点查询
- [ ] 文档: 完整的API文档

---

## 🎓 附录

### A. 工作流YAML语法参考

```yaml
name: 工作流名称
description: 工作流描述
workflow_version: "1.0.0"

vars:
  key: value

tasks:
  - id: task_id
    name: 任务名称
    skill: skill_name
    params:
      param: value
    depends_on: [previous_task]
    timeout: 300

success_criteria:
  - task_id: task_name
    condition: "tests_passed > 90%"

notifications:
  on_complete:
    - type: slack
      channel: "#channel"
      message: "完成!"
```

### B. 常用命令

```bash
# 启动工作流
lingflow run workflow.yaml

# 查看状态
lingflow status

# 查看日志
lingflow logs --workflow workflow_name --follow

# 重试失败任务
lingflow retry --workflow workflow_name

# 回滚
lingflow rollback --workflow workflow_name --task task_id

# 停止工作流
lingflow stop --workflow workflow_name
```

### C. 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 工作流无法启动 | LingFlow未安装 | pip install lingflow |
| Docker连接失败 | Docker未运行 | docker-compose up -d |
| 数据库错误 | 数据库未就绪 | docker-compose exec postgres pg_isready |
| 依赖包冲突 | 版本不兼容 | pip install --upgrade |
| 内存不足 | 容器限制 | 增加Docker内存限制 |

---

**最后更新**: 2026-03-31
**文档版本**: 1.0.0
**审核状态**: ✅ 已完成创建，已审计（见 AUDIT_MULTI_WORKFLOW_GUIDE.md）
**下次更新**: 项目启动后1周
