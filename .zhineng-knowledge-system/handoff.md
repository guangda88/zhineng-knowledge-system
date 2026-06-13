# 灵知 (LingZhi) Handoff

## 最后更新
2026-06-13 21:40 UTC+8（会话：CI修复 + SDT注册 + RAG交叉验证 + Skills补充 + Embedding选型）

## 状态
active

## 本次会话产出（2026-06-13）

### 1. GitHub推送欠债清理 ✅

| commit | 内容 |
|--------|------|
| `34045e46` | 知识库清理全量同步 + auth安全修复(PATH_TRAVERSE) + hybrid检索增强 |
| `3238ba5a` | CI修复 — flake8 E402豁免 + pytest DB schema初始化 + secret兜底 |
| `7e03e5bb` | embedding模型选型对比脚本 |

审计三步全通过，pre-commit/pre-push hook全通过。

### 2. CI修复 ✅

| 问题 | 修复 |
|------|------|
| flake8 E402 (main.py) | `.flake8` per-file-ignores 添加 `backend/main.py:E402` |
| pytest DB schema缺失 | CI添加 `psql -f init.sql` 初始化步骤 |
| TEST_DB_PASSWORD secret | 统一使用固定密码 `zhineng_test`，移除secret依赖 |
| conftest RuntimeError | DATABASE_URL兜底默认值 |

### 3. SDT程序化注册 ✅

4条SDT已注册到LingBus sdt_registry：

| SDT ID | 名称 | 间隔 | 方向 |
|--------|------|------|------|
| SDT-lz-001 | 检索质量巡检 | 1440m | D1 |
| SDT-lz-002 | 数据质量巡检 | 1440m | D1 |
| SDT-lz-003 | Embedding覆盖率检查 | 10080m | D2 |
| SDT-lz-004 | 知识库文档增长监控 | 1440m | D1 |

### 4. RAG交叉验证 ✅

`scripts/rag_cross_verify.py`：将关键词分类的健康声明用知识库检索交叉验证。

| 指标 | 值 |
|------|-----|
| 总声明 | 22 |
| 有知识库支撑 | 20 (90.9%) |
| 平均相似度 | 0.631 |
| 中风险有支撑 | 18/19 |
| 高风险有支撑 | 2/3 |

### 5. Skills补充 ✅

新增3个Skill（灵知总计4个，全族31个）：

| Skill | 覆盖内容 |
|-------|---------|
| lingzhi-hybrid-retrieval | 混合检索调优流程（权重+融合+rerank） |
| lingzhi-concept-map | 跨域概念映射构建（180概念） |
| lingzhi-data-quality-audit | 知识库数据质量审计（垃圾检测+去重+清理） |

### 6. Embedding模型选型框架 ✅

`scripts/embedding_model_comparison.py`：三模型对比框架就绪。

| 模型 | 维度 | 显存 | 状态 |
|------|------|------|------|
| bge-small-zh | 512 | 500MB | ✅ 当前使用 (κ=0.839) |
| bge-large-zh | 1024 | 1.5GB | ❌ 未下载 |
| bge-m3 | 1024 | 2.2GB | ❌ 未下载 |

**阻塞项**：numpy 2.2.6不兼容 + CUDA不可用

---

## 知识库数据

|| 领域 | 文档数 | chunks |
||------|--------|--------|
|| 气功 | 60,870 | 95,761 |
|| 科学 | 2,978 | 19,278 |
|| 武术 | 2,041 | 3,551 |
|| 佛家 | 1,632 | 143,652 |
|| 心理学 | 1,565 | 2,923 |
|| 哲学 | 1,398 | 7,211 |
|| 儒家 | 1,255 | 3,479 |
|| 道家 | 1,140 | 9,587 |
|| 中医 | 487 | 46,356 |
|| **总计** | **73,366** | **331,798** |

## 自进化进度

|| 方向 | 状态 | 进度 |
||------|------|------|
|| E1: 自主发现问题 | ✅ health_patrol + anomaly_detector | 80% |
|| E2: 溯源核实 | ✅ source_citation + RAG交叉验证 | 75% |
|| E3: 多智能体协作 | ✅ 巡检→灵信报告 | 20% |
|| E4: 系统性预防 | ✅ pre-commit hook + 变更影响评估 | 40% |
|| E5: 领域深度理解 | ✅ 概念映射(180概念) + 跨域检索 | 50% |
|| E6: 边缘智能+硬件 | ⬜ 待实施 | 0% |

## 待办（按优先级）

1. **⚠️ CI验证** — 确认推送后CI通过（flake8 + pytest）
2. **numpy降级** — `pip install 'numpy<2'` 解除embedding选型阻塞
3. **Embedding选型执行** — numpy修复后下载bge-large-zh跑对比
4. **中风险47条细分** — 等用户确认分级
5. **灵康v2第一层** — 263K古籍embedding（等灵通提供数据源）

## 阻塞项

- numpy 版本不兼容（宿主机 Python）— embedding选型阻塞
- CI pytest可能因DB schema差异仍失败（需观察下一次CI运行）

---

## 关键端口

|| 服务 | 端口 |
||------|------|
|| API (Docker) | 8000 |
|| PostgreSQL | 5436→5432 |
|| Redis | 6381→6379 |
|| Web (Nginx) | 8008→80 |
