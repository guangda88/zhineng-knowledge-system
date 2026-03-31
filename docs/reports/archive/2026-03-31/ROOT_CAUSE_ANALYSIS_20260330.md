# 系统高资源占用问题根因分析与预防方案

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

**分析日期**: 2026-03-30
**分析人**: Claude Code
**问题描述**: 系统内存占用达 30GB/31GB (96%)，可用内存仅剩 1GB

---

## 一、问题根因分析

### 1.1 技术层面问题

#### 🔴 问题1：容器无资源限制（严重）

**现状**：
```yaml
# docker-compose.yml 中所有服务都没有资源限制
services:
  api:
    # ❌ 没有 mem_limit
    # ❌ 没有 cpus
    # ❌ 没有 mem_reservation
```

**影响**：
- openlist 服务无限制占用 11.2GB 内存
- mount.davfs 无限制占用 15.2GB 内存
- github-recommender-scheduler 无限制创建僵尸进程

**根因**：
- Docker 默认不限制容器资源
- 未配置 `mem_limit`、`cpus` 等资源限制参数
- 容器可以无限制使用系统资源

---

#### 🔴 问题2：监控频率过低（严重）

**现状**：
```bash
# crontab 配置
0 0 * * 0  # 每周执行一次监控
```

**影响**：
- 问题发生 7 天内未被发现
- 内存从正常到 96% 耗时 3 天，但监控未覆盖
- 错过了最佳干预时机

**根因**：
- 监控脚本存在但频率太低（每周一次）
- 没有实时监控告警
- Prometheus 和 Grafana 配置了但未启用告警规则

---

#### 🔴 问题3：多项目混跑无隔离（严重）

**现状**：
- 系统同时运行 21 个容器，来自 6+ 个不同项目
- 所有容器共享系统资源（31GB 内存）
- 没有按项目或优先级进行资源划分

**影响**：
- 低优先级项目（github-recommender）占用资源影响核心项目
- 单个项目异常影响整个系统稳定性
- 无法追踪资源归属和责任

**根因**：
- 缺少项目级别的资源隔离
- 没有容器编排策略
- 缺少资源配额管理

---

#### 🟡 问题4：僵尸进程未及时清理（中等）

**现状**：
- github-recommender-scheduler 产生 19 个僵尸进程
- 父进程未正确 wait() 子进程
- 僵尸进程累积 2 天未清理

**影响**：
- 占用进程表资源
- 虽然内存占用小，但影响系统健康

**根因**：
- 应用代码缺陷：未正确处理子进程退出
- 缺少进程监控和自动清理机制

---

### 1.2 流程层面问题

#### 🟡 问题5：缺少定期巡检机制（中等）

**现状**：
- 没有每日/每周资源使用报告
- 缺少系统健康检查清单
- 没有责任人制度

**根因**：
- 运维流程不规范
- 过度依赖自动化，缺少人工复核

---

#### 🟡 问题6：缺少容量规划（中等）

**现状**：
- 31GB 内存运行 21 个容器，平均每个容器 1.5GB
- 没有评估容器资源需求
- 没有预留应急资源（建议预留 20%）

**根因**：
- 部署前未做容量评估
- 没有资源使用基线

---

### 1.3 架构层面问题

#### 🟡 问题7：单点故障风险（中等）

**现状**：
- openlist 和 mount.davfs 是核心存储服务
- 无冗余，无故障转移
- 单点故障影响整个系统

**根因**：
- 架构设计未考虑高可用
- 缺少服务降级方案

---

## 二、系统化预防方案

### 2.1 技术层面改进（立即执行）

#### ✅ 方案1：为所有容器添加资源限制

**执行优先级**: 🔴 紧急

**修改 docker-compose.yml**：
```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M

  redis:
    image: redis:7-alpine
    deploy:
      resources:
        limits:
          cpus: '0.3'
          memory: 256M
        reservations:
          memory: 128M

  api:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

**预期效果**：
- 单个容器内存占用上限：1GB
- 总预留：50% 内存给系统和其他服务
- 防止单个容器耗尽系统资源

---

#### ✅ 方案2：配置实时监控告警

**执行优先级**: 🔴 紧急

**2.2.1 修改 cron 监控频率**：
```bash
# 每小时执行监控（而非每周）
0 * * * * /home/ai/zhineng-knowledge-system/scripts/monitor_disk.sh
*/30 * * * * /home/ai/zhineng-knowledge-system/scripts/monitor_docker.sh
```

**2.2.2 配置 Prometheus 告警规则**：
```yaml
# monitoring/prometheus/alerts.yml
groups:
  - name: memory_alerts
    rules:
      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "内存使用率过高"
          description: "内存使用率超过 80% (当前: {{ $value }}%)"

      - alert: CriticalMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.9
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "内存严重不足"
          description: "内存使用率超过 90%，需立即处理！"

  - name: container_alerts
    rules:
      - alert: ContainerOOMKilled
        expr: rate(container_oom_events_total[5m]) > 0
        labels:
          severity: critical
        annotations:
          summary: "容器因内存不足被杀死"
```

**2.2.3 配置 AlertManager 告警通知**：
```yaml
# monitoring/alertmanager/config.yml
receivers:
  - name: 'email-alerts'
    email_configs:
      - to: 'admin@example.com'
        send_resolved: true
```

---

#### ✅ 方案3：项目资源隔离

**执行优先级**: 🟡 重要

**3.1 使用 Docker Compose 项目分离**：
```bash
# 每个项目独立 compose 文件
docker-compose -f docker-compose.yml up -d        # zhineng 项目
docker-compose -f github-recommender.yml up -d    # github 项目
docker-compose -f safeline.yml up -d              # safeline 项目
```

**3.2 为每个项目设置资源配额**：
```yaml
# docker-compose.yml
services:
  api:
    mem_limit: 1g
    memswap_limit: 1.5g
    cpus: 1.0
    blkio_config:
      weight: 500  # IO 权重
```

**3.3 使用 cgroup 资源控制**：
```bash
# 创建资源控制组
sudo cgcreate -g memory,cpuset:/zhineng
sudo cgcreate -g memory,cpuset:/other-projects

# 设置资源限制
sudo echo "10G" > /sys/fs/cgroup/memory/zhineng/memory.limit_in_bytes
sudo echo "15G" > /sys/fs/cgroup/memory/other-projects/memory.limit_in_bytes
```

---

#### ✅ 方案4：僵尸进程自动清理

**执行优先级**: 🟡 重要

**创建清理脚本** `scripts/cleanup_zombies.sh`：
```bash
#!/bin/bash
# 自动清理僵尸进程

ZOMBIE_COUNT=$(ps aux | grep defunct | grep -c defunct)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

if [ "$ZOMBIE_COUNT" -gt 10 ]; then
    echo "[$TIMESTAMP] 发现 $ZOMBIE_COUNT 个僵尸进程，开始清理..."

    # 查找僵尸进程的父进程
    ps -ef | grep defunct | grep -v grep | awk '{print $3}' | sort -u | while read PPID; do
        if [ -n "$PPID" ] && [ "$PPID" != "1" ]; then
            echo "尝试重启父进程: $PPID"
            # 检查是否是 Docker 容器进程
            CONTAINER_ID=$(docker ps -q --filter "id=$PPID")
            if [ -n "$CONTAINER_ID" ]; then
                docker restart "$CONTAINER_ID"
            else
                # 非容器进程，发送 SIGCHLD 信号
                kill -CHLD "$PPID" 2>/dev/null
            fi
        fi
    done

    sleep 5
    NEW_COUNT=$(ps aux | grep defunct | grep -c defunct)
    echo "[$TIMESTAMP] 清理完成，剩余僵尸进程: $NEW_COUNT"
fi
```

**添加到定时任务**：
```bash
# 每小时检查一次
0 * * * * /home/ai/zhineng-knowledge-system/scripts/cleanup_zombies.sh >> logs/cleanup_zombies.log 2>&1
```

---

### 2.2 流程层面改进（本周执行）

#### ✅ 方案5：建立日常巡检机制

**5.1 每日巡检清单**：
```bash
#!/bin/bash
# scripts/daily_health_check.sh

echo "==================================="
echo "系统健康日报 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "==================================="

# 1. 内存检查
echo ""
echo "📊 内存使用情况："
free -h

# 2. Docker 容器状态
echo ""
echo "🐳 Docker 容器状态："
docker ps --format "table {{.Names}}\t{{.Status}}"

# 3. 异常容器检测
echo ""
echo "⚠️  异常容器："
docker ps -a --format "{{.Names}}: {{.Status}}" | grep -E "(exited|dead|restarting)"

# 4. 僵尸进程检测
ZOMBIE_COUNT=$(ps aux | grep defunct | grep -c defunct)
echo ""
echo "🧟 僵尸进程数量：$ZOMBIE_COUNT"

# 5. 磁盘使用
echo ""
echo "💾 磁盘使用情况："
df -h | grep -E "(Filesystem|/dev/)"

# 6. 最近错误日志
echo ""
echo "📝 最近错误日志（最近 10 条）："
journalctl --since "1 hour ago" | grep -i error | tail -10

echo ""
echo "==================================="
```

**5.2 每周容量评估**：
```bash
#!/bin/bash
# scripts/weekly_capacity_review.sh

echo "==================================="
echo "系统容量周报 - $(date '+%Y-%m-%d')"
echo "==================================="

# 容器资源使用趋势
echo "容器内存使用 Top 10："
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | \
    sort -k2 -hr | head -11

# 建议和告警
MEMORY_USAGE=$(free | awk '/Mem/{printf("%.0f"), $3/$2*100}')
if [ "$MEMORY_USAGE" -gt 80 ]; then
    echo "⚠️  警告：内存使用率 ${MEMORY_USAGE}%，建议扩展或优化"
fi
```

---

#### ✅ 方案6：建立容量规划基线

**6.1 建立资源使用基线**：
```bash
# 记录正常运行时的资源使用
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" > baseline/$(date +%Y%m%d).txt
```

**6.2 容量评估标准**：
| 服务类型 | 内存限制 | CPU限制 | 备注 |
|---------|---------|---------|------|
| 核心API | 1GB | 1核 | 业务核心 |
| 数据库 | 512MB | 0.5核 | PostgreSQL/Redis |
| 监控服务 | 256MB | 0.3核 | Prometheus/Grafana |
| 辅助服务 | 128MB | 0.2核 | Exporter等 |
| 预留 | 6GB | 2核 | 系统和应急 |

**总计**：约 20GB 用于服务，11GB 预留（35%）

---

### 2.3 架构层面改进（本月执行）

#### ✅ 方案7：服务高可用改造

**7.1 核心服务冗余**：
```yaml
# docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    deploy:
      replicas: 2  # 主从复制
      placement:
        constraints:
          - node.labels.role == database

  api:
    deploy:
      replicas: 2  # 多实例负载均衡
```

**7.2 服务降级策略**：
- 当内存使用率 > 85% 时，自动停止非核心服务
- 当内存使用率 > 90% 时，触发告警并准备重启
- 当内存使用率 > 95% 时，自动重启高内存占用服务

---

#### ✅ 方案8：应急响应机制

**8.1 创建应急脚本** `scripts/emergency_memory_recovery.sh`：
```bash
#!/bin/bash
# 内存应急恢复脚本

THRESHOLD=90
MEMORY_USAGE=$(free | awk '/Mem/{printf("%.0f"), $3/$2*100}')

if [ "$MEMORY_USAGE" -gt "$THRESHOLD" ]; then
    echo "🚨 内存使用率 ${MEMORY_USAGE}% 超过阈值，执行应急恢复..."

    # 1. 停止非核心容器
    echo "停止非核心容器..."
    docker stop github-recommender-web github-recommender-scheduler

    # 2. 清理 Docker 缓存
    echo "清理 Docker 缓存..."
    docker system prune -f

    # 3. 清理系统缓存
    echo "清理系统缓存..."
    sync
    sudo sysctl -w vm.drop_caches=3

    # 4. 清理僵尸进程
    ./scripts/cleanup_zombies.sh

    # 5. 报告结果
    NEW_USAGE=$(free | awk '/Mem/{printf("%.0f"), $3/$2*100}')
    echo "应急恢复完成，内存使用率: ${MEMORY_USAGE}% → ${NEW_USAGE}%"
fi
```

**8.2 设置应急触发器**：
```bash
# 添加到 crontab，每 10 分钟检查一次
*/10 * * * * /home/ai/zhineng-knowledge-system/scripts/emergency_memory_recovery.sh
```

---

## 三、实施计划

### 阶段1：紧急修复（24小时内）

| 任务 | 优先级 | 预计时间 | 责任人 |
|------|--------|---------|--------|
| ✅ 为所有容器添加资源限制 | 🔴 紧急 | 1小时 | 系统管理员 |
| ✅ 配置 Prometheus 告警规则 | 🔴 紧急 | 2小时 | 运维工程师 |
| ✅ 修改监控频率为每小时 | 🔴 紧急 | 10分钟 | 系统管理员 |
| ✅ 创建僵尸进程清理脚本 | 🟡 重要 | 30分钟 | 开发工程师 |

### 阶段2：流程建立（本周内）

| 任务 | 优先级 | 预计时间 | 责任人 |
|------|--------|---------|--------|
| ✅ 创建每日巡检脚本 | 🟡 重要 | 1小时 | 运维工程师 |
| ✅ 建立容量规划基线 | 🟡 重要 | 2小时 | 架构师 |
| ✅ 编写应急响应预案 | 🟡 重要 | 3小时 | 运维团队 |
| ✅ 项目资源隔离改造 | 🟡 重要 | 4小时 | 系统管理员 |

### 阶段3：架构优化（本月内）

| 任务 | 优先级 | 预计时间 | 责任人 |
|------|--------|---------|--------|
| ✅ 核心服务高可用改造 | 🟢 长期 | 1周 | 架构师 |
| ✅ 服务降级策略实施 | 🟢 长期 | 3天 | 开发团队 |
| ✅ 容量规划自动化 | 🟢 长期 | 2天 | 运维工程师 |

---

## 四、效果验证

### 4.1 技术指标

| 指标 | 优化前 | 目标 | 验证方法 |
|------|--------|------|---------|
| 内存使用率 | 96% | <80% | `free -h` |
| 可用内存 | 1GB | >6GB | `free -h` |
| 僵尸进程数 | 19个 | <5个 | `ps aux \| grep defunct` |
| 监控频率 | 每周 | 每小时 | `crontab -l` |
| 告警响应时间 | N/A | <5分钟 | Prometheus告警日志 |

### 4.2 流程指标

| 指标 | 优化前 | 目标 |
|------|--------|------|
| 问题发现时间 | 7天 | <1小时 |
| 问题响应时间 | 3天 | <30分钟 |
| 容量评估频率 | 无 | 每周 |

---

## 五、总结

### 5.1 根本原因

1. **技术层面**：容器无资源限制、监控缺失、多项目混跑无隔离
2. **流程层面**：缺少巡检机制、无容量规划
3. **架构层面**：单点故障、缺少应急机制

### 5.2 解决方案核心

**技术防护**：资源限制 + 实时监控 + 自动恢复
**流程保障**：日常巡检 + 容量规划 + 应急预案
**架构支撑**：资源隔离 + 高可用 + 服务降级

### 5.3 预期效果

通过系统化改进，预期：
- ✅ 内存使用率控制在 80% 以下
- ✅ 问题发现时间从 7天缩短到 <1小时
- ✅ 自动处理 90% 的资源异常
- ✅ 系统具备自我恢复能力

**最终目标：建立可预测、可控制、可自动恢复的稳定系统！**

---

**文档版本**: v1.0
**最后更新**: 2026-03-30
**下次审查**: 2026-04-30
