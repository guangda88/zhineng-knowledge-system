# 智能知识系统 - 统一部署指南

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 设置 API 密钥等

# 2. 一键启动所有服务
docker-compose up -d

# 3. 等待服务启动 (约2-3分钟)
docker-compose logs -f

# 4. 访问服务
# 前端界面: http://localhost:3000
# 后端API: http://localhost:8000
# 气功服务: http://localhost:8002
# Grafana: http://localhost:3001
# MinIO: http://localhost:9001
```

## 服务架构

```
┌─────────────────────────────────────────────────────────────┐
│                        统一知识系统                            │
│                    (MVP: 气功知识领域)                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐                            │
│  │ Web Frontend │  │ Web Backend │                           │
│  │   :3000      │  │   :8000      │                           │
│  └──────┬──────┘  └──────┬──────┘                            │
│         │                │                                   │
│         └────────────────┘                                   │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              气功知识服务                            │    │
│  │           :8002 (领域知识 + RAG)                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              知识存储层                              │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐     │    │
│  │  │PostgreSQL│  │  Redis   │  │    MinIO        │     │    │
│  │  │+pgvector │  │  缓存    │  │  对象存储       │     │    │
│  │  └──────────┘  └──────────┘  └──────────────────┘     │    │
│  └─────────────────────────────────────────────────────┘    │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              AI处理层                               │    │
│  │  DeepSeek API + Celery Workers                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 服务列表

| 服务 | 端口 | 说明 | 状态 |
|------|------|------|------|
| **web-frontend** | 3000 | React前端界面 | ✅ |
| **web-backend** | 8000 | FastAPI后端 | ✅ |
| **qigong-service** | 8002 | 气功知识服务 | ✅ 新增 |
| **postgres** | 5432 | PostgreSQL + pgvector | ✅ |
| **redis** | 6379 | Redis缓存 | ✅ |
| **minio** | 9000/9001 | MinIO对象存储 | ✅ |
| **grafana** | 3001 | Grafana监控 | ✅ |
| **prometheus** | 9090 | Prometheus指标 | ✅ |
| **celery-worker** | - | 异步任务处理 | ✅ |
| **celery-beat** | - | 定时任务调度 | ✅ |

## 气功知识服务

### 功能
- 知识搜索 (`/api/v1/search`)
- 智能问答 (`/api/v1/qa`)
- 推理查询 (`/api/v1/reasoning`)
- 分类浏览 (`/api/v1/categories`)

### 知识分类
- 基础理论
- 功法练习
- 养生保健
- 练习技巧

## 开发模式启动

```bash
# 单独启动某个服务
docker-compose up -d postgres redis

# 查看日志
docker-compose logs -f qigong-knowledge-service

# 重启服务
docker-compose restart web-backend

# 停止所有服务
docker-compose down

# 查看服务状态
docker-compose ps
```

## 数据持久化

所有数据存储在 `/data/` 目录：
- `/data/postgres` - PostgreSQL 数据
- `/data/redis` - Redis 数据
- `/data/minio` - MinIO 对象存储
- `/data/grafana` - Grafana 配置
- `/data/prometheus` - Prometheus 数据
- `/data/qigong` - 气功知识数据

## 监控

- **Grafana**: http://localhost:3001 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **服务日志**: `docker-compose logs -f [service-name]`

## 故障排查

```bash
# 检查服务状态
docker-compose ps

# 查看服务日志
docker-compose logs web-backend
docker-compose logs qigong-knowledge-service

# 重启特定服务
docker-compose restart postgres

# 进入容器调试
docker-compose exec web-backend bash
docker-compose exec postgres psql -U zhineng -d zhineng_kb
```
