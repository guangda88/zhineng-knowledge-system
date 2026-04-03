# 技术债务清单

> 审计日期: 2026-04-01 | 版本: v1.3.0-dev | pytest: 424/442 (18 pre-existing) | e2e: 12/12 ✅
>
> **最后更新**: 2026-03-31 - 新增情报系统(Intelligence System): GitHub/npm/HuggingFace趋势采集, 相关性评分, API端点

---

## P0 — 安全漏洞 (立即修复)

| # | 问题 | 文件 | 行 | 说明 | 状态 |
|---|------|------|----|------|------|
| S1 | ~~源码中硬编码 API 密钥~~ | `backend/api/v1/external.py` | ~~30-42~~ | ~~- `"lingzhi_dev_key_2026"`, `"lingzhi_prod_key_2026"` 写在源码里，无轮换机制~~ | ✅ 已修复 (当前代码使用环境变量) |
| S2 | ~~JWT 密钥弱默认值~~ | `backend/core/security.py` | ~~18~~ | ~~`SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-min-32-characters-long")` — 生产环境若未设环境变量可被伪造~~ | ✅ 已修复 (要求SECRET_KEY环境变量，开发模式使用随机密钥) |
| S3 | ~~源码中硬编码数据库凭据~~ | `backend/services/textbook_importer.py` | ~~288~~ | ~~`"postgresql://zhineng:zhineng123@localhost:5436/zhineng_kb"`~~ | ✅ 已修复 (使用DATABASE_URL环境变量) |
| S4 | ~~docker-compose 弱密码回退~~ | `docker-compose.yml` | ~~9, 37, 183~~ | ~~- `${POSTGRES_PASSWORD:-zhineng123}`, `${REDIS_PASSWORD:-redis123}`, `${GRAFANA_PASSWORD:-admin123}`~~ | ✅ 已修复 (2026-04-01 - 移除所有弱密码默认值) |
| S5 | ~~命令注入风险~~ | `backend/services/learning/innovation_manager.py` | ~~103~~ | ~~`subprocess.run(f"... git checkout -b {branch_name}", shell=True)` — branch_name 未转义~~ | ✅ 已修复 (2026-04-01) |
| S6 | ~~缺少 `.dockerignore`~~ | 项目根目录 | — | ~~`.git`, `__pycache__`, `venv`, `backups/` 全部打入 Docker 镜像~~ | ✅ 已存在 (59行，良好覆盖) |

**修复详情**:
- **S1 (2026-04-01)**: 代码审查确认 - 当前实现已使用环境变量 `EXTERNAL_API_KEYS`，开发模式有明确的"仅用于测试"警告
- **S2 (2026-04-01)**: 代码审查确认 - 生产环境要求 `SECRET_KEY` 环境变量（未设置则抛出异常），开发模式生成随机密钥
- **S3 (2026-04-01)**: 代码审查确认 - 使用 `DATABASE_URL` 环境变量，未设置时抛出错误
- **S4 (2026-04-01)**:
  - 移除 docker-compose.yml 中所有弱密码默认值（7处）
  - 修改: `:-zhineng123`, `:-redis123`, `:-admin123` → 要求环境变量
  - 更新 `.env.example`，添加安全警告和密码强度要求
  - 影响服务: postgres, redis, api, grafana, redis-exporter, postgres-exporter
- **S5 (2026-04-01)**:
  - 添加 `_validate_command()` 方法，检测危险 shell 元字符 (`; | & $ ` ( ) < > \n`)
  - 所有 `subprocess.run(shell=True)` 改为 list 格式或添加验证
  - 新增 11 个安全测试 (`tests/test_innovation_manager.py`)
  - 修复位置: lines 103, 142, 223, 230, 237, 244
- **S6 (2026-04-01)**: 代码审查确认 - `.dockerignore` 已存在且配置良好

---

## P1 — 架构缺陷 (短期修复)

### A. 导入路径不一致 (根因: `sys.path` 操控)

`backend/main.py:15` 执行 `sys.path.insert(0, backend_dir)`，导致同一模块可用两种路径导入。SQLAlchemy mapper 对同一类注册两次。

| 导入风格 | 文件数 | 示例 |
|----------|--------|------|
| `from backend.xxx` (绝对) | 33 | `from backend.core.database import Base` |
| `from xxx` (裸) | 11 | `from cache.decorators import cached` |
| **同文件混用** | 4 | `main.py`, `search.py`, `health.py`, `gateway.py` |

**影响**: `extend_existing=True` 就是为了绕过此问题而加的 workaround (`models/book.py:17`, `models/source.py:14`)。

### B. TestClient + asyncpg 事件循环冲突

| 文件 | 测试失败数 | 原因 |
|------|-----------|------|
| `tests/test_api.py` | 9/15 | `TestClient` 内部创建同步事件循环，与 `asyncpg.create_pool` 冲突 |
| `tests/test_main.py` | 5/16 | 同上 |

**总计 14/397 测试因此失败**。根因: Starlette `TestClient` 在 sync 线程运行 async endpoint，asyncpg pool 无法跨事件循环。

### C. ~~全文搜索索引语言不匹配~~ ✅ 已修复

| 组件 | 语言配置 | 文件 |
|------|---------|------|
| GIN 索引 | `'english'` → `'chinese'` ✅ | `scripts/migrations/add_indexes.sql:11` |
| 查询 | `'chinese'` | `backend/services/hybrid_retrieval.py:118` |

**影响**: ~~GIN 索引不会被使用，102,923 行全表扫描。~~ ✅ 已修复 - 索引重建为 `'chinese'` 配置，与查询匹配。

**修复**: `scripts/migrations/add_indexes.sql` 添加 `DROP INDEX IF EXISTS` 后重建为 `to_tsvector('chinese', content)`。

### D. 缺失数据库表

`textbook_nodes` 和 `textbook_blocks` 表在 `textbook_importer.py` 中引用，但无任何 `.sql` schema 文件定义。

---

## P2 — 测试质量 (中期改善)

### A. 宽松断言 (掩盖真实失败)

20 处断言接受 `[200, 500]` 或更多状态码，服务崩溃 500 也能通过测试:

| 文件 | 问题断言数 | 最差示例 |
|------|-----------|---------|
| `tests/test_api.py` | 9 | `assert response.status_code in [200, 500]` |
| `tests/test_main.py` | 11 | `assert response.status_code in [400, 422, 200, 500, 503]` |

### B. 空测试 / 存根测试

| 文件 | 行 | 问题 |
|------|----|------|
| `tests/test_text_annotation_service.py` | 241-251 | `test_end_to_end_annotation_workflow`: 只有 `pass` |
| `tests/test_enhanced_vector_service.py` | 122-126 | `test_auto_fallback_to_local`: 只有 `pass`，注释"暂时跳过" |
| `tests/test_api.py` | 11-13 | `class TestAPI` 重复定义，第一个为空 |

### C. 非 pytest 测试文件

| 文件 | 说明 |
|------|------|
| `tests/test_deepseek_integration.py` | 使用 `print()` + `sys.exit()`，pytest 无法发现 |
| `tests/test_rate_limit.py` | 使用 `aiohttp` 脚本，非 pytest 格式 |

### D. 测试覆盖率阈值过低

`pytest.ini` 设置 `fail_under = 60`，允许 40% 代码未测试。目标应提升至 80%。

### E. 全局状态污染

`tests/test_api_key_protection.py:35-56` 直接修改 `backend.config._config = None`，测试顺序依赖。

---

## P3 — 未完成功能 (中期)

### A. ~~运行时崩溃 Bug~~ ✅ 已修复 (4/4)

| 文件 | 行 | 问题 | 状态 |
|------|----|------|------|
| `services/evolution/comparison_engine.py` | 510 | `professionalism` 变量未定义，应为 `professionalism_score` | ✅ 已修复 |
| `services/generation/course_generator.py` | 98 | `from services.retrieval.vector import VectorRetrievalService` 不存在 | ✅ 已修复 → `get_db_pool()` + asyncpg |
| `services/generation/ppt_generator.py` | 98, 300 | 同上（2处） | ✅ 已修复 |
| `services/generation/report_generator.py` | 111 | 同上 | ✅ 已修复 |

### B. ~~未激活路由~~ ✅ 已修复 (2/2)

| 文件 | 路由 | 端点数 | 状态 |
|------|------|--------|------|
| `api/v1/evolution.py` | `/api/v1/evolution/*` | 5 | ✅ 已注册到 `api/v1/__init__.py` |
| `api/v2/authenticated.py` | `/api/v2/auth/*` | 6 | ✅ 已注册到 `api/v2/__init__.py` |

### C. ~~NotImplementedError 存根~~ ✅ 已修复 (4/9, 5项保留)

| 文件 | 行 | 功能 | 状态 |
|------|----|------|------|
| `services/annotation/ocr_annotator.py` | 142 | OCR 识别 | ✅ 已实现（多引擎: pdfplumber/tesseract/easyocr） |
| `services/annotation/transcription_annotator.py` | 169 | 转写标注 | ✅ 已实现（委托给 ASRRouter/Whisper） |
| `services/textbook_importer.py` | 272 | BGE 嵌入生成 | ✅ 已实现（VectorRetriever.embed_batch + 远程服务备用） |
| `services/knowledge_base/processor.py` | 296 | 嵌入生成 | ✅ 已实现（VectorRetriever.embed_batch + 远程服务备用） |
| `services/generation/video_generator.py` | 89 | 视频生成 | ❌ 保留 |
| `services/generation/generators.py` | 88 | TTS 音频生成 | ✅ 已实现（edge-tts集成） |
| `services/annotation/annotation_manager.py` | 130 | 生产力指标 | ❌ 保留 |
| `services/generation/data_analyzer.py` | 22 | 知识图谱分析 | ✅ 已实现（DB统计近似） |
| `gateway/rate_limiter.py` | 86 | 分布式限流 | ❌ 保留 |

### D. 返回硬编码假数据的方法 (3 处)

| 文件 | 行 | 方法 | 假数据 |
|------|----|------|--------|
| `services/generation/data_analyzer.py` | 34-50 | `analyze_learning_progress()` | ✅ 已替换为DB查询 |
| `services/generation/data_analyzer.py` | 56-88 | `analyze_content_distribution()` | ✅ 已替换为DB查询 |
| `services/generation/data_analyzer.py` | 94-112 | `analyze_user_behavior()` | ✅ 已替换为DB查询 |
| `api/v1/external.py` | 275-282 | `/analyze` 端点 | ✅ 已实现（jieba关键词/摘要/情感+DB分类） |
| `api/v1/generation.py` | 379-385 | 生成端点 | ✅ 已实现（generation_tasks表追踪） |

---


### E. ✅ P0-P3 功能完善 (Session 3: 19项已修复)

| # | 文件 | 修复内容 | 状态 |
|---|------|---------|------|
| E1 | `api/v2/authenticated.py:89` | 登录逻辑反转bug — `if not (correct)` → `if (correct)` | ✅ |
| E2 | `api/v1/evolution.py:253` | `GET /comparison/{id}` 查询 `ai_comparison_log` | ✅ |
| E3 | `api/v1/evolution.py:275` | `GET /dashboard` 查询视图+统计表 | ✅ |
| E4 | `api/v1/evolution.py:167` | `POST /track-behavior` INSERT到 `user_focus_log` | ✅ |
| E5 | `api/v1/evolution.py:211` | `POST /submit-feedback` UPDATE `ai_comparison_log` | ✅ |
| E6 | `api/v1/external.py:284` | keywords分析 — jieba TF-IDF提取 | ✅ |
| E7 | `api/v1/external.py:286` | summary分析 — 关键句抽取 | ✅ |
| E8 | `api/v1/external.py:285` | sentiment分析 — 正负面词匹配 | ✅ |
| E9 | `api/v1/external.py:287` | category分析 — DB文档分类匹配 | ✅ |
| E10 | `services/generation/data_analyzer.py` | 4个方法全部替换为真实DB查询 | ✅ |
| E11 | `api/v2/authenticated.py:138` | `POST /documents` INSERT到documents表 | ✅ |
| E12 | `api/v2/authenticated.py:152` | `GET /documents/{id}` SELECT从documents表 | ✅ |
| E13 | `scripts/migrations/add_generation_tasks.sql` | 新建 `generation_tasks` 迁移表 | ✅ |
| E14 | `api/v1/generation.py:371` | `GET /status/{task_id}` 查询任务状态 | ✅ |
| E15 | `api/v1/generation.py:421` | `GET /outputs` 查询完成列表 | ✅ |
| E16 | `api/v1/generation.py:85-330` | 5个后台任务添加DB追踪 | ✅ |
| E17 | `services/generation/generators.py:88` | TTS — edge-tts集成 | ✅ |
| E18 | `services/generation/base.py:23` | OutputFormat 添加 MP3/WAV/MP4 | ✅ |

---

## P4 — 代码质量 (持续改善)

### A. ~~已弃用 API~~ ✅ 已修复 (6/6)

`asyncio.get_event_loop()` 在 Python 3.10+ 已弃用:

| 文件 | 行 | 状态 |
|------|----|------|
| `services/enhanced_vector_service.py` | 224 | ✅ → `get_running_loop()` |
| `cache/manager.py` | 444 | ✅ → `get_running_loop()` |
| `core/urgency_guard.py` | 88, 98 | ✅ → `get_running_loop()` |
| `core/services.py` | 332 | ✅ → `get_running_loop()` |
| `cache/decorators.py` | 466 | ✅ → `get_running_loop()` |
| `services/retrieval/vector.py` | 33 | ✅ → `get_running_loop()` |

### B. 异步上下文中的阻塞 I/O (3 处)

| 文件 | 行 | 阻塞调用 |
|------|----|---------|
| `core/urgency_guard.py` | 145 | `subprocess.run(["curl", ...])` |
| `services/learning/innovation_manager.py` | 103 | `subprocess.run(..., shell=True)` |
| `textbook_processing/workflow.py` | 356 | `subprocess.run(["python3", ...], timeout=300)` |

**修复**: 替换为 `asyncio.create_subprocess_exec()`

### C. ~~静默吞异常~~ ✅ 已修复 (4/7, 其余 3 处为误报)

| 文件 | 行 | 状态 |
|------|----|------|
| `auth/middleware.py` | 428-429 | ✅ 添加 `logger.debug()` |
| `core/dependency_injection.py` | 221-222 | ✅ 添加 `logger.debug()` |
| `textbook_processing/deep_toc_parser.py` | 326-328 | ✅ 添加 `logger.debug()` |
| `services/compression.py` | 431-433 | ✅ 添加 `logger.warning()` |
| `services/audio/asr_router.py` | 103-104 | 误报 — except 块内有实际代码 |
| `core/database.py` | 56-58 | 误报 — except 块内有实际代码 |
| `core/validators.py` | 330-331 | 误报 — except 块内有实际代码 |

### D. ~~未使用导入~~ ✅ 已修复 (2/2)

| 文件 | 行 | 状态 |
|------|----|------|
| `services/hybrid_retrieval.py` | 21 | ✅ 已移除 `import numpy as np` |
| `services/audio/cohere_transcriber.py` | 13 | ✅ 已移除 `import numpy as np` |

### E. ~~死代码~~ ✅ 已修复 (2/2)

| 文件 | 行 | 状态 |
|------|----|------|
| `services/textbook_importer.py` | 277-281 | ✅ 已移除 `raise NotImplementedError` 之后的不可达代码 |
| `services/retrieval/vector.py` | 65 | ✅ 已移除未使用的 `embedding_api_url` 参数 |

### F. 缺少错误处理的 API 端点

以下端点无 try/except，任何异常直接返回 500:

| 路由文件 | 无保护的端点数 |
|----------|--------------|
| `api/v1/search.py` | 7 |
| `api/v1/documents.py` | 3 |
| `api/v1/gateway.py` | 5 |
| `api/v1/reasoning.py` | 4 |
| `api/v1/learning.py` | 3 |
| `api/v1/audio.py` | 7 |
| `api/v1/lifecycle.py` | 12 (全部) |
| `api/v1/health.py` | 3 |

**总计 44 个端点缺少错误处理**。

---

## P5 — Docker / 部署 (运维)

| # | 问题 | 位置 | 说明 |
|---|------|------|------|
| D1 | API 服务无 healthcheck | `docker-compose.yml` | postgres/redis 有 healthcheck，api 没有 |
| D2 | Dockerfile 带 `--reload` | `backend/Dockerfile:32` | 生产环境不应开启热重载 |
| D3 | 无多阶段构建 | `backend/Dockerfile` | `gcc` 残留在生产镜像 |
| D4 | Prometheus/Grafana 用 `:latest` | `docker-compose.yml:152,179` | 版本漂移风险 |
| D5 | Redis exporter 无密码 | `docker-compose.yml:209` | `REDIS_ADDR: redis://redis:6379` 缺密码 |
| D6 | 镜像源码挂载 | `docker-compose.yml:109` | `./backend:/app/backend` 仅适用于开发 |
| D7 | Prometheus 手写格式 | `monitoring/prometheus.py` | 未使用 `prometheus_client` 库，格式不兼容标准采集 |

---

## P6 — 性能

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| P1 | BM25 启动加载 55s | `services/retrieval/bm25.py` | 102,923 文档全量加载到内存，启动慢 |
| P2 | FTS 索引不命中 | `scripts/migrations/add_indexes.sql` | ~~`english` 索引对 `chinese` 查询无效，全表扫描~~ ✅ 已修复 |
| P3 | `/metrics` 404 | `monitoring/prometheus.py` | 未注册到主路由，Prometheus 无法采集 |

---

## 统计总览

| 优先级 | 类别 | 总数 | 已修复 | 状态 |
|--------|------|------|--------|------|
| P0 | 安全漏洞 | 6 | 6 | ✅ 全部完成 |
| P1 | 架构缺陷 | 4 | 1 | P1-C 已修复, P1-A/B/D 延期 |
| P2 | 测试质量 | 5 | 0 | 延期 |
| P3 | 未完成功能 | 29 | 26 | ✅ P3-A/B/C/D/E 已修复, 5项保留 |
| P4 | 代码质量 | ~60 | 14 | P4-A/C/D/E 已修复, P4-B/F 延期 |
| P5 | Docker/部署 | 7 | 0 | 延期 |
| P6 | 性能 | 3 | 1 | P6-P2(FTS) 已修复 |
| P7 | 情报系统 | 1 | 1 | ✅ 全新功能 |
| **合计** | | **~114 + 情报系统** | **48** | |

---

## 建议修复顺序

1. **P0 安全** ✅ — 移除硬编码密钥/凭据，添加 `.dockerignore`，修复命令注入
2. **P1-A 导入路径** — 统一为 `from backend.xxx`，移除 `sys.path` hack 和 `extend_existing` (延期: 44文件, 风险大)
3. **P1-B 测试框架** — `test_api.py` / `test_main.py` 改用 `httpx.AsyncClient` 或 mock DB pool (延期: 需要大规模重写)
4. **P1-C FTS 索引** ✅ — 重建 GIN 索引为 `'chinese'` 配置
5. **P4-A 弃用 API** ✅ — 全局替换 `asyncio.get_event_loop()` → `asyncio.get_running_loop()`
6. **P4-C 静默异常** ✅ — 4处 `except...pass` 添加日志记录 (3处误报)
7. **P4-D 未使用导入** ✅ — 移除 2 处 `import numpy as np`
8. **P4-E 死代码** ✅ — 移除 2 处不可达代码/未使用参数
9. **P3 运行时 bug + 路由激活 + OCR/ASR引擎** ✅ — 4个导入路径/变量名崩溃修复, 2个路由激活, 4个NotImplementedError实现
10. **P4-F 错误处理** — 为 44 个端点添加统一错误处理（建议用 FastAPI exception handler）(延期)
11. **P3 功能完善** ✅ — 登录bug修复, 进化系统接线(4端点), 文本分析(jieba), 数据分析器(DB查询), 文档CRUD, 生成任务追踪, TTS(edge-tts)
12. **P7 情报系统** ✅ — GitHub/npm/HuggingFace趋势采集, 相关性评分, 9个API端点, 2表+2视图
