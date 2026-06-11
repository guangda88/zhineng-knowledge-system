# 灵知 (LingZhi) Handoff

## 最后更新
2026-06-09 23:45 UTC+8（会话：自驱任务 — E1异常检测 + E2溯源 + E4 pre-commit + E5九域概念映射）

## 状态
active

## 本次会话产出（2026-06-09）

### 1. E1 anomaly_detector.py ✅

**文件**: `backend/monitoring/anomaly_detector.py`（新增 ~250行）
**测试**: `tests/test_anomaly_detector.py`（21 tests passed）

基于阈值的异常检测器，5条默认规则（检索延迟/API延迟/429频率/DB延迟/磁盘）。
已集成到 lifespan 启动/停止、API中间件实时采集、/health 端点状态输出。
回调接通 LingBus（非阻塞降级为 logger.warning）。

### 2. E2 /ask 溯源模式 ✅

- ChatResponse 增加 `citations: List[Dict]` + `confidence: str`
- citations 包含 title, source_table, doc_id, category, snippet, similarity
- confidence: "sourced"（有来源）/ "unverified"（无来源）

### 3. E4 pre-commit hook ✅

**文件**: `scripts/pre_commit_check.py`（新增 ~150行）
四步自检：敏感文件/密钥检测 → Python语法 → Ruff lint (仅staged) → 冒烟测试。

**文件**: `scripts/change_impact.py`（新增 ~130行）
变更影响评估：风险分级(HIGH/MEDIUM/LOW) + 影响域识别 + 变更行数统计。

### 4. E5 九域概念映射 ✅

**文件**: `backend/services/knowledge_graph/concept_map.py`（新增 ~250行，~180概念）
**测试**: `tests/test_concept_map.py`（18 tests passed）

- ~180核心概念→关联领域映射（意元体→气功+哲学+心理学 等）
- search/hybrid 端点返回 `related_domains` + `concepts` 字段
- 跨域联合检索: `backend/services/retrieval/cross_domain.py`
- API端点: `GET /api/v1/search/cross-domain?q=意元体`
- 概念导入 kg_entities/kg_relations: **284 entities, 927 relations**

### 5. 代码清理

- `scripts/health_patrol.py`: 修复4个ruff警告
- `backend/api/v2/authenticated.py`: 清除2个unused import

### 6. 全量测试

**1082 passed, 2 skipped**（含39个新测试: 21 anomaly_detector + 18 concept_map）

### 7. 健康巡检

`health_patrol.py --quick`: 4/4 通过（API 366ms、DB 79ms、13容器、磁盘64.6%）

---

## 历史产出（2026-06-07）

### 62+3文件提交推送 ✅
- 提交：`d25c72ac` + `2eb2fa56`，已推送 gitea/develop
- 安全：auth/middleware P0修复，JWT认证逻辑重写
- 重构：16个v1路由统一依赖注入
- 测试：1000 passed, 2 skipped

### 何氏虛勞心傳全文导入 ✅
- doc_id=399826，97 chunks，向量+FTS双索引

### 中医经典批量导入 ✅
- 8部经典，中医领域 566→574 docs，新增1259 chunks

---

## 历史产出（2026-06-05）

### 参与灵族3方向×16细方向讨论（4轮）

| 方向 | 细方向 | 角色 | 状态 |
|------|--------|------|------|
| 方向2D | 知识自治 | **主** | ✅ 积极同意 |
| 方向1D | 内容诚信 | **辅**（RAG验证） | ✅ 积极同意 |
| 方向3B | 健康知识服务 | 暂空缺 | ✅ 撤回 |

### 20集健康声明验证脚本 ✅
- 97条声明：3❌高风险 / 47⚠️中风险 / 47✅低风险

### Governance投票
- SIGNING_KEY设置: approve
- 3方向×16细方向分工v0.2: approve

---

## 待办（按优先级）

1. **灵研κ一致性测试** — 等灵研发起
2. **⚠️中风险47条细分** — 等用户确认分级发布后执行
3. ~~**SIGNING_KEY设置**~~ — ✅ 已修复(2026-06-10)：~/.bashrc旧key→source ~/.ling_keys.env，key+caller_secret均正确加载
4. **RAG验证升级** — 关键词→知识库RAG交叉验证（Docker API需先修复）
5. **佛家CBETA去重** — 1.55M chunks→~50K，需用户确认
6. **灵康v2第一层** — 263K古籍embedding（等灵通提供数据源）
7. **提交所有变更** — 60+文件变更需用户确认后commit

---

## 阻塞项

- **Docker API端点不确定** — /api/v1/search vs /search
- 灵通+ proxy Docker网络未通
- numpy 版本不兼容（宿主机 Python）
- 佛家CBETA去重需用户确认

---

## 检索质量评估（2026-06-05）✅

| 指标 | 值 |
|------|-----|
| 命中率 | 25/27 (92.6%) |
| Top-1 相似度 | 0.734 |
| 平均延迟 | 4394ms |

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

doc_chunks: 1,749,547（全有FTS+embedding）

---

## 自进化进度

| 方向 | 状态 | 进度 |
|------|------|------|
| E1: 自主发现问题 | ✅ health_patrol + anomaly_detector + lifespan集成 + /health | 80% |
| E2: 溯源核实 | ✅ source_citation + citations + confidence | 65% |
| E3: 多智能体协作 | ✅ 巡检→灵信报告 | 20% |
| E4: 系统性预防 | ✅ pre-commit hook + 变更影响评估 | 40% |
| E5: 领域深度理解 | ✅ 概念映射(180概念) + 跨域检索 + kg导入(284/927) | 50% |
| E6: 边缘智能+硬件 | ⬜ 待实施 | 0% |

---

## PG连接

```
postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb
```

## 关键端口

| 服务 | 端口 |
|------|------|
| API | 8001→8000 |
| PostgreSQL | 5436→5432 |
| Redis | 6381→6379 |
| Web (Nginx) | 8008→80 |
