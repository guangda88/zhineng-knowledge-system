# 灵知 (LingZhi) Handoff

## 最后更新
2026-06-11 22:55 UTC+8（会话：唤醒+提交+Skill化+LingBus讨论）

## 状态
active

## 本次会话产出（2026-06-11）

### 1. 60+文件提交 ✅

**Commit**: `7e62bb09` + `44f4d23f`

E1-E5全量产出提交：
- E1 anomaly_detector.py（~250行，21 tests）
- E2 溯源模式（citations + confidence）
- E4 pre-commit hook + 变更影响评估
- E5 九域概念映射（180概念，284 entities，927 relations）
- 检索质量评估（κ=0.839，27题评估集）
- 安全修复（shell=True→列表参数，硬编码密码→env变量，SQL f-string→常量内联）

### 2. κ检索质量评估 Skill化 ✅

**文件**: `~/.lingfamily/skills/lingzhi-retrieval-eval/SKILL.md`
**manifest**: 已注册到 `~/.lingfamily/skills/manifest.json`

灵知第一个Skill：评估5步流程 + 基线数据 + 调优参数 + 常见失败case。

### 3. 评估集选取标准文档化 ✅

**文件**: `data/eval/SELECTION_CRITERIA.md`

领域覆盖/难度分布/expected_doc_ids确认规则/排除规则/扩展标准。

### 4. SDT注册到灵信系统 ✅

| SDT ID | 名称 | 方向 | 优先级 |
|--------|------|------|--------|
| SDT-lz-001 | 知识库索引检查 | M-03 | P2 |
| SDT-lz-002 | 知识库健康巡检 | M-03 | P2 |
| SDT-lz-003 | 概念映射维护 | M-03 | P2 |
| SDT-lz-004 | 知识检索工程质量提升 | 跨方向 | P3 |

### 5. LingBus讨论回复 ✅

- 知识资产普查（thread `cc5bf3b3`）：9条可复用资产
- Skills资产化+统一Memory层（thread `655443f8`）：互补关系，灵知贡献语义检索引擎
- 底层思维模式方向错位（thread `121c1c0a`）：最大错位=④记忆≠上下文（每次κ评估从零推导）
- 张姐=统一Memory层（thread `7484837e`）：灵知可扩展为组织知识检索引擎

---

## 历史产出（2026-06-09）

### E1-E5 自进化里程碑 ✅

- E1 anomaly_detector: 5条阈值规则 + lifespan集成 + /health输出 + LingBus回调
- E2 溯源模式: ChatResponse增加citations/confidence字段
- E4 pre-commit hook: 敏感文件/密钥检测 + 语法/lint/冒烟测试
- E4 变更影响评估: 风险分级 + 影响域识别
- E5 九域概念映射: 180概念 + 跨域检索
- E5 知识图谱导入: 284 entities, 927 relations
- 1082 tests passed, 2 skipped

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

## 待办（按优先级）

1. **科学/心理学领域数据采集** — 各≥1000条documents，补齐9领域覆盖
2. **⚠️中风险47条细分** — 等用户确认分级发布后执行
3. **RAG验证升级** — 关键词→知识库RAG交叉验证（Docker API search路由缺失，需修复）
4. **Embedding模型选型** — 对比bge-small-zh vs bge-large-zh vs bge-m3
5. **佛家CBETA去重** — 1.55M chunks→~50K，需用户确认
6. **灵康v2第一层** — 263K古籍embedding（等灵通提供数据源）
7. **灵研κ一致性测试** — 等灵研发起

---

## 阻塞项

- **Docker API search路由缺失** — 容器内只有embed/health端点，需排查路由注册
- 灵通+ proxy Docker网络未通
- numpy 版本不兼容（宿主机 Python）
- 佛家CBETA去重需用户确认

---

## 检索质量评估

| 指标 | 值 |
|------|-----|
| κ (Cohen's) | 0.839 |
| Top-1 命中率 | 85.7% (23/27) |
| Top-3 命中率 | 90.5% |
| 评估集规模 | 27题 |
| Skill | ✅ 已资产化 |

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
