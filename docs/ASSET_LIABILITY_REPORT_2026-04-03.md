# 智能知识系统 — 资产与负债盘点报告

> **日期**: 2026-04-03
> **版本**: v1.0
> **范围**: `/home/ai/zhineng-knowledge-system` 全项目

---

## 目录

- [第一部分：资产盘点](#第一部分资产盘点)
  - [一、核心架构资产](#一核心架构资产)
  - [二、数据资产](#二数据资产)
  - [三、AI/ML 资产](#三aiml-资产)
  - [四、基础设施资产](#四基础设施资产)
- [第二部分：负债盘点](#第二部分负债盘点)
  - [一、安全负债](#一安全负债)
  - [二、数据负债](#二数据负债)
  - [三、代码负债](#三代码负债)
  - [四、基础设施负债](#四基础设施负债)
  - [五、测试负债](#五测试负债)
- [第三部分：盘活方案](#第三部分盘活方案)
  - [第一阶段：紧急清债（1-2天）](#第一阶段紧急清债12天)
  - [第二阶段：数据导入（3-5天）](#第二阶段数据导入35天)
  - [第三阶段：代码治理（5-7天）](#第三阶段代码治理57天)
  - [第四阶段：能力升级（持续）](#第四阶段能力升级持续)

---

# 第一部分：资产盘点

## 一、核心架构资产

### 1.1 已完成且可用的核心模块

| 模块 | 文件 | 状态 | 价值评估 |
|------|------|------|---------|
| **混合检索引擎** | `services/retrieval/` | ✅ 完整 | 🔴 极高 — 向量+BM25+RRF融合，生产级 |
| **十领域路由系统** | `domains/` (10个) | ✅ 完整 | 🔴 极高 — 气功/中医/儒家/佛家/道家/武术/哲学/科学/心理学/通用 |
| **二级缓存** | `cache/manager.py` | ✅ 完整 | 🟠 高 — L1内存+L2Redis，三种写策略，热键追踪 |
| **JWT认证** | `auth/jwt.py` + `middleware.py` | ✅ 完整 | 🟠 高 — RS256非对称加密，自动续签，Token黑名单 |
| **API网关** | `gateway/` (router+circuit_breaker+rate_limiter) | ✅ 完整 | 🟠 高 — 熔断器+限流器+域名路由，4种策略 |
| **监控体系** | `monitoring/` (4个模块) | ✅ 完整 | 🟠 高 — HealthChecker+MetricsCollector+Prometheus+缓存指标 |
| **知识图谱** | `services/knowledge_graph/` | ✅ 完整 | 🟡 中 — 8实体类型+6关系类型，正则提取 |
| **推理引擎** | `services/reasoning/` (CoT/ReAct/GraphRAG/Auto) | ✅ 架构完整 | 🟠 高 — 依赖外部LLM API Key |
| **教材处理管线** | `textbook_processing/` | ✅ 完整 | 🟠 高 — 自动TOC提取+AI扩展+分段+质量评估 |
| **内容生成框架** | `services/generation/` | ✅ 框架完整 | 🟡 中 — 报告/课程/PPT可用，视频未实现 |

### 1.2 API 资产（171 端点）

| 模块 | 端点数 | 核心能力 |
|------|--------|---------|
| search | ~12 | 关键词搜索、混合检索、向量更新、问答 |
| documents | ~15 | 文档CRUD、分类过滤 |
| reasoning | ~8 | 推理/CoT/ReAct/GraphRAG/图谱查询 |
| annotation | ~20 | 音频标注、标签体系、协作评论 |
| books | ~12 | 教材搜索、章节浏览 |
| audio | ~15 | 上传、转写(5引擎)、分段 |
| sysbooks | ~10 | 302万图书编目查询 |
| guoxue | ~8 | 26万古籍查询 |
| evolution | ~10 | AI对比、进化日志 |
| 其他 | ~61 | 学习、生成、外部数据、健康检查等 |

---

## 二、数据资产

### 2.1 离线已处理数据（SQLite，总计 ~9.2 GB）

| 数据库 | 大小 | 内容 | 状态 |
|--------|------|------|------|
| `data/external/Sys_books.db` | **2.4 GB** | 302万条图书编目 | ✅ 完整，未导入PG |
| `lingzhi_ubuntu/database/guoxue.db` | **6.3 GB** | 26.4万条古籍（110个wx表） | ⚠️ 仅导出3000条 |
| `lingzhi_ubuntu/database/wxlb.db` | 98 MB | 文学列表 | ❌ 未导入 |
| `lingzhi_ubuntu/database/kxzd.db` | 18 MB | 康熙字典 | ❌ 未导入 |
| `lingzhi_ubuntu/database/skqs2018.db` | 2.9 MB | 四库全书2018 | ❌ 未导入 |
| `data/textbooks.db` | 496 MB | 9卷教材（3,211章节+304文档） | ✅ 完整，未导入PG |
| `data/data.db` | 296 MB | 云盘索引（90.7万文件） | ✅ 完整，未导入PG |

### 2.2 原始文件资产（~705 MB）

| 类型 | 数量 | 说明 |
|------|------|------|
| PDF | ~106 | 9本核心教材 + 辅导材料 + 1992-1999年杂志 |
| TXT | ~199 | 文章、讲义、庞明老师答疑集 |
| DOC/DOCX | ~40 | 各类文档 |

### 2.3 PostgreSQL 已导入数据

| 表 | 行数 | 内容 |
|---|---|---|
| `guji_documents` | 3,000 | 古籍文本（仅wx200表的2.8%） |
| `guji_file_book_mapping` | 42 | 文件-书籍映射 |
| `user_activity_log` | 8 | 运行时数据 |
| `guji_content_mapping` | 7 | 内容映射 |
| `user_feedback` | 6 | 运行时数据 |
| `user_profile` | 4 | 运行时数据 |
| **其余64张表** | **0** | 空表 |

---

## 三、AI/ML 资产

### 3.1 LLM 提供商（7个，月均免费 ~1.11 亿 token）

| 提供商 | 模型 | 免费额度 |
|--------|------|---------|
| GLM (智谱) | glm-4-flash 等 | Coding Plan 1亿 token/月 |
| DeepSeek | deepseek-chat | — |
| 通义千问 | qwen-max 等 | — |
| 混元 | hunyuan-lite 等 | — |
| 豆包 | doubao-pro 等 | — |
| Claude (CLIProxy) | claude-3.5-sonnet | — |

### 3.2 Embedding 模型

| 模型 | 维度 | 部署 |
|------|------|------|
| BGE-M3 | 1024 | Docker 微服务 (4G/2CPU) |
| BGE-small-zh-v1.5 | 512 | 内嵌调用 |

### 3.3 语音能力

| 类型 | 引擎数 | 明细 |
|------|--------|------|
| ASR | 5 | Whisper, Cohere, FunASR, SenseVoice, 听悟 |
| TTS | 1 | edge-tts (Microsoft, 免费) |

---

## 四、基础设施资产

| 资产 | 规模 |
|------|------|
| Docker 服务 | 9 个（PG+Redis+Embedding+API+Nginx+Prometheus+Grafana+2个Exporter） |
| 告警规则 | 20 条（已定义但未启用） |
| 运维脚本 | 60+ 个 |
| 文档 | 140+ 个 |
| CI/CD | GitHub Actions (lint + test + security) |

---

# 第二部分：负债盘点

## 一、安全负债

### 🔴 S1: JWT 私钥已提交到 Git

| 项目 | 详情 |
|------|------|
| **文件** | `jwt_private.pem`, `jwt_public.pem` |
| **风险** | 任何有权访问仓库的人可获得 JWT 签名密钥，伪造任意用户身份 |
| **影响范围** | 全系统认证体系 |
| **修复** | 从 Git 历史中清除密钥，重新生成密钥对，加入 `.gitignore` |

### 🔴 S2: 数据库密码硬编码在 16+ 脚本中

| 密码 | 出现文件数 |
|------|-----------|
| `zhineng_secure_2024` | 11 个脚本 |
| `zhineng123` | 7 个脚本 |
| `postgres:postgres` | 2 个脚本 |

**影响**: 源码泄露即导致数据库被入侵。

### 🔴 S3: JWT Secret 硬编码在配置文件中

| 文件 | 内容 |
|------|------|
| `data/config.json` | `"jwt_secret": "fhiklwCEOkdRRqpK"` |
| `docker-compose.cli-proxy.yml` | `JWT_SECRET=${JWT_SECRET:-lingzhi-default-secret-change-in-production}` |

### 🟠 S4: 浏览器 Cookie 和会话数据存储在仓库中

| 文件 | 内容 |
|------|------|
| `data/textbooks/ima_cookies.json` | ima.qq.com 登录 Cookie |
| `data/textbooks/ima_cookies_selenium.json` | Selenium 会话 Cookie |
| `data/textbooks/ima_page_logged_in.html` | 已登录页面快照 |

### 🟡 S5: 内网 IP 泄露

- `backend/config/security.py:27` — `http://100.66.1.8:8008`
- `scripts/verify_bid_mapping.py:16` — `http://100.66.1.8:2455`

---

## 二、数据负债

### 🔴 D1: PostgreSQL 数据库基本为空壳

**70 张表中仅 6 张有数据**，核心业务表全部为 0 行：

| 空 table | 预期行数 | 价值损失 |
|---|---|---|
| `sys_books` | 302 万 | 图书检索不可用 |
| `sys_book_contents` / `sys_book_chunks` | 数十万 | 内容搜索不可用 |
| `documents` | 数千 | 文档检索不可用 |
| `textbook_nodes` / `textbook_blocks` | 3,200+ | 教材浏览不可用 |
| `kg_entities` / `kg_relations` | 数千 | 知识图谱不可用 |
| `books` / `book_chapters` | 数百 | 教材搜索不可用 |

**这是最大的资产浪费** — 系统有完善的检索架构，但没有数据可检索。

### 🔴 D2: 6.3 GB 古籍数据仅导入 1.1%

- 源库 `guoxue.db` 有 **263,767 条**，仅导入 **3,000 条**（wx200 表的 2.8%）
- 109 个 wx 表完全未导入

### 🔴 D3: SQLite 数据库零备份

| 数据库 | 大小 | 备份 |
|--------|------|------|
| `Sys_books.db` | 2.4 GB | ❌ 无 |
| `guoxue.db` | 6.3 GB | ❌ 无 |
| `wxlb.db` | 98 MB | ❌ 无 |
| `kxzd.db` | 18 MB | ❌ 无 |
| `textbooks.db` | 496 MB | ❌ 无 |
| `data.db` | 296 MB | ❌ 无 |

备份脚本 `scripts/backup.sh` 仅备份 PostgreSQL，**SQLite 数据全裸奔**。

### 🟠 D4: SQLite ↔ PostgreSQL 数据重复

| 数据 | SQLite | PostgreSQL | 同步状态 |
|------|--------|-----------|---------|
| 图书编目 | `Sys_books.db` (302万) | `sys_books` (0) | ❌ 未同步 |
| 教材 | `textbooks.db` (9册) | `textbook_nodes` (0) | ❌ 未同步 |
| 古籍 | `guoxue.db` (26万) | `guji_documents` (3千) | ❌ 部分同步 |

### 🟡 D5: 数据处理重复

- `data/processed/textbooks/` 和 `data/processed/textbooks_v2/` 包含相同教材的两次处理结果
- `data/textbooks_duplicate_backup/` 包含手动复制的备份文件
- `data/context/` 有 25 个会话文件无清理策略

---

## 三、代码负债

### 🔴 C1: 伪造的安全审计结果

`backend/services/optimization/auditor.py` 的 3 个安全检查函数返回**伪造数据**：

```python
# 第112行: API密钥检查 → 返回 fabricated 结果
# 第124行: SQL注入检查 → 返回 fabricated 结果  
# 第136行: 依赖漏洞检查 → 返回 fabricated 结果
```

**风险**: 用户以为安全检查已执行，实际什么都没做。

### 🔴 C2: 损坏的导入 — `AI_HOOKS_AVAILABLE` 永远为 True

`backend/core/__init__.py` 第17-22行：

```python
try:
    pass                          # ← 没有实际导入
    AI_HOOKS_AVAILABLE = True     # ← 永远为 True
except ImportError:
    AI_HOOKS_AVAILABLE = False
```

后续代码引用未导入的 `AIActionWrapper`、`RulesChecker` 等符号，将触发 `NameError`。

### 🟠 C3: `lingminopt.py` 重复实现

同一模块存在两个不同版本：

| 文件 | 行数 | 用途 |
|------|------|------|
| `services/evolution/lingminopt.py` | ~825 | 进化系统版本 |
| `services/optimization/lingminopt.py` | ~437 | 优化系统版本 |

且 `services/optimization/` 整个模块自声明为 "experimental and incomplete, not recommended for production"。

### 🟠 C4: 大量 TODO/FIXME 未完成

| 文件 | 内容 |
|------|------|
| `api/v1/analytics.py:426` | 管理员接口缺少权限检查 |
| `services/optimization/lingminopt.py:304` | 论坛反馈分析返回空列表 |
| `services/annotation/ocr_annotator.py:255` | 模型微调未实现 |
| `services/annotation/transcription_annotator.py:217` | 模型微调未实现 |

### 🟠 C5: 过度捕获异常（100 处 `except Exception`）

| 区域 | 数量 |
|------|------|
| `services/` | 60 |
| `api/v1/` | 13 |
| `core/` | 8 |
| 其他 | 19 |

大量异常被静默吞掉，如：
- `knowledge_graph/builder.py:498` — 关联创建失败被静默忽略
- `evolution/lingminopt.py:587` — 改进计算错误被静默忽略

### 🟠 C6: 重复代码

| 模式 | 出现次数 | 文件 |
|------|---------|------|
| `to_dict()` | 13+ | 各处独立实现 |
| `_pool()` DB连接助手 | 3 | `api/v1/sysbooks.py`, `guoxue.py`, `pipeline.py` |
| `get_ai_service()` | 2 | `ai_service.py`, `ai_service_enhanced.py` |
| `get_lingminopt_framework()` | 2 | 两个 `lingminopt.py` |

### 🟠 C7: God Files（>500 行）

| 文件 | 行数 | 问题 |
|------|------|------|
| `textbook_processing/autonomous_processor.py` | 942 | 3个类+CLI+测试代码混在一起 |
| `services/evolution/lingminopt.py` | 825 | 数据类+优化器+编排器+CLI |
| `auth/jwt.py` | 796 | Token载荷+黑名单+管理器+编解码 |
| `services/audio/audio_service.py` | 785 | 上传+转写+导入+分段+SRT解析 |
| `api/v1/evolution.py` | 599 | 10+端点+独立工具函数 |

### 🟡 C8: 废弃文件

| 文件 | 说明 |
|------|------|
| `services/generation/video_generator.py.backup` | 未实现的视频生成器 |
| `services/generation/audio_generator.py.backup` | 未实现的音频生成器 |
| `auth/rbac.py.backup.20260401_114324` | 旧RBAC模块 |
| `data/textbooks/real_file.txt` | 仅含 "content" 的测试文件 |
| `data/textbooks_duplicate_backup/` | 手动备份副本 |

### 🟡 C9: 未使用变量（15处 noqa: F841）

多处变量赋值后从未使用，包括一个逻辑 Bug：

```python
# huggingface_collector.py:212 — 两个分支返回相同值
_hf_type = "models" if "models" in model.get("_id", "") else "models"
```

---

## 四、基础设施负债

### 🔴 I1: Prometheus 告警全部失效

| 问题 | 原因 |
|------|------|
| 告警规则未加载 | `prometheus.yml` 第13行 `rule_files` 被注释 |
| Alertmanager 未部署 | `docker-compose.yml` 中无该服务 |
| Node Exporter 未部署 | 5条系统指标告警永远无法触发 |
| 告警邮箱为占位符 | `admin@example.com` 等假地址 |

**20 条告警规则 = 完全无效**。

### 🟠 I2: Nginx 静态文件路由错误

| 配置 | 实际 | 问题 |
|------|------|------|
| `alias /usr/share/nginx/html/frontend-v2/` | `./frontend/frontend-v2/` | 目录不存在 |
| `alias /usr/share/nginx/html/frontend/` | `./frontend/frontend/` | 目录不存在 |

前端页面可能无法正确加载。

### 🟡 I3: Docker Compose 版本过时

- `version: "3.8"` 已被 Docker Compose V2 废弃
- BGE-M3 embedding 服务启动需要 180 秒，可能掩盖启动失败

### 🟡 I4: .env.example 配置不一致

| 项目 | .env.example | 代码实际 |
|------|-------------|---------|
| JWT 算法 | HS256 | RS256 |
| BGE_API_KEY | "已弃用" | 仍在示例文件中 |

---

## 五、测试负债

### 🔴 T1: 52% API 模块无测试

21 个 API 模块中 **11 个无直接测试**：

| 无测试模块 | 影响 |
|-----------|------|
| `documents.py` | 核心 CRUD 无覆盖 |
| `search.py` | 检索功能无覆盖 |
| `books.py` | 教材搜索无覆盖 |
| `learning.py` | 学习功能无覆盖 |
| `annotation.py` | 标注功能无覆盖 |
| `external.py` | 外部数据无覆盖 |
| `optimization.py` | 优化功能无覆盖 |
| `intelligence.py` | 情报功能无覆盖 |
| `lifecycle.py` | 生命周期无覆盖 |
| `textbook_processing.py` | 教材处理无覆盖 |
| `generation.py` | 仅框架测试 |

---

# 第三部分：盘活方案

## 第一阶段：紧急清债（1-2天）

### 🔒 安全修复（最高优先级）

| 编号 | 行动 | 具体操作 |
|------|------|---------|
| FIX-S1 | **移除 JWT 私钥** | `git rm jwt_*.pem` → 加入 `.gitignore` → 重新生成密钥对 → 通知所有协作者 |
| FIX-S2 | **清除硬编码密码** | 所有脚本改用环境变量 `os.getenv("DATABASE_URL")` 或 `from backend.config import get_config` |
| FIX-S3 | **清除敏感数据** | 删除 `data/config.json` 中的 JWT secret、`ima_cookies*.json`、`ima_page_logged_in.html` |
| FIX-S4 | **加入 .gitignore** | 添加 `*.pem`, `*.key`, `*.crt`, `data/config.json`, `data/context/`, `data/textbooks/ima_*` |

### 🧹 清理废弃文件

```bash
# 删除备份文件
rm backend/services/generation/*.backup
rm backend/auth/rbac.py.backup.*
rm -rf data/textbooks_duplicate_backup/
rm data/textbooks/real_file.txt

# 删除敏感会话数据
rm data/textbooks/ima_cookies*.json
rm data/textbooks/ima_page_logged_in.html
rm data/textbooks/network_requests.json
```

### 🩹 关键代码修复

| 编号 | 行动 | 文件 |
|------|------|------|
| FIX-C1 | 修复 `core/__init__.py` 中的 `try: pass` 导入 | `backend/core/__init__.py:17-22` |
| FIX-C2 | 移除 `auditor.py` 中的伪造安全检查，改为明确报错 | `backend/services/optimization/auditor.py` |
| FIX-C3 | 删除或合并重复的 `lingminopt.py` | 保留 `evolution/` 版本，删除 `optimization/` 版本 |

---

## 第二阶段：数据导入（3-5天）

这是**盘活资产的最关键步骤** — 系统有完善的检索架构，但缺少数据。

### 📊 导入执行顺序

```
步骤1: 导入 302 万图书编目          ← scripts/import_sys_books.py
   │
步骤2: 导入 26 万古籍数据           ← scripts/import_guji_data.py
   │
步骤3: 导入 9 册核心教材             ← backend/services/textbook_importer.py
   │
步骤4: 内容提取（sys_books 文本）     ← services/content_extraction/extractor.py
   │
步骤5: 批量生成向量嵌入              ← scripts/regenerate_embeddings.py
   │
步骤6: 构建知识图谱                  ← services/knowledge_graph/builder.py
```

### 预估数据量与时间

| 步骤 | 目标行数 | 预估耗时 | 依赖 |
|------|---------|---------|------|
| 1. sys_books 导入 | 302 万 | ~30 分钟 | PG 可用 |
| 2. 古籍导入 | 26 万 | ~60 分钟 | PG 可用 |
| 3. 教材导入 | ~3,200 章节 | ~10 分钟 | BGE 服务可用 |
| 4. 内容提取 | 数万文件 | ~数小时（I/O 密集） | 文件系统可访问 |
| 5. 向量化 | 数十万 chunks | ~数小时 | BGE-M3 服务可用 |
| 6. 知识图谱 | 数千实体/关系 | ~30 分钟 | 步骤1完成后 |

### 建立数据备份

```bash
# 为所有 SQLite 数据库建立备份
scripts/backup_sqlite.sh   # 新建脚本
# 备份到 /backup/ 或云存储
# 加入 cron 每日自动备份
```

---

## 第三阶段：代码治理（5-7天）

### 🏗️ 架构清理

| 行动 | 具体操作 |
|------|---------|
| **合并重复模块** | 删除 `services/optimization/lingminopt.py`，统一到 `evolution/` 版本 |
| **抽取公共工具** | `to_dict()` → 提取到 `common/serialization.py`；`_pool()` → 提取到 `common/db_helpers.py` |
| **修复异常处理** | 100处 `except Exception` → 替换为具体异常类型 |
| **删除实验性模块** | `services/optimization/` 整体标记为废弃或删除 |
| **修复告警系统** | 取消 `prometheus.yml` 中 `rule_files` 注释 → 部署 Alertmanager → 部署 Node Exporter |

### 📐 大文件拆分

| 文件 | 行数 | 拆分建议 |
|------|------|---------|
| `autonomous_processor.py` | 942 | 分为 `toc_extractor.py` + `text_segmenter.py` + `quality_assessor.py` |
| `lingminopt.py` | 825 | 分为 `models.py` + `optimizer.py` + `orchestrator.py` |
| `jwt.py` | 796 | 分为 `token.py` + `blacklist.py` + `manager.py` |
| `audio_service.py` | 785 | 分为 `upload.py` + `transcription.py` + `import_service.py` |

### 🧪 测试补齐

优先为以下无测试的核心模块添加测试：

| 优先级 | 模块 | 原因 |
|--------|------|------|
| P0 | `documents.py` | 核心 CRUD |
| P0 | `search.py` | 核心检索 |
| P1 | `books.py` | 教材搜索 |
| P1 | `learning.py` | 学习功能 |
| P2 | `annotation.py` | 标注功能 |
| P2 | `external.py` | 外部数据 |

---

## 第四阶段：能力升级（持续）

### 🚀 盘活后的系统价值提升

| 方向 | 当前 | 目标 | 路径 |
|------|------|------|------|
| **可检索内容** | ~3,000 条古籍 | 302万+26万+3200 ≈ **329万条** | 完成第二阶段导入 |
| **向量覆盖率** | 0% | >80% | 完成 embedding 批量生成 |
| **知识图谱** | 空 | 数千实体+关系 | 完成KG构建 |
| **告警能力** | 0 条有效 | 20 条有效 | 修复 Prometheus 配置 |
| **测试覆盖** | ~48% 模块有测试 | >80% 模块有测试 | 完成第三阶段测试 |
| **安全态势** | 密钥泄露+硬编码密码 | 零硬编码密钥 | 完成第一阶段修复 |

### 📈 资产利用率提升路线

```
当前状态:    ██████░░░░░░░░░░░░░░  30% 资产利用率
                                        ↑ 架构完整但数据空

第一阶段后:  ████████░░░░░░░░░░░░  40%  (安全清债)
第二阶段后:  ████████████████░░░░  80%  (数据导入) ← 最大收益点
第三阶段后:  ██████████████████░░  90%  (代码治理)
第四阶段后:  ████████████████████  95%+ (持续优化)
```

---

## 附录：负债汇总表

| 编号 | 等级 | 类别 | 描述 | 修复成本 |
|------|------|------|------|---------|
| S1 | 🔴 | 安全 | JWT 私钥在 Git 中 | 低 (1h) |
| S2 | 🔴 | 安全 | 16+脚本硬编码密码 | 中 (4h) |
| S3 | 🔴 | 安全 | JWT Secret 硬编码 | 低 (1h) |
| S4 | 🟠 | 安全 | Cookie/会话数据泄露 | 低 (1h) |
| D1 | 🔴 | 数据 | PG 核心表全空 | 高 (3-5天) |
| D2 | 🔴 | 数据 | 26万古籍仅导入1.1% | 中 (1天) |
| D3 | 🔴 | 数据 | SQLite 零备份 | 中 (1天) |
| D4 | 🟠 | 数据 | 数据双重存储 | 低 (评估) |
| C1 | 🔴 | 代码 | 伪造安全审计 | 低 (2h) |
| C2 | 🔴 | 代码 | 损坏的 import | 低 (30min) |
| C3 | 🟠 | 代码 | 重复 lingminopt 模块 | 中 (4h) |
| C4 | 🟠 | 代码 | TODO 未完成项 | 中 (1天) |
| C5 | 🟠 | 代码 | 100处过度捕获异常 | 高 (3天) |
| C6 | 🟠 | 代码 | 重复代码模式 | 中 (2天) |
| C7 | 🟠 | 代码 | 9个过大文件 | 高 (3天) |
| C8 | 🟡 | 代码 | 废弃文件 | 低 (1h) |
| I1 | 🔴 | 基础设施 | 告警系统全部失效 | 中 (1天) |
| I2 | 🟠 | 基础设施 | Nginx 路由错误 | 低 (2h) |
| T1 | 🔴 | 测试 | 52% API 无测试 | 高 (5天) |

**负债总计: 19 项**（🔴 严重 7 项 / 🟠 高 7 项 / 🟡 中 5 项）

---

> **核心结论**: 系统的架构资产极为丰富（混合检索、十领域路由、二级缓存、JWT认证、API网关、监控体系均为生产级实现），但**最大的资产浪费在于数据未导入** — PostgreSQL 70张表中64张为空。完成第二阶段数据导入后，系统可检索内容将从 3,000 条跃升至 329 万条，资产利用率从 30% 提升至 80%。
