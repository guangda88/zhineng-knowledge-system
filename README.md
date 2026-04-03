# 灵知系统 (Lingzhi System)

<div align="center">

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v1.3.0--dev-orange.svg)](https://github.com/guangda88/zhineng-knowledge-system)

**集科学研究、理论探索、实践指导于一体的智能生命状态提升系统**

通过先进技术，帮助每个人将传统智慧转化为日常实践，真正提升生命状态

核心理念：知行合一，生命改变

[快速开始](#快速开始) • [文档](docs/) • [API 文档](docs/API.md) • [更新日志](CHANGELOG.md)

</div>

---

## 项目简介

灵知系统是一个集**科学研究、理论探索、实践指导**于一体的智能知识系统，专注于帮助用户将传统智慧转化为日常实践，真正提升生命状态。

系统以**智能气功**为核心，融合**儒、释、道、医、武、哲、科、气、心理**九大类别，采用先进的RAG（检索增强生成）技术，提供完整的知识服务。

### 核心特性

| 特性 | 说明 | 为生命服务 |
|------|------|-----------|
| **向量检索** | 基于 pgvector 的语义搜索 | 用户3秒找到需要的知识 |
| **混合检索** | 向量 + BM25 双路召回 | 全面找到理论与实践 |
| **完整回答** | 理论 + 科学 + 实践 | 用户获得完整的指导 |
| **个性化计划** | 从2天体验到5年规划 | 尊重用户意愿，灵活适配 |
| **领域驱动** | 儒释道医武哲科气心理九大类别 | 完整的知识体系 |
| **认证授权** | JWT + RBAC 权限控制 | 保护用户隐私数据 |
| **标注系统** | OCR/语音转写精度提升 | 确保用户获得准确内容 |

---

## 系统架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Web UI    │────▶│  FastAPI    │────▶│ PostgreSQL  │
│   (Nginx)   │     │   Backend   │     │  + pgvector │
│  Port 8008  │     │  Port 8001  │     │  Port 5436  │
└─────────────┘     └─────────────┘     └─────────────┘
                          │                    │
                          ▼                    ▼
                   ┌─────────────┐     ┌─────────────┐
                   │    Redis    │     │  DeepSeek   │
                   │   Cache     │     │     API     │
                   │ Port 6381   │     │             │
                   └─────────────┘     └─────────────┘
```

---

## 技术栈

| 类别 | 技术 |
|------|------|
| **后端** | Python 3.12, FastAPI, AsyncPG |
| **数据库** | PostgreSQL 16, pgvector |
| **缓存** | Redis 7 |
| **前端** | HTML5, CSS3, Vanilla JavaScript |
| **容器** | Docker, Docker Compose |
| **监控** | Prometheus, Grafana |

---

## 快速开始

### 前置要求

- Docker 24.0+
- Docker Compose 2.20+

### 一键启动

```bash
# 克隆项目
git clone https://github.com/guangda88/zhineng-knowledge-system.git
cd zhineng-knowledge-system

# 启动服务
docker-compose up -d

# 查看状态
docker-compose ps
```

### 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端界面 | http://localhost:8008 | Web UI |
| API 服务 | http://localhost:8001 | API 端点 |
| API 文档 | http://localhost:8001/docs | Swagger UI |
| Prometheus | http://localhost:9090 | 监控指标 |
| Grafana | http://localhost:3000 | 可视化面板 |

---

## 功能说明

### 1. 文档管理

- 创建、编辑、删除文档
- 支持分类：气功、中医、儒家
- 全文搜索和向量搜索

### 2. 智能检索

- **语义搜索**：基于向量嵌入的相似度搜索
- **关键词搜索**：BM25 算法精确匹配
- **混合搜索**：双路召回 + RRF 融合

### 3. 智能问答

- **CoT 推理**：链式思考，逐步推理
- **ReAct 推理**：推理 + 行动交替
- **GraphRAG**：基于知识图谱的推理
- **自动路由**：根据问题自动选择领域

### 4. 领域系统

| 领域 | 特性 |
|------|------|
| **气功** | 功法分类、原理说明、练习指导 |
| **中医** | 理论基础、诊断方法、治疗方案 |
| **儒家** | 经典解读、思想体系、实践应用 |
| **通用** | 通用知识、跨领域问答 |

---

## API 示例

### 搜索文档

```bash
curl "http://localhost:8001/api/v1/search?q=太极拳&limit=5"
```

### 智能问答

```bash
curl -X POST "http://localhost:8001/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "太极拳的基本要领是什么？",
    "category": "气功"
  }'
```

### 领域查询

```bash
curl -X POST "http://localhost:8001/api/v1/domains/qigong/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是站桩？"}'
```

---

## 环境配置

### 必需环境变量

```bash
# 数据库连接
DATABASE_URL=postgresql://zhineng:zhineng123@postgres:5432/zhineng_kb

# Redis 连接
REDIS_URL=redis://:redis123@redis:6379/0

# AI API (可选)
DEEPSEEK_API_KEY=your_api_key_here
```

### 可选环境变量

```bash
# 运行环境 (development/production)
ENVIRONMENT=development

# CORS 允许来源
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8008

# 日志级别
LOG_LEVEL=INFO
```

---

## 安全特性 (v1.1.0)

| 安全项 | 状态 |
|--------|------|
| CORS 配置加固 | ✅ 生产环境强制验证 |
| 安全响应头 | ✅ CSP, HSTS, X-Frame-Options |
| JWT 密钥验证 | ✅ 生产环境强制要求 |
| SQL 注入防护 | ✅ 参数化查询 |
| XSS 防护 | ✅ 输入验证 + 转义 |

---

## 开发指南

### 项目结构

```
zhineng-knowledge-system/
├── backend/                    # 后端服务
│   ├── main.py                # FastAPI 主入口 (App Factory)
│   ├── config/                # Pydantic Settings 配置包
│   │   ├── __init__.py        # Config 单例 (BaseConfig+DB+Redis+Security+LingZhi)
│   │   ├── base.py            # 基础配置 (环境、API、BGE、DeepSeek)
│   │   ├── database.py        # 数据库配置
│   │   ├── redis.py           # Redis 配置
│   │   ├── security.py        # 安全配置
│   │   └── lingzhi.py         # 灵知遗留配置
│   ├── models.py              # Pydantic 请求/响应模型
│   ├── api/v1/                # v1 API 路由
│   ├── api/v2/                # v2 API 路由 (复用 v1 router)
│   ├── core/                  # 应用基础设施
│   │   ├── lifespan.py        # FastAPI 生命周期管理
│   │   ├── database.py        # DB 连接池管理
│   │   ├── services.py        # DatabaseService, CacheService 等
│   │   ├── service_manager.py # 服务注册/编排
│   │   └── dependency_injection.py
│   ├── services/              # 业务服务
│   │   ├── retrieval/         # Vector/BM25/Hybrid 检索
│   │   ├── reasoning/         # CoT/ReAct/GraphRAG 推理
│   │   ├── rag/               # RAG 编排
│   │   └── knowledge_base/    # 知识库处理
│   ├── domains/               # 领域处理器 (气功/中医/儒家/通用)
│   ├── auth/                  # JWT RS256 认证 + RBAC
│   ├── gateway/               # API 网关 (限流/熔断/路由)
│   ├── cache/                 # L1 内存 + L2 Redis 两级缓存
│   ├── monitoring/            # Prometheus/Grafana 监控
│   ├── common/                # 共享工具 (db_helpers, singleton)
│   └── middleware/             # HTTP 中间件
├── frontend/                  # 静态前端 (HTML/CSS/JS, Nginx 托管)
├── tests/                     # 测试套件 (pytest, 232 用例)
├── docs/                      # 项目文档
├── scripts/                   # 运维脚本
├── nginx/                     # Nginx 反向代理配置
├── monitoring/                # Prometheus + Grafana 配置
├── docker-compose.yml         # 9 个服务编排
├── init.sql                   # 数据库 Schema
├── DEVELOPMENT_RULES.md       # 开发规范 v2.0.0
└── ENGINEERING_ALIGNMENT.md   # 工程对齐文档
```

### 分支策略

```
main (生产分支，稳定版本)
  ↑
develop (开发分支，集成测试)
  ↑
feature/xxx (功能分支)
fix/xxx (修复分支)
```

- **main**: 生产环境，保持稳定
- **develop**: 开发集成，接受feature/fix分支PR
- **feature/***: 新功能开发
- **fix/***: Bug修复

详见：[分支策略文档](.github/BRANCH_STRATEGY.md) | [分支命名规范](.github/FEATURE_BRANCH_NAMING.md)

### 开发流程

1. 从 `develop` 创建功能分支
2. 开发并遵循开发规范
3. 运行测试：`pytest tests/ -v`
4. 提交代码：遵循 Conventional Commits
5. PR回 `develop` 分支
6. 测试通过后合并到 `develop`

详见：[开发规则文档](DEVELOPMENT_RULES.md)

### 开发者环境设置

#### 快速安装

```bash
# 运行自动安装脚本（推荐）
bash setup-dev-env.sh

# 或使用脚本单独安装钩子
bash scripts/install_hooks.sh
```

#### 手动安装

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装开发依赖
pip install black isort flake8 bandit mypy pre-commit

# 安装预提交钩子
pre-commit install
```

#### 预提交钩子

项目配置了以下自动化检查：

| 类别 | 钩子 | 功能 | 自动修复 |
|------|------|------|----------|
| **格式化** | black | 代码格式化 | ✅ |
| | isort | import 排序 | ✅ |
| | pretty-format-yaml | YAML 格式化 | ✅ |
| **规范检查** | flake8 | 代码规范检查 | ❌ |
| | trailing-whitespace | 清理尾随空格 | ✅ |
| | end-of-file-fixer | 文件换行符结尾 | ✅ |
| **语法检查** | check-yaml | YAML 语法检查 | ❌ |
| | check-toml | TOML 语法检查 | ❌ |
| | check-json | JSON 语法检查 | ❌ |
| **安全检查** | detect-private-key | 检测私钥泄露 | ❌ |
| | bandit | 安全漏洞检查 | ❌ |
| | debug-statements | 检查调试语句 | ❌ |
| **类型检查** | mypy | 类型检查 | ❌ |
| **其他** | check-added-large-files | 检查大文件 | ❌ |
| | check-merge-conflict | 检查合并冲突 | ❌ |

#### 常用命令

```bash
# === Pre-commit 钩子 ===
# 手动运行所有钩子
pre-commit run --all-files

# 运行特定钩子
pre-commit run black --all-files

# 跳过钩子提交（不推荐）
git commit --no-verify -m "message"

# 更新钩子版本
pre-commit autoupdate

# 查看钩子状态
pre-commit run --show-diff-on-failure

# === 代码质量脚本 ===
# 检查代码质量
bash scripts/check_code.sh

# 自动格式化代码
bash scripts/format_code.sh

# 仅检查不修改
bash scripts/format_code.sh -c

# 检查特定目录
bash scripts/check_code.sh backend/

# === 环境检查 ===
# 检查开发环境
bash setup-dev-env.sh -c

# === 钩子管理 ===
# 更新钩子
bash scripts/install_hooks.sh -u

# 安装并运行钩子
bash scripts/install_hooks.sh -r
```

#### 配置文件

| 文件 | 用途 |
|------|------|
| `.pre-commit-config.yaml` | Pre-commit 钩子配置 |
| `.flake8` | Flake8 代码规范配置 |
| `pyproject.toml` | Black、isort、mypy、bandit 配置 |
| `pytest.ini` | Pytest 测试配置 |

---

## 部署指南

### Docker 部署（推荐）

```bash
docker-compose up -d
```

### 手动部署

详见：[部署文档](docs/DEPLOYMENT.md)

---

## 监控与运维

### 健康检查

```bash
# 服务健康状态
curl http://localhost:8001/health

# 数据库连接状态
curl http://localhost:8001/health/db
```

### 日志查看

```bash
# API 服务日志
docker logs -f zhineng-api

# 数据库日志
docker logs -f zhineng-postgres
```

---

## 更新日志

### v1.3.0 (2026-03-31)

- ✅ 深度安全审计修复 (C1-C6 + R1-R6)
- ✅ 232 测试通过验证
- ✅ 容器资源限制优化
- ✅ 文档对齐 (DEVELOPMENT_RULES v2.0.0 + ENGINEERING_ALIGNMENT)

### v1.2.0 (2026-03-29)

- ✅ Hooks 系统实施（双层 Hooks 架构）
- ✅ AI 操作包装器与规则检查器
- ✅ 监控自动化脚本

### v1.1.0 (2026-03-25)

- ✅ 首个正式版本发布
- ✅ 完成向量检索功能
- ✅ 完成混合检索功能
- ✅ 完成智能问答功能
- ✅ 建立领域驱动架构
- ✅ 完成安全加固（P0）

详见：[更新日志](CHANGELOG.md)

---

## 文档

- [API 文档](docs/API.md)
- [部署指南](docs/DEPLOYMENT.md)
- [开发规则 v2.0.0](DEVELOPMENT_RULES.md)
- [工程对齐文档](ENGINEERING_ALIGNMENT.md)
- [更新日志](CHANGELOG.md)
- [运维手册](docs/OPERATIONS.md)
- [用户手册](docs/USER_MANUAL.md)

---

## 仓库

- **GitHub**: https://github.com/guangda88/zhineng-knowledge-system
- **Gitea**: http://zhinenggitea.iepose.cn/guangda/zhineng-knowledge-system

---

## 许可证

MIT License

---

**智能知识系统 v1.3.0-dev** | © 2026 Guangda
