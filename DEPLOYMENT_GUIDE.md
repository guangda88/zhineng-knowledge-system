# 智能知识系统 - 统一部署指南

## 目录

- [快速开始](#快速开始)
- [部署前检查清单](#部署前检查清单)
- [服务架构](#服务架构)
- [部署流程](#部署流程)
- [备份策略](#备份策略)
- [回滚方案](#回滚方案)
- [健康检查](#健康检查)
- [故障恢复流程](#故障恢复流程)
- [紧急联系](#紧急联系)

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
# 前端界面: http://localhost:8008
# 后端API: http://localhost:8001
# Grafana: http://localhost:3000
# Prometheus: http://localhost:9090
```

## 部署前检查清单

### 系统环境检查

- [ ] **操作系统**: Linux (推荐 Ubuntu 20.04+)
- [ ] **Docker**: 版本 20.10+
  ```bash
  docker --version
  ```
- [ ] **Docker Compose**: 版本 2.0+
  ```bash
  docker-compose --version
  ```
- [ ] **磁盘空间**: 至少 20GB 可用空间
  ```bash
  df -h
  ```
- [ ] **内存**: 至少 4GB 可用内存
  ```bash
  free -h
  ```
- [ ] **端口检查**: 确保以下端口未被占用
  ```bash
  netstat -tuln | grep -E '8008|8001|5436|6381|9090|3000'
  ```

### 配置文件检查

- [ ] **docker-compose.yml**: 存在且配置正确
- [ ] **.env**: 已创建并配置必要的环境变量
  ```bash
  test -f .env && echo "配置文件存在"
  ```
- [ ] **nginx配置**: nginx/nginx.conf 存在
- [ ] **后端配置**: backend/config.py 存在

### 网络检查

- [ ] **防火墙规则**: 允许必要端口
  ```bash
  sudo ufw status
  ```
- [ ] **DNS解析**: 确保可以访问外部API
  ```bash
  ping -c 3 api.deepseek.com
  ```

### 数据库检查

- [ ] **数据卷**: postgres_data、redis_data 等卷可用
  ```bash
  docker volume ls
  ```
- [ ] **备份目录**: backups 目录可写
  ```bash
  mkdir -p backups && ls -ld backups
  ```

### 依赖服务检查

- [ ] **外部API**: DeepSeek API密钥有效
  ```bash
  grep DEEPSEEK_API_KEY .env
  ```

## 服务架构

```
┌─────────────────────────────────────────────────────────────┐
│                        智能知识系统                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐                            │
│  │   Nginx     │  │   API       │                           │
│  │   :8008     │  │   :8001      │                           │
│  └──────┬──────┘  └──────┬──────┘                            │
│         │                │                                   │
│         └────────────────┘                                   │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              数据存储层                              │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐     │    │
│  │  │PostgreSQL│  │  Redis   │  │   Prometheus    │     │    │
│  │  │+pgvector │  │  缓存    │  │   + Grafana     │     │    │
│  │  └──────────┘  └──────────┘  └──────────────────┘     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 服务列表

| 服务 | 端口 | 说明 | 健康检查 |
|------|------|------|----------|
| **nginx** | 8008 | 反向代理/前端 | `curl http://localhost:8008` |
| **api** | 8001 | FastAPI后端 | `curl http://localhost:8001/health` |
| **postgres** | 5436 | PostgreSQL + pgvector | `docker-compose exec postgres pg_isready` |
| **redis** | 6381 | Redis缓存 | `docker-compose exec redis redis-cli ping` |
| **prometheus** | 9090 | Prometheus指标 | `curl http://localhost:9090` |
| **grafana** | 3000 | Grafana监控 | `curl http://localhost:3000` |
| **postgres-exporter** | 9187 | Postgres指标 | `curl http://localhost:9187/metrics` |
| **redis-exporter** | 9121 | Redis指标 | `curl http://localhost:9121/metrics` |

## 部署流程

### 标准部署

```bash
# 1. 执行部署前备份
./scripts/deploy/backup.sh all

# 2. 创建部署前版本快照
./scripts/deploy/rollback.sh pre-rollback

# 3. 拉取最新代码
git pull origin main

# 4. 更新配置文件（如需要）
cp .env.example .env
vim .env

# 5. 构建镜像
docker-compose build

# 6. 启动服务
docker-compose up -d

# 7. 等待服务就绪
sleep 30

# 8. 执行健康检查
./scripts/deploy/health_check.sh

# 9. 验证部署成功后创建版本快照
./scripts/deploy/rollback.sh pre-rollback post-deploy_$(date +%Y%m%d_%H%M%S)
```

### 零停机部署

```bash
# 1. 备份当前版本
./scripts/deploy_backup.sh pre-deploy

# 2. 拉取新代码
git pull origin main

# 3. 构建新版本镜像
docker-compose build

# 4. 启动新版本容器（并行运行）
docker-compose up -d --no-deps --scale api=2

# 5. 验证新版本
./scripts/health_check.sh api

# 6. 切换流量（通过nginx配置）
# 重载nginx配置
docker-compose exec nginx nginx -s reload

# 7. 停止旧版本容器
docker-compose up -d --scale api=1
```

## 备份策略

### 自动备份

设置每日自动备份（推荐凌晨2点执行）：

```bash
# 安装定时任务
./scripts/deploy/backup.sh install-cron

# 查看定时任务
crontab -l
```

### 手动备份

```bash
# 全量备份（数据库+配置）
./scripts/deploy/backup.sh all

# 快速备份（仅数据库）
./scripts/deploy/backup.sh quick

# 仅备份数据库
./scripts/deploy/backup.sh db

# 仅备份配置文件
./scripts/deploy/backup.sh config

# 列出所有备份
./scripts/deploy/backup.sh list

# 验证备份文件
./scripts/deploy/backup.sh verify backups/db_full_20240325.sql.gz

# 清理旧备份
./scripts/deploy/backup.sh clean
```

### 备份保留策略

- **数据库备份**: 保留7天（默认）
- **配置备份**: 保留14天（默认）
- **数据目录备份**: 保留7天

可通过环境变量调整：

```bash
export RETENTION_DAYS=14
./scripts/deploy/backup.sh clean
```

## 回滚方案

### 快速回滚

当部署出现问题需要快速恢复时：

```bash
# 查看可用版本和备份
./scripts/deploy/rollback.sh list

# 快速回滚（使用最近备份恢复数据库并重启服务）
./scripts/deploy/rollback.sh quick

# 快速容器恢复（仅重启服务）
./scripts/deploy/rollback.sh quick-container
```

### 指定版本回滚

```bash
# 回滚到指定版本
./scripts/deploy/rollback.sh rollback v_20240325_120000

# 仅回滚容器配置（不恢复数据库）
./scripts/deploy/rollback.sh config-only v_20240325_120000

# 仅回滚数据库（从指定备份）
./scripts/deploy/rollback.sh db-only backups/db_full_20240325.sql.gz
```

### 回滚步骤详解

#### 第一步：评估问题

```bash
# 查看当前系统状态
./scripts/deploy/rollback.sh status

# 执行健康检查，确定问题范围
./scripts/deploy/health_check.sh

# 查看服务日志定位问题
docker-compose logs --tail=100 api
```

#### 第二步：选择回滚版本

```bash
# 列出所有可用版本和备份
./scripts/deploy/rollback.sh list
```

输出示例：
```
=== 可用版本列表 ===

v_20240325_140000 * 当前版本
  created_at=2024-03-25T14:00:00+08:00
  git_commit=abc1234

v_20240325_120000
  created_at=2024-03-25T12:00:00+08:00
  git_commit=def5678

--- 数据库备份 ---
  db_full_20240325_140000.sql.gz    15MB  2024-03-25 14:00
  db_full_20240325_120000.sql.gz    14MB  2024-03-25 12:00
```

#### 第三步：执行回滚

```bash
# 回滚到指定版本
# 系统会自动：
# 1. 创建当前状态快照（用于再次回滚）
# 2. 恢复指定版本的配置文件
# 3. 询问是否恢复数据库
# 4. 重启服务
# 5. 验证回滚结果

./scripts/deploy/rollback.sh rollback v_20240325_120000
```

#### 第四步：验证回滚结果

```bash
# 执行完整健康检查
./scripts/deploy/health_check.sh

# 查看当前版本
./scripts/deploy/rollback.sh status
```

### 部署前快照

在每次部署前创建快照，以便快速回滚：

```bash
# 部署前创建快照
./scripts/deploy/rollback.sh pre-rollback

# 部署...

# 如果部署失败，快速回滚
./scripts/deploy/rollback.sh rollback v_<最新快照版本>
```

## 健康检查

### 完整健康检查

```bash
# 检查所有服务
./scripts/deploy/health_check.sh
```

输出示例：
```
========================================
  智能知识系统 - 健康检查
========================================
检查时间: 2024-03-25 10:30:00

--- 容器状态检查 ---
✓ PASS - zhineng-postgres - 运行中 (重启次数: 0)
✓ PASS - zhineng-redis - 运行中 (重启次数: 0)
✓ PASS - zhineng-api - 运行中 (重启次数: 1)

--- 数据库检查 ---
✓ PASS - 数据库连接正常
ℹ INFO - 数据库大小: 256 MB
ℹ INFO - 数据表数量: 12

--- API服务检查 ---
✓ PASS - API健康检查端点正常
✓ PASS - API响应时间: 45ms
```

### 单项检查

```bash
# 快速检查（容器+数据库+API）
./scripts/deploy/health_check.sh quick

# 仅检查容器
./scripts/deploy/health_check.sh containers

# 仅检查数据库
./scripts/deploy/health_check.sh database

# 仅检查Redis
./scripts/deploy/health_check.sh redis

# 仅检查API
./scripts/deploy/health_check.sh api

# 仅检查前端
./scripts/deploy/health_check.sh frontend

# 检查监控服务
./scripts/deploy/health_check.sh monitoring

# 检查资源使用
./scripts/deploy/health_check.sh resources

# 检查日志错误
./scripts/deploy/health_check.sh logs

# 检查网络状态
./scripts/deploy/health_check.sh network

# 持续监控模式（每30秒刷新一次）
./scripts/deploy/health_check.sh watch
```

### 部署后验证流程

```bash
# 1. 等待服务启动
sleep 30

# 2. 执行快速健康检查
./scripts/deploy/health_check.sh quick

# 3. 如果快速检查通过，执行完整检查
./scripts/deploy/health_check.sh

# 4. 检查服务日志
docker-compose logs --tail=50
```

## 故障恢复流程

### 服务异常

**症状**: 容器频繁重启

```bash
# 1. 查看容器状态
docker-compose ps

# 2. 查看日志
docker-compose logs -f --tail=100 <service-name>

# 3. 重启服务
docker-compose restart <service-name>

# 4. 如果问题持续，执行健康检查
./scripts/health_check.sh
```

### 数据库异常

**症状**: 数据库连接失败

```bash
# 1. 检查数据库容器
docker-compose ps postgres

# 2. 检查数据库日志
docker-compose logs postgres

# 3. 测试连接
docker-compose exec postgres pg_isready -U zhineng

# 4. 如果数据损坏，从备份恢复
./scripts/restore.sh restore-db <backup-file>
```

### 磁盘空间不足

**症状**: 磁盘使用率过高

```bash
# 1. 检查磁盘使用
df -h

# 2. 清理Docker资源
docker system prune -a

# 3. 清理旧备份
./scripts/deploy_backup.sh clean

# 4. 清理日志
docker-compose logs --tail=0 -f > /dev/null
find ./logs -name "*.log" -mtime +30 -delete
```

### 性能问题

**症状**: 响应缓慢

```bash
# 1. 检查资源使用
./scripts/health_check.sh resources

# 2. 查看容器资源占用
docker stats

# 3. 检查慢查询
docker-compose exec postgres psql -U zhineng -d zhineng_kb -c "
  SELECT query, mean_exec_time, calls
  FROM pg_stat_statements
  ORDER BY mean_exec_time DESC
  LIMIT 10;
"

# 4. 重启服务
docker-compose restart
```

### 完全恢复流程

当系统出现严重问题时，执行完全恢复：

```bash
# 1. 停止所有服务
docker-compose down

# 2. 备份当前状态（如果可能）
./scripts/deploy_backup.sh pre-deploy

# 3. 选择一个已知良好的备份
./scripts/restore.sh list

# 4. 执行完整恢复
./scripts/restore.sh restore-full <date>

# 5. 启动服务
docker-compose up -d

# 6. 验证恢复
./scripts/health_check.sh
```

## 监控

### Grafana仪表板

- **地址**: http://localhost:3000
- **默认账号**: admin / admin123
- **配置数据源**: Prometheus (http://prometheus:9090)

### Prometheus指标

- **地址**: http://localhost:9090
- **关键指标**:
  - `up`: 服务可用性
  - `rate(http_requests_total[5m])`: 请求速率
  - `rate(http_request_duration_seconds_sum[5m])`: 响应时间

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f api

# 查看最近100行日志
docker-compose logs --tail=100

# 查看带时间戳的日志
docker-compose logs -t
```

## 开发模式启动

```bash
# 单独启动某个服务
docker-compose up -d postgres redis

# 查看日志
docker-compose logs -f api

# 重启服务
docker-compose restart api

# 停止所有服务
docker-compose down

# 查看服务状态
docker-compose ps
```

## 数据持久化

所有数据存储在 Docker volumes 中：

| Volume | 用途 | 备份频率 |
|--------|------|----------|
| postgres_data | PostgreSQL 数据 | 每日 |
| redis_data | Redis 数据 | 每日 |
| prometheus_data | Prometheus 数据 | 每周 |
| grafana_data | Grafana 配置 | 每周 |

## 紧急联系

### 系统架构师
- **职责**: 架构设计、重大故障处理
- **联系方式**: [待填写]

### DevOps工程师
- **职责**: 部署、备份、监控
- **联系方式**: [待填写]

### 数据库管理员
- **职责**: 数据库优化、恢复
- **联系方式**: [待填写]

### 值班轮换

| 星期 | 负责人 | 联系方式 |
|------|--------|----------|
| 周一 | [待填写] | [待填写] |
| 周二 | [待填写] | [待填写] |
| 周三 | [待填写] | [待填写] |
| 周四 | [待填写] | [待填写] |
| 周五 | [待填写] | [待填写] |

### 紧急响应流程

1. **发现问题** → 立即通知值班人员
2. **初步评估** → 确定影响范围
3. **快速修复** → 执行回滚或重启
4. **根因分析** → 事后复盘
5. **改进措施** → 更新文档和流程

## 附录

### 常用命令速查

```bash
# 部署相关
./scripts/deploy/backup.sh all                # 全量备份
./scripts/deploy/rollback.sh list             # 列出版本
./scripts/deploy/rollback.sh rollback <ver>   # 回滚
./scripts/deploy/rollback.sh quick            # 快速回滚
./scripts/deploy/health_check.sh              # 健康检查

# Docker相关
docker-compose up -d                              # 启动服务
docker-compose down                               # 停止服务
docker-compose ps                                 # 查看状态
docker-compose logs -f [service]                  # 查看日志
docker-compose restart [service]                  # 重启服务

# 数据库相关
docker-compose exec postgres psql -U zhineng      # 进入数据库
docker-compose exec postgres pg_dump ...          # 导出数据库
```

### 端口映射

| 内部端口 | 外部端口 | 服务 |
|----------|----------|------|
| 5432 | 5436 | PostgreSQL |
| 6379 | 6381 | Redis |
| 8000 | 8001 | API |
| 80 | 8008 | Nginx |
| 9090 | 9090 | Prometheus |
| 3000 | 3000 | Grafana |
| 9187 | 9187 | Postgres Exporter |
| 9121 | 9121 | Redis Exporter |

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| POSTGRES_USER | zhineng | 数据库用户名 |
| POSTGRES_PASSWORD | zhineng123 | 数据库密码 |
| POSTGRES_DB | zhineng_kb | 数据库名 |
| REDIS_PASSWORD | redis123 | Redis密码 |
| API_PORT | 8000 | API内部端口 |
| RETENTION_DAYS | 7 | 备份保留天数 |

### 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2024-03-25 | v2.0 | 完善部署回滚方案，添加健康检查脚本 |
| 2024-03-20 | v1.5 | 添加监控服务 |
| 2024-03-15 | v1.0 | 初始版本 |
