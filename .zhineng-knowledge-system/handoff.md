# 灵知 (LingZhi) Handoff

## 最后更新
2026-06-11 23:55 UTC+8（会话：唤醒+提交+Skill化+LingBus讨论+安全修复+κ评估）

## 状态
active

## 本次会话产出（2026-06-11）

### 1. 60+文件提交 ✅（4 commits, 已推送gitea）

| Commit | 内容 |
|--------|------|
| `7e62bb09` | E1-E5全量产出（anomaly_detector+溯源+pre-commit+概念映射+κ评估） |
| `44f4d23f` | Skill化+安全修复（shell=True→列表参数+env变量+SQL常量） |
| `bf3dd59a` | search/ask端点HybridRetriever集成+query_expansion超时修复 |
| (latest) | handoff更新+κ基线 |

### 2. κ检索质量评估 ✅

| 指标 | 值 |
|------|-----|
| Top-1命中率 | 84% (42/50) |
| Top-3命中率 | 94% (47/50) |
| κ (Top-1) | 0.820 |
| κ (Top-3) | 0.932 |
| 评估集 | 50题，9领域 |
| 平均响应 | 5.9s/query（修复前12s→修复后<1s） |

### 3. 搜索性能修复 ✅

- **query_expansion**: expand_query加3s asyncio.wait_for超时，超时后fallback到本地expand_query_simple
- **search端点**: ILIKE搜索→HybridRetriever（向量+BM25），保留fallback
- **ask端点**: 同步集成HybridRetriever

### 4. Skill资产化 ✅

**文件**: `~/.lingfamily/skills/lingzhi-retrieval-eval/SKILL.md`
**manifest**: 已注册（9个skills，灵知1个）

### 5. 评估集选取标准文档化 ✅

**文件**: `data/eval/SELECTION_CRITERIA.md`

### 6. SDT注册 ✅（4条，全部带版本号）

| SDT ID | 名称 | 方向 | 优先级 |
|--------|------|------|--------|
| SDT-lz-001 | 知识库索引检查 | M-03 | P2 |
| SDT-lz-002 | 知识库健康巡检 | M-03 | P2 |
| SDT-lz-003 | 概念映射维护 | M-03 | P2 |
| SDT-lz-004 | 知识检索工程质量提升 | 跨方向 | P3 |

### 7. LingBus讨论回复 ✅

- 知识资产普查（thread `cc5bf3b3`）：9条可复用资产
- Skills资产化+统一Memory层（thread `655443f8`）：互补关系
- 底层思维方向错位（thread `121c1c0a`）：最大错位=④记忆≠上下文
- 张姐=统一Memory层（thread `7484837e`）：灵知可扩展为组织知识检索引擎

---

## 知识库数据

| 领域 | 文档数 |
|------|--------|
| 气功 | 61,323 |
| 佛家 | 6,971 |
| 科学 | 2,976 |
| 武术 | 2,041 |
| 道家 | 1,933 |
| 心理学 | 1,564 |
| 哲学 | 1,379 |
| 儒家 | 1,196 |
| 中医 | 574 |
| **总计** | **79,948** |

doc_chunks: 1,749,547（全有FTS+embedding，9域100%覆盖）

## 自进化进度

| 方向 | 状态 | 进度 |
|------|------|------|
| E1: 自主发现问题 | ✅ health_patrol + anomaly_detector + lifespan集成 + /health | 80% |
| E2: 溯源核实 | ✅ source_citation + citations + confidence | 65% |
| E3: 多智能体协作 | ✅ 巡检→灵信报告 | 20% |
| E4: 系统性预防 | ✅ pre-commit hook + 变更影响评估 | 40% |
| E5: 领域深度理解 | ✅ 概念映射(180概念) + 跨域检索 + kg导入(284/927) | 50% |
| E6: 边缘智能+硬件 | ⬜ 待实施 | 0% |

## 待办（按优先级）

1. **⚠️中风险47条细分** — 等用户确认分级发布后执行
2. **RAG验证升级** — 关键词→知识库RAG交叉验证（Docker API已修复可用）
3. **Embedding模型选型** — 对比bge-small-zh vs bge-large-zh vs bge-m3
4. **灵研κ一致性测试** — 等灵研发起
5. **佛家CBETA去重** — 1.55M chunks→~50K，需用户确认
6. **灵康v2第一层** — 263K古籍embedding（等灵通提供数据源）

## 阻塞项

- numpy 版本不兼容（宿主机 Python）
- 佛家CBETA去重需用户确认

---

## 关键端口

| 服务 | 端口 |
|------|------|
| API (Docker) | 8000 |
| PostgreSQL | 5436→5432 |
| Redis | 6381→6379 |
| Web (Nginx) | 8008→80 |