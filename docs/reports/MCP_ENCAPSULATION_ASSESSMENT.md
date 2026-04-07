# MCP封装评估报告 — 灵知工具能力全面审计

> **评估日期**: 2026-04-08  
> **评估对象**: 灵知(Crush CLI Agent)的全部功能和工具  
> **评估目标**: 为灵研/灵极优/其他Agent提供可复用的MCP工具服务

---

## 一、工具能力全景 (共6层, 73项)

### 第1层: 文件系统操作 (7项)

| 工具 | 功能 | 当前状态 | 调用频次 |
|------|------|----------|----------|
| View | 读取文件(支持行号/偏移/图片渲染) | 内置 | ★★★★★ |
| Edit | 精确文本替换(单点) | 内置 | ★★★★★ |
| Multiedit | 多点文本替换(批量) | 内置 | ★★★★ |
| Write | 创建/覆盖文件 | 内置 | ★★★★ |
| LS | 目录树浏览 | 内置 | ★★★★ |
| Glob | 文件名模式匹配(ripgrep) | 内置 | ★★★★ |
| Grep | 文件内容搜索(正则/字面量) | 内置 | ★★★★★ |

### 第2层: 代码智能 (3项)

| 工具 | 功能 | 当前状态 | 调用频次 |
|------|------|----------|----------|
| LSP References | 符号引用查找(语义级) | LSP集成 | ★★★ |
| LSP Diagnostics | 代码诊断(错误/警告) | LSP集成 | ★★★★ |
| LSP Restart | LSP服务重启 | LSP集成 | ★ |

### 第3层: 终端执行 (3项)

| 工具 | 功能 | 当前状态 | 调用频次 |
|------|------|----------|----------|
| Bash (同步) | 执行命令并等待结果 | 内置 | ★★★★★ |
| Bash (后台) | 长时间运行命令 | 内置 | ★★ |
| Job管理 | job_output / job_kill | 内置 | ★ |

### 第4层: 网络能力 (5项)

| 工具 | 功能 | 当前状态 | 调用频次 |
|------|------|----------|----------|
| fetch | 原始URL内容获取 | 内置 | ★★★ |
| agentic_fetch | AI处理的URL内容提取 | 内置 | ★★★ |
| web_search | DuckDuckGo搜索 | 内置 | ★★ |
| Sourcegraph | 公共代码仓库搜索 | 内置 | ★★ |
| Agent | 子Agent委托(搜索/探索) | 内置 | ★★★★ |

### 第5层: 已有MCP服务 (13项) ✅ 已封装

| MCP服务 | 功能 | 提供方 |
|---------|------|--------|
| mcp_web-reader_webReader | URL→Markdown/HTML转换 | web-reader |
| mcp_web-search-prime_web_search_prime | 网络搜索(高级) | web-search-prime |
| mcp_zread_get_repo_structure | GitHub仓库目录结构 | zread |
| mcp_zread_read_file | GitHub文件内容读取 | zread |
| mcp_zread_search_doc | GitHub文档/Issue搜索 | zread |
| mcp_zai-mcp-server_analyze_image | 通用图像分析 | zai-mcp-server |
| mcp_zai-mcp-server_analyze_video | 视频内容分析 | zai-mcp-server |
| mcp_zai-mcp-server_analyze_data_visualization | 数据图表分析 | zai-mcp-server |
| mcp_zai-mcp-server_diagnose_error_screenshot | 错误截图诊断 | zai-mcp-server |
| mcp_zai-mcp-server_extract_text_from_screenshot | OCR文字提取 | zai-mcp-server |
| mcp_zai-mcp-server_ui_to_artifact | UI→代码/规范/描述 | zai-mcp-server |
| mcp_zai-mcp-server_ui_diff_check | UI视觉差异对比 | zai-mcp-server |
| mcp_zai-mcp-server_understand_technical_diagram | 技术图表理解 | zai-mcp-server |

### 第6层: 项目自有后端服务 (70+ API端点)

#### 6A. 知识检索类 (核心, 高价值)

| 端点 | 功能 | MCP优先级 |
|------|------|-----------|
| POST /api/v1/search | 向量/BM25/混合搜索 | **P0** |
| POST /api/v1/ask | RAG问答 | **P0** |
| GET /api/v1/categories | 分类列表 | P2 |
| GET /api/v1/stats | 统计信息 | P2 |
| POST /api/v1/reason | CoT/ReAct/GraphRAG推理 | **P1** |
| GET /api/v1/health | 健康检查 | P2 |
| GET /api/v1/health/db | 数据库健康 | P2 |

#### 6B. 文档管理类

| 端点 | 功能 | MCP优先级 |
|------|------|-----------|
| POST /api/v1/documents | 创建文档 | P1 |
| GET /api/v1/documents/{id} | 读取文档 | P1 |
| DELETE /api/v1/documents/{id} | 删除文档 | P2 |
| POST /api/v1/embeddings/update | 更新嵌入向量 | P1 |

#### 6C. 网关/路由类

| 端点 | 功能 | MCP优先级 |
|------|------|-----------|
| POST /gateway/query | 网关查询路由 | P1 |
| GET /gateway/stats | 网关统计 | P2 |
| POST /domains/{name}/query | 领域路由查询 | **P0** |
| GET /domains | 领域列表 | P2 |

#### 6D. 缓存管理类

| 端点 | 功能 | MCP优先级 |
|------|------|-----------|
| GET /api/v1/cache/stats | 缓存统计 | P2 |
| GET /api/v1/cache/metrics | 缓存指标 | P2 |
| POST /api/v1/cache/clear | 清除缓存 | P2 |

#### 6E. 进化/优化类 (灵极优相关)

| 服务模块 | 功能 | MCP优先级 |
|---------|------|-----------|
| evolution/lingminopt.py | 自优化引擎 | **P0** |
| evolution/comparison_engine.py | 多模型对比 | P1 |
| evolution/verification_agent.py | 验证Agent | P1 |
| evolution/token_monitor.py | Token监控 | P1 |
| evolution/rate_limiter.py | 速率限制 | P2 |
| optimization/lingminopt.py | 优化入口 | **P0** |
| optimization/auditor.py | 审计器 | P1 |
| optimization/error_analyzer.py | 错误分析 | P1 |
| optimization/feedback_collector.py | 反馈收集 | P1 |

#### 6F. 训练/标注类 (灵研相关)

| 服务模块 | 功能 | MCP优先级 |
|---------|------|-----------|
| annotation/annotation_manager.py | 标注管理 | P1 |
| annotation/ocr_annotator.py | OCR标注 | P1 |
| annotation/transcription_annotator.py | 语音转录标注 | P1 |
| prepare_training_data.py (脚本) | 训练数据生成 | **P0** |

#### 6G. 数据处理类

| 脚本 | 功能 | MCP优先级 |
|------|------|-----------|
| import_guji_*.py | 古籍导入(6个) | P2 |
| import_sys_books.py | 系统书籍导入 | P2 |
| rebuild_embeddings.py | 嵌入向量重建 | P1 |
| generate_guji_embeddings.py | 古籍嵌入生成 | P1 |
| tag_qigong_docs.py | 气功文档标注 | P2 |

#### 6H. 多媒体处理类

| 服务模块 | 功能 | MCP优先级 |
|---------|------|-----------|
| audio/whisper_transcriber.py | Whisper语音转录 | P1 |
| audio/funasr_transcriber.py | FunASR转录 | P1 |
| audio/sensevoice_transcriber.py | SenseVoice转录 | P1 |
| audio/asr_router.py | ASR路由 | P1 |
| content_extraction/extractor.py | 内容提取 | P2 |

---

## 二、MCP封装评估矩阵

### 评估标准

| 维度 | 权重 | 说明 |
|------|------|------|
| **必要性** | 40% | 多Agent复用需求程度(灵研+灵极优+灵犀+...) |
| **可行性** | 30% | 技术实现难度、依赖复杂度 |
| **价值** | 20% | 封装后的效率提升、能力扩展 |
| **紧迫性** | 10% | 当前工作流是否被阻塞 |

### 分级标准

- **P0 (立即做)**: 必要性≥8, 可行性≥7, 高复用价值
- **P1 (近期做)**: 必要性≥6, 可行性≥6, 明确价值
- **P2 (可做可不做)**: 必要性≥4, 锦上添花
- **P3 (不建议)**: 必要性<4 或 可行性<4

---

### P0 — 立即封装 (7项)

| # | 工具/服务 | 必要性 | 可行性 | 价值 | 紧迫性 | 理由 |
|---|----------|--------|--------|------|--------|------|
| 1 | **知识检索** (search + ask) | 9 | 9 | 9 | 9 | 所有Agent的核心需求。已有HTTP API，封装成本极低 |
| 2 | **训练数据生成** | 8 | 8 | 9 | 9 | 灵研直接依赖。脚本已存在，需包装为服务 |
| 3 | **自优化引擎** | 8 | 7 | 9 | 8 | 灵极优核心。已有Python模块，需暴露标准接口 |
| 4 | **文件读写** (view/write/edit) | 8 | 6 | 8 | 7 | Agent协作基础。需安全沙箱化 |
| 5 | **数据库查询** | 8 | 8 | 8 | 7 | 数据审计/统计的通用需求。需参数化安全 |
| 6 | **领域路由查询** | 9 | 9 | 8 | 7 | 10个领域的知识路由。已有API，封装为MCP即可 |
| 7 | **命令执行** (bash) | 7 | 5 | 8 | 8 | 自动化基础。需白名单+权限控制 |

### P1 — 近期封装 (10项)

| # | 工具/服务 | 必要性 | 可行性 | 价值 | 理由 |
|---|----------|--------|--------|------|------|
| 1 | 推理引擎 (reason) | 7 | 8 | 8 | CoT/ReAct/GraphRAG能力开放 |
| 2 | 嵌入向量管理 | 7 | 8 | 7 | 向量生成/更新/重建 |
| 3 | 文档管理 CRUD | 7 | 9 | 7 | 知识库内容管理 |
| 4 | 反馈收集 | 7 | 8 | 7 | 灵极优优化闭环需要 |
| 5 | 错误分析 | 7 | 7 | 7 | 自优化诊断能力 |
| 6 | 音频转录路由 | 6 | 7 | 7 | 多ASR引擎统一接口 |
| 7 | OCR标注 | 6 | 7 | 7 | 灵研微调数据标注 |
| 8 | 内容提取 | 6 | 7 | 7 | 文本/书籍内容提取 |
| 9 | 代码搜索 (sourcegraph) | 6 | 8 | 6 | 开源代码参考 |
| 10 | 多模型对比 | 6 | 6 | 7 | 灵极优对比评估 |

### P2 — 可选封装 (8项)

| # | 工具/服务 | 理由 |
|---|----------|------|
| 1 | 缓存管理 | 运维向，非Agent核心 |
| 2 | 监控指标 | Prometheus已有，重复 |
| 3 | 健康检查 | 简单HTTP调用即可 |
| 4 | 数据导入(6脚本) | 一次性操作，不需常驻 |
| 5 | 文档标注 | 频次低 |
| 6 | 知识图谱 | 尚在早期阶段 |
| 7 | 课程/PPT生成 | 低频场景 |
| 8 | Git操作 | Bash封装即可 |

### P3 — 不建议封装

| 类别 | 理由 |
|------|------|
| 文件格式转换 (format_code.sh) | 开发工具链，非Agent需求 |
| 部署脚本 (deploy.sh等) | DevOps人工操作 |
| 磁盘清理脚本 | 系统运维 |
| 安全检查脚本 | CI/CD流水线 |

---

## 三、已有MCP工具复用评估

### 13项已有MCP工具的利用率

| MCP工具 | 本项目使用频率 | 对灵研/灵极优价值 | 建议 |
|---------|---------------|-------------------|------|
| web-reader | ★★ | 低(离线知识库为主) | 保留 |
| web-search-prime | ★★ | 中(资料搜集) | 保留 |
| zread (3项) | ★ | 中(开源参考) | 保留 |
| analyze_image | ★ | 高(OCR/文档分析) | **推广给灵研** |
| analyze_video | ★ | 中(音视频处理) | 保留 |
| data_visualization | ★ | 高(分析报告) | **推广给灵极优** |
| error_screenshot | ★★ | 中(调试) | 保留 |
| extract_text_screenshot | ★ | 高(OCR) | **推广给灵研** |
| ui_to_artifact | ★ | 低(前端不活跃) | 保留 |
| ui_diff_check | ★ | 低 | 可移除 |
| technical_diagram | ★ | 中(架构文档) | 保留 |

**发现**: zai-mcp-server的视觉能力(图像分析、OCR、数据可视化)对灵研和灵极优价值很高，但当前利用率低。应优先推广现有MCP工具的使用。

---

## 四、实施方案

### 方案A: FastAPI MCP Proxy (推荐 ⭐)

将现有FastAPI端点直接包装为MCP Server，无需重写业务逻辑。

```
┌──────────────┐     MCP Protocol      ┌──────────────────┐
│  灵研/灵极优  │ ◄──────────────────► │ MCP Server (新)   │
│  (LLM Agent) │                       │  ├─ tools:        │
└──────────────┘                       │  │  knowledge_search│
                                       │  │  ask_question    │
┌──────────────┐                       │  │  generate_data   │
│    灵知       │ ◄──── HTTP API ────► │  │  optimize        │
│  (Crush CLI) │                       │  │  domain_query    │
└──────────────┘                       │  └─ http_proxy →   │
                                       │     FastAPI :8000  │
                                       └──────────────────┘
```

**优点**: 复用现有70+API端点，零侵入，FastAPI→MCP映射直接
**缺点**: 需要一个轻量MCP Server进程

### 方案B: Python SDK直接封装

用 `mcp` Python SDK 直接在backend内注册工具。

**优点**: 更紧密集成，可直接调用Python函数
**缺点**: 需修改backend代码，与现有HTTP API重复

### 方案C: 混合方案 (实际推荐)

- **外部MCP服务**(zai-mcp-server等): 保持现有
- **新建1个MCP Server**: 封装P0的7项工具，Proxy到FastAPI
- **灵研/灵极优**: 通过MCP标准协议调用

### 工作量估算

| 阶段 | 工作项 | 工时 | 负责 |
|------|--------|------|------|
| **Phase 1** | MCP Server脚手架 + 知识检索(search/ask) | 2天 | 灵知 |
| **Phase 2** | 训练数据生成 + 领域路由 + DB查询 | 1天 | 灵知 |
| **Phase 3** | 自优化引擎 + 反馈收集 | 2天 | 灵极优 |
| **Phase 4** | 文件操作沙箱 + 命令执行白名单 | 2天 | 灵知+灵研 |
| **Phase 5** | 音频/OCR/推理等P1工具 | 3天 | 灵研 |
| **总计** | | **~10天** | |

---

## 五、结论

### 核心发现

1. **已有13个MCP工具**但利用率偏低，特别是视觉分析类对灵研价值很高
2. **70+个FastAPI端点**已有现成接口，MCP封装成本极低(主要是配置工作)
3. **真正需要新建的MCP工具只有3个**: 训练数据生成、自优化引擎、文件操作沙箱
4. **最大收益点**: 知识检索(search/ask)→MCP封装后，所有Agent都能直接用知识库

### 优先行动项

1. ✅ 推广现有zai-mcp-server视觉工具给灵研/灵极优
2. 🔨 Phase 1: 建MCP Server + 知识检索封装(2天)
3. 🔨 Phase 2: 训练数据 + 自优化接口(3天)
4. 📋 Phase 3-5: 按需推进P1工具

### 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| MCP Server进程管理 | 低 | Docker sidecar |
| 认证透传(JWT) | 中 | MCP Server共享JWT密钥 |
| 工具权限控制 | 中 | RBAC映射到MCP tool permissions |
| 并发性能 | 低 | 现有FastAPI已处理 |
