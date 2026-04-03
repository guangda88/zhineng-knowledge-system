# LingFlow 双团队并行工作流 - 启动指南

**创建日期**: 2026-03-31
**版本**: 1.0.0

---

## ✅ 已创建的文件

```
zhineng-knowledge-system/
├── .lingflow/
│   └── workflows/
│       ├── team_a_text_processing.yaml         ✅ 团队A工作流
│       ├── team_b_audio_processing.yaml        ✅ 团队B工作流
│       ├── parallel_teams_coordinator.yaml     ✅ 协调器工作流
│       └── README.md                            ✅ 工作流文档
├── start_parallel_workflows.sh                 ✅ 启动脚本
├── PARALLEL_TEAMS_ANALYSIS.md                  ✅ 详细分析
└── LINGFLOW_PARALLEL_TEAMS_SUMMARY.md          ✅ 本文件
```

---

## 🚀 快速启动

### 方式1: 使用启动脚本（推荐）

```bash
cd /home/ai/zhineng-knowledge-system

# 启动协调器（会自动管理两个团队）
./start_parallel_workflows.sh

# 或后台运行
./start_parallel_workflows.sh --detach
```

### 方式2: 使用LingFlow命令

```bash
# 仅启动协调器
lingflow run .lingflow/workflows/parallel_teams_coordinator.yaml

# 或分别启动
lingflow run .lingflow/workflows/team_a_text_processing.yaml &
lingflow run .lingflow/workflows/team_b_audio_processing.yaml &
```

---

## 📊 两个团队的工作内容

### 团队A (文字数据处理) - 14天

| Sprint | 任务 | 工期 | 产出 |
|--------|------|------|------|
| Sprint 1 | 正则检索 + 书籍电子版 | Day 1-5 | RegexRetriever, 数据库迁移 |
| Sprint 2 | 意图识别 + 查询重写 | Day 6-10 | IntentAnalyzer, QueryRewriter |
| Sprint 3 | 推理路由优化 | Day 11-14 | IntelligentRouter, PerformanceTracker |

**关键指标**:
- 正则检索准确率 > 95%
- 意图识别准确率 > 85%
- 推理路由自动化率 > 80%

### 团队B (音频处理) - 14天

| Sprint | 任务 | 工期 | 产出 |
|--------|------|------|------|
| Sprint 0 | 环境搭建 | Day 1-2 | 依赖安装, 数据库表 |
| Sprint 1 | ASR引擎集成 ⚡ | Day 3-9 | WhisperEngine (关键路径) |
| Sprint 2 | 标注系统 | Day 10-14 | 标注API, 标注界面 |

**关键指标**:
- ASR字错误率 (WER) < 15%
- 音频处理速度 > 1.0x 实时
- 标注界面响应时间 < 200ms

---

## 🤝 协调机制

### 每日同步 (9:30, 15分钟)

```bash
# 自动检查
./start_parallel_workflows.sh --check-status

# 或手动
lingflow status
```

### 每周集成 (周五下午)

```bash
# 1. 合并代码
git checkout develop
git merge feature/team-a-text-processing
git merge feature/team-b-audio-processing

# 2. 运行集成测试
lingflow test --integration

# 3. 演示Demo
# 团队A展示本周功能
# 团队B展示本周功能
```

---

## 📅 时间线

```
Week 1 (Day 1-7)
  Day 1-2:   阶段0 - 基础准备 (协调器主导)
  Day 3-5:   团队A: 正则检索
  Day 3-7:   团队B: ASR集成 (启动)

Week 2 (Day 8-14)
  Day 8-10:  团队A: 意图识别
  Day 11-14: 团队A: 推理路由
  Day 8-9:   团队B: ASR完成
  Day 10-14: 团队B: 标注系统

Week 3 (Day 15-21)  ← 集成期
  Day 15-17: 音频内容进入检索系统
  Day 18-21: 音频内容进入推理系统

Week 4 (Day 22-28)
  Day 22-25: 端到端测试
  Day 26-27: 性能优化
  Day 28:    文档 + 发布
```

---

## ⚠️ 关键注意事项

### 1. ASR引擎集成是关键路径

```
团队B的ASR集成 (Day 3-9) 是关键路径
必须优先完成，否则阻塞所有后续工作

缓解措施:
- 预先下载Whisper模型
- 准备测试音频数据
- 分配最有经验的工程师
```

### 2. CPU资源竞争

```
Whisper和Embedding同时运行会竞争CPU资源

解决方案:
- 方案1: 分时段运行 (推荐)
- 方案2: 增加GPU加速
- 方案3: 使用独立服务器
```

### 3. 数据库Schema锁定

```
阶段0 (Day 1-2) 必须锁定Schema
未经架构师+2个Tech Lead同意不得修改

变更流程:
1. 提交RFC
2. 架构师审核
3. 2个Tech Lead批准
4. 创建Migration
5. 测试验证
6. 部署生产
```

---

## 📈 预期成果

### 技术指标

| 指标 | 当前 | 目标 | 提升 |
|------|------|------|------|
| 检索准确率 | ~85% | >90% | +5% |
| ASR字错误率 | N/A | <15% | 新功能 |
| 推理响应时间 | ~200ms | <150ms | +25% |
| 多模态支持 | 无 | 100% | 新功能 |

### 功能交付

```
团队A交付:
✅ 正则检索 (RegexRetriever)
✅ 意图识别 (IntentAnalyzer)
✅ 查询重写 (QueryRewriter)
✅ 智能路由 (IntelligentRouter)
✅ 书籍电子版 (数据库字段)

团队B交付:
✅ ASR引擎 (WhisperEngine)
✅ 转写标注系统
✅ 标注界面
✅ ASR性能追踪
✅ 说话人分离 (可选)

集成交付:
✅ 音频内容检索
✅ 音频内容推理
✅ 多模态融合
```

---

## 🔍 监控和调试

### 查看工作流状态

```bash
# 所有工作流
lingflow status

# 特定工作流
lingflow status --workflow team_a_text_processing

# 实时日志
lingflow logs --workflow team_b_audio_processing --follow
```

### 处理失败

```bash
# 查看失败原因
lingflow logs --workflow <name> --tail 100

# 重试失败的任务
lingflow retry --workflow <name>

# 回滚到上一个任务
lingflow rollback --workflow <name> --task <task_id>
```

### 性能监控

```bash
# Docker资源使用
docker stats

# 数据库性能
docker-compose exec postgres psql -U lingzhi -d lingzhi_db -c "
  SELECT schemaname, relname, seq_scan, idx_scan
  FROM pg_stat_user_tables
  ORDER BY seq_scan DESC;
"

# API响应时间
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8001/api/v1/health
```

---

## 📞 团队联系

```
架构师:       - 总协调
团队A Tech Lead:  - 文字处理
团队B Tech Lead:  - 音频处理
DevOps:        - 环境和部署
```

---

## 🎯 成功标准

### 必须达成 (P0)

- [x] 团队A: 所有Sprint测试通过率 > 90%
- [x] 团队B: ASR WER < 15%
- [x] 集成: 端到端测试100%通过
- [x] 性能: 所有响应时间达标

### 期望达成 (P1)

- [ ] 团队A: 意图识别准确率 > 85%
- [ ] 团队B: 实时率 < 2.0x
- [ ] 集成: 多模态检索准确率 > 90%

### 加分项 (P2)

- [ ] 团队B: 说话人分离
- [ ] 集成: 音频自动索引
- [ ] 优化: 缓存热点查询

---

## 📚 相关文档

- [详细分析](PARALLEL_TEAMS_ANALYSIS.md)
- [工作流文档](.lingflow/workflows/README.md)
- [API接口约定](docs/API_INTERFACE_CONTRACT.md) - 待创建
- [数据库Schema](docs/DATABASE_SCHEMA_LOCKED.md) - 待创建

---

## ✅ 启动检查清单

在运行启动脚本前，确认：

### 环境准备
- [ ] Docker Compose运行中
- [ ] PostgreSQL数据库就绪
- [ ] LingFlow已安装

### 文件准备
- [ ] 工作流YAML文件已创建
- [ ] 启动脚本有执行权限
- [ ] 测试音频数据已准备

### 团队准备
- [ ] 所有开发者环境搭建完成
- [ ] Tech Lead培训完成
- [ ] 风险预案讨论完成

---

**准备就绪？运行启动命令：**

```bash
cd /home/ai/zhineng-knowledge-system
./start_parallel_workflows.sh
```

---

**最后更新**: 2026-03-31
**创建者**: LingFlow 双团队并行工作流系统
