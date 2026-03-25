# 智能知识系统 (Zhineng Knowledge System)

<div align="center">

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v1.1.0-orange.svg)](https://github.com/guangda88/zhineng-knowledge-system/releases/tag/v1.1.0)

**基于 RAG 的气功、中医、儒家智能知识问答系统**

语义搜索 • 智能问答 • 领域驱动 • 安全合规

[快速开始](#快速开始) • [文档](docs/) • [API 文档](docs/API.md) • [更新日志](CHANGELOG.md)

</div>

---

## 项目简介

智能知识系统是一个基于检索增强生成（RAG）技术的专业知识问答系统，专注于**气功、中医、儒家**等中华传统文化领域。

### 核心特性

| 特性 | 说明 |
|------|------|
| **向量检索** | 基于 pgvector 的语义搜索 |
| **混合检索** | 向量 + BM25 双路召回 |
| **智能问答** | CoT/ReAct/GraphRAG 多种推理模式 |
| **领域驱动** | 气功/中医/儒家/通用 四大领域 |
| **认证授权** | JWT + RBAC 权限控制 |
| **API 网关** | 限流、熔断、服务发现 |

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
├── backend/               # 后端服务
│   ├── main.py           # FastAPI 主入口
│   ├── config.py         # 配置管理
│   ├── models.py         # 数据模型
│   ├── api/              # API 路由
│   ├── services/         # 业务服务
│   ├── auth/             # 认证授权
│   ├── cache/            # 缓存管理
│   └── monitoring/       # 监控指标
├── frontend/             # 前端文件
├── tests/                # 测试代码
├── docs/                 # 文档
├── scripts/              # 脚本工具
├── docker-compose.yml    # 容器编排
└── DEVELOPMENT_RULES.md  # 开发规范
```

### 开发流程

1. 从 `develop` 创建功能分支
2. 开发并遵循开发规范
3. 运行测试：`pytest tests/ -v`
4. 提交代码：遵循 Conventional Commits
5. 合并到 `develop`

详见：[开发规则文档](DEVELOPMENT_RULES.md)

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
- [开发规则](DEVELOPMENT_RULES.md)
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

**智能知识系统 v1.1.0** | © 2026 Guangda
