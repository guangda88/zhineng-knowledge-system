# 灵知主线任务

**日期**: 2026-05-07
**依据**: 数据库实况 + git status + 未提交脚本分析

---

## 一、现状数据

| 领域 | 文档数 | 占比 | 平均长度 | 来源数 | 健康度 |
|------|--------|------|----------|--------|--------|
| 气功 | 61,337 | 79.8% | 425 | 0 | ⚠️ 来源单一 |
| 佛家 | 6,971 | 9.1% | 60,253 | 0 | ⚠️ 来源单一，文档过长 |
| 科学 | 2,920 | 3.8% | 1,546 | 951 | ✅ |
| 道家 | 1,925 | 2.5% | 17,560 | 397 | ⚠️ 文档过长 |
| 心理学 | 1,521 | 2.0% | 396 | 703 | ✅ |
| 哲学 | 1,378 | 1.8% | 1,120 | 544 | ✅ |
| 武术 | 514 | 0.7% | 668 | 171 | 🔴 严重不足 |
| 儒家 | 201 | 0.3% | 1,786 | 0 | 🔴 严重不足 |
| 中医 | 80 | 0.1% | 11,819 | 0 | 🔴 极度不足 |

**总计**: 76,847 文档，全部有 embedding

### 核心问题
1. **数据极度倾斜** — 气功占 80%，6 个领域合计不足 10%
2. **来源不明** — 气功/佛家/儒家/中医的 metadata->source 全部为空
3. **文档粒度不均** — 佛家平均 60K 字（未分块？），气功仅 425 字

---

## 二、主线任务（按优先级）

### P0: 数据补全 — 消除领域短板

**目标**: 中医→500+，儒家→1000+，武术→2000+，各领域来源≥3

- [ ] 运行 `scripts/import_tcm_wikisource.py` — 中医核心经典（黄帝内经、伤寒论等）
- [ ] 运行 `scripts/import_confucian_wikisource.py` — 儒家六经
- [ ] 运行 `scripts/import_martial_arts_wikisource.py` — 武术典籍
- [ ] 运行 `scripts/import_philosophy_wikisource.py` — 先秦诸子补全
- [ ] 运行 `scripts/import_openalex.py` — 学术论文（科学/心理学/哲学）
- [ ] 提交这批 import 脚本（已写好，在 git status 中为 untracked）

**阻塞**: 需要网络访问 wikisource/openalex，需确认脚本可用

### P1: 数据治理 — 质量对齐

**目标**: 所有文档粒度合理（500-2000字），来源可追溯

- [ ] 佛家文档分块 — 60K 平均长度说明是整本书未切分，需按章节/段落 chunk
- [ ] 道家文档分块 — 同理，17K 平均长度
- [ ] 中医文档分块 — 12K 平均长度
- [ ] 为气功/佛家/儒家/中医补充 source 元数据
- [ ] 重建受影响领域的 embedding（用宿主机 GPU，40x 加速）

### P2: 检索质量优化

**目标**: MRR@10 从 0.876 提升到 0.92+

**现状基线**（`data/training/baseline_metrics.json`）:
- MRR@10: 0.876
- Recall@5: 0.910
- Recall@10: 0.930
- Intent F1: 0.786

- [ ] 分析 P0 数据补全后的检索指标变化
- [ ] 针对弱势领域（武术/儒家/中医）构造领域测试集
- [ ] 评估 BGE-small-zh 微调的必要性
- [ ] 实现 `/ask` 端点溯源模式（回答附带文档 ID 和原文片段）

### P3: 系统稳定性

**目标**: CI 全绿，Docker 环境可一键启动

- [ ] 修复 `test_pipeline_api.py` 超时（需 mock 或拆分）
- [ ] 修复 `test_reasoning.py` 2 个失败用例（DEEPSEEK_API_KEY 相关）
- [ ] 修复 `test_watchdog.py` 4 个失败用例
- [ ] 清理 `.audit/exclude_tests.txt` — 长期方案应修复测试而非排除

### P4: 未提交资产整理

**目标**: 工作区干净，所有有价值的脚本入库

- [ ] 提交 import 脚本（5 个 wikisource + 1 个 openalex）
- [ ] 提交 `scripts/fast_embed.py`、`scripts/evaluate_baseline.py`
- [ ] 提交 `data/training/baseline_metrics.json`
- [ ] 提交修改的 `import_daoist_wikisource.py`、`import_fodao_from_guoxue.py`、`import_missing_domains.py`
- [ ] 清理 `.audit/exclude_tests.txt`（提交或删除）
- [ ] 清理 OWData 旧日志文件

---

## 三、不做的事（明确排除）

- ❌ 不做前端开发（灵网负责）
- ❌ 不做新功能开发（当前数据质量是瓶颈，不是功能）
- ❌ 不做模型微调（先补数据再评估）
- ❌ 不做基础设施改造（Docker 配置够用）

---

## 四、立即下一步

1. 提交 P4 未提交资产（快速，无风险）
2. 启动 P0 数据补全（网络依赖，需监控）
3. P0 完成后启动 P1 数据治理
