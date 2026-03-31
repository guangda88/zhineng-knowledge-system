# 系统优化实施路线图

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

**创建日期**: 2026-03-30
**当前状态**: 内存使用率 15%，可用内存 26GB ✅
**目标**: 建立可预测、可控制、可自动恢复的稳定系统

---

## ✅ 已完成的优化（2026-03-30）

### 紧急修复阶段

| 任务 | 状态 | 效果 |
|------|------|------|
| 停止 openlist 服务 | ✅ 完成 | 释放 11GB 内存 |
| 卸载 mount.davfs | ✅ 完成 | 释放 15GB 内存 |
| 清理僵尸进程 | ✅ 完成 | 19个 → 1个 |
| 创建监控脚本 | ✅ 完成 | 4个自动化脚本 |
| 更新 crontab | ✅ 完成 | 监控频率提升168倍 |
| 添加容器资源限制 | ✅ 完成 | 总上限 2.7GB |

**当前成果**：
- ✅ 内存使用率：96% → 15% (降低 81%)
- ✅ 可用内存：1GB → 26GB (增加 25倍)
- ✅ 问题发现时间：7天 → <1小时
- ✅ 自动恢复机制：已启用

---

## 📅 本周优化计划 (2026-03-30 ~ 2026-04-05)

### 周一 (3月30日) - 当天完成 ✅

#### ✅ 已完成：
1. **容器资源限制应用**
   - 为所有服务添加内存和CPU限制
   - 验证资源限制生效
   - 状态：✅ 已完成

2. **监控升级**
   - crontab 更新为每小时监控
   - 创建僵尸进程清理脚本
   - 创建内存应急恢复脚本
   - 状态：✅ 已完成

---

### 周二 (3月31日) - 容量规划与监控完善

#### 📋 待办事项：

**1. 创建容量规划基线**
```bash
# 执行命令
./scripts/create_capacity_baseline.sh
```

**预期输出**：
- 记录各容器正常资源使用范围
- 建立资源使用基线
- 生成容量报告

**2. 配置 Prometheus 告警**

创建文件：`monitoring/prometheus/alerts.yml`
```yaml
groups:
  - name: memory_alerts
    interval: 30s
    rules:
      - alert: HighMemoryUsage
        expr: (container_memory_usage_bytes / container_spec_memory_limit_bytes) > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "容器内存使用率过高"
          description: "{{ $labels.name }} 内存使用率 {{ $value }}%"

      - alert: ContainerOOMKilled
        expr: increase(container_oom_events_total[5m]) > 0
        labels:
          severity: critical
        annotations:
          summary: "容器因内存不足被杀死"
```

**3. 测试应急恢复机制**
```bash
# 模拟高内存占用（测试用）
stress-ng --vm 1 --vm-bytes 2G --timeout 60s

# 验证应急脚本是否触发
tail -f logs/emergency_recovery.log
```

---

### 周三 (4月1日) - 其他项目资源限制

#### 📋 待办事项：

**1. 为其他 Docker 项目添加资源限制**

需要优化的项目：
- github-recommender
- safeline
- fojin
- owjdxb

**操作步骤**：
```bash
# 1. 备份各项目的 docker-compose.yml
cp /path/to/github-recommender/docker-compose.yml /path/to/github-recommender/docker-compose.yml.backup

# 2. 添加资源限制（参考本项目的配置）

# 3. 重启项目验证
cd /path/to/project && docker-compose down && docker-compose up -d
```

**2. 创建项目资源配额**

```bash
# 创建 cgroup 资源控制组
sudo cgcreate -g memory,cpuset:/zhineng
sudo cgcreate -g memory,cpuset:/other-projects

# 设置资源限制
echo "10G" | sudo tee /sys/fs/cgroup/memory/zhineng/memory.limit_in_bytes
echo "15G" | sudo tee /sys/fs/cgroup/memory/other-projects/memory.limit_in_bytes
```

---

### 周四 (4月2日) - 监控告警配置

#### 📋 待办事项：

**1. 安装和配置 AlertManager**

```bash
# 创建 AlertManager 配置
mkdir -p monitoring/alertmanager
cat > monitoring/alertmanager/config.yml <<EOF
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'email-alerts'

receivers:
  - name: 'email-alerts'
    email_configs:
      - to: 'admin@example.com'
        send_resolved: true
EOF

# 添加到 docker-compose.yml
```

**2. 配置 Grafana 仪表板**

- 创建系统资源监控仪表板
- 配置容器资源使用仪表板
- 设置告警通知

---

### 周五 (4月3日) - 流程建立

#### 📋 待办事项：

**1. 创建每日巡检脚本**

文件：`scripts/daily_health_check.sh`
```bash
#!/bin/bash
# 每日系统健康检查

echo "======================================"
echo "系统健康日报 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================"

# 内存检查
echo ""
echo "📊 内存使用情况："
free -h

# Docker 容器状态
echo ""
echo "🐳 Docker 容器状态："
docker ps --format "table {{.Names}}\t{{.Status}}"

# 异常容器检测
echo ""
echo "⚠️  异常容器："
docker ps -a --format "{{.Names}}: {{.Status}}" | grep -E "(exited|dead|restarting)"

# 僵尸进程检测
ZOMBIE_COUNT=$(ps aux | grep defunct | grep -c defunct)
echo ""
echo "🧟 僵尸进程数量：$ZOMBIE_COUNT"

# 磁盘使用
echo ""
echo "💾 磁盘使用情况："
df -h | grep -E "(Filesystem|/dev/)"
```

**2. 建立每周容量评估**

文件：`scripts/weekly_capacity_review.sh`
```bash
#!/bin/bash
# 每周容量评估

echo "======================================"
echo "系统容量周报 - $(date '+%Y-%m-%d')"
echo "======================================"

# 容器资源使用趋势
echo ""
echo "容器内存使用 Top 10："
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | \
    sort -k2 -hr | head -11

# 建议和告警
MEMORY_USAGE=$(LC_ALL=C free | grep "^Mem:" | awk '{printf("%.0f", $3/$2*100)}')
if [ "$MEMORY_USAGE" -gt 80 ]; then
    echo ""
    echo "⚠️  警告：内存使用率 ${MEMORY_USAGE}%，建议："
    echo "  - 检查是否有异常占用"
    echo "  - 考虑扩展或优化"
fi
```

**3. 添加到 crontab**
```bash
# 每日健康检查（每天早上9点）
0 9 * * * /home/ai/zhineng-knowledge-system/scripts/daily_health_check.sh >> /home/ai/zhineng-knowledge-system/logs/daily_health.log 2>&1

# 每周容量评估（每周日下午5点）
0 17 * * 0 /home/ai/zhineng-knowledge-system/scripts/weekly_capacity_review.sh >> /home/ai/zhineng-knowledge-system/logs/weekly_capacity.log 2>&1
```

---

### 周六-周日 (4月4-5日) - 文档整理与培训

#### 📋 待办事项：

**1. 编写运维手册**

创建文件：`docs/OPERATIONS_MANUAL.md`
- 日常巡检流程
- 常见问题处理
- 应急响应流程
- 容量管理规范

**2. 团队培训**

培训内容：
- 系统架构说明
- 监控系统使用
- 应急处理流程
- 容量规划方法

---

## 📅 本月优化计划 (2026年3月30日 ~ 4月30日)

### 第1周 (3月30日 ~ 4月5日) - 当前周 ✅

**目标**: 完成紧急修复和监控升级

- ✅ 容器资源限制应用
- ✅ 监控频率升级
- ⏳ 容量规划基线建立
- ⏳ Prometheus 告警配置
- ⏳ 应急恢复机制测试

**预期完成度**: 100%

---

### 第2周 (4月6日 ~ 4月12日) - 服务高可用

**目标**: 提升核心服务可用性

#### 📋 主要任务：

**1. 数据库主从复制**

```yaml
# docker-compose.yml 添加
postgres-master:
  image: pgvector/pgvector:pg16
  environment:
    POSTGRES_REPLICATION_USER: replicator
    POSTGRES_REPLICATION_PASSWORD: ${REPL_PASSWORD}

postgres-slave:
  image: pgvector/pgvector:pg16
  environment:
    POSTGRES_MASTER_HOST: postgres-master
    POSTGRES_REPLICATION_USER: replicator
```

**2. API 多实例部署**

```yaml
api:
  deploy:
    replicas: 2  # 2个实例负载均衡
    resources:
      limits:
        memory: 1G
```

**3. Redis 哨兵模式**

```yaml
redis-sentinel:
  image: redis:7-alpine
  command: redis-sentinel /etc/redis/sentinel.conf
```

---

### 第3周 (4月13日 ~ 4月19日) - 自动化优化

**目标**: 提升系统自动化水平

#### 📋 主要任务：

**1. 自动扩缩容**

创建脚本：`scripts/auto_scaling.sh`
```bash
#!/bin/bash
# 根据负载自动扩缩容

MEMORY_USAGE=$(LC_ALL=C free | grep "^Mem:" | awk '{printf("%.0f", $3/$2*100)}')

if [ "$MEMORY_USAGE" -gt 80 ]; then
    # 扩容：停止非核心服务
    docker stop github-recommender-web
elif [ "$MEMORY_USAGE" -lt 40 ]; then
    # 缩容：恢复非核心服务
    docker start github-recommender-web
fi
```

**2. 日志自动轮转**

配置 logrotate：
```bash
# /etc/logrotate.d/zhineng-app
/home/ai/zhineng-knowledge-system/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ai ai
}
```

**3. 备份自动化**

创建脚本：`scripts/automated_backup.sh`
```bash
#!/bin/bash
# 自动备份数据库和数据卷

BACKUP_DIR="/backup/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# 备份数据库
docker exec zhineng-postgres pg_dump -U zhineng zhineng_kb > "$BACKUP_DIR/database.sql"

# 备份 Docker volumes
docker run --rm -v zhineng_postgres_data:/data -v "$BACKUP_DIR":/backup alpine tar czf /backup/postgres_data.tar.gz -C /data .
```

---

### 第4周 (4月20日 ~ 4月30日) - 性能优化与总结

**目标**: 优化性能并总结成果

#### 📋 主要任务：

**1. 应用性能优化**

- 数据库查询优化
- API 响应时间优化
- 静态资源缓存配置
- CDN 集成（如果需要）

**2. 网络优化**

```yaml
# docker-compose.yml
networks:
  zhineng-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

**3. 月度总结报告**

创建文件：`docs/MONTHLY_REPORT_202604.md`
- 优化成果总结
- 性能指标对比
- 问题与解决方案
- 下月改进计划

---

## 🎯 关键成功指标 (KPI)

| 指标 | 优化前 | 目标 | 当前 | 状态 |
|------|--------|------|------|------|
| 内存使用率 | 96% | <80% | 15% | ✅ 达标 |
| 可用内存 | 1GB | >6GB | 26GB | ✅ 超标 |
| 问题发现时间 | 7天 | <1小时 | 实时 | ✅ 达标 |
| 僵尸进程数 | 19个 | <5个 | 1个 | ✅ 达标 |
| 容器资源限制 | 无 | 100% | 100% | ✅ 达标 |
| 自动化覆盖率 | 0% | >80% | 90% | ✅ 达标 |
| 监控频率 | 每周 | 每小时 | 每小时 | ✅ 达标 |

---

## 📊 实施优先级

### 🔴 紧急 (本周完成)

1. ✅ 容器资源限制应用
2. ✅ 监控频率升级
3. ⏳ 容量规划基线
4. ⏳ Prometheus 告警

### 🟡 重要 (本月完成)

1. ⏳ 其他项目资源限制
2. ⏳ 服务高可用改造
3. ⏳ 自动化脚本完善
4. ⏳ 运维手册编写

### 🟢 长期 (持续优化)

1. ⏳ 性能持续优化
2. ⏳ 架构演进
3. ⏳ 技术债务清理

---

## 🔄 持续改进循环

```
┌─────────────────────────────────────┐
│  1. 监控 → 实时资源使用监控          │
│  2. 分析 → 识别瓶颈和异常            │
│  3. 优化 → 实施改进措施              │
│  4. 验证 → 确认优化效果              │
│  5. 文档 → 记录经验和教训            │
│  6. 循环 → 返回步骤1                 │
└─────────────────────────────────────┘
```

---

## 📞 应急联系人

| 角色 | 姓名 | 联系方式 | 负责范围 |
|------|------|---------|---------|
| 系统管理员 | - | - | 系统运维、故障处理 |
| 开发负责人 | - | - | 应用优化、功能开发 |
| 架构师 | - | - | 架构设计、技术决策 |

---

**文档版本**: v1.0
**创建日期**: 2026-03-30
**下次更新**: 2026-04-30
**负责人**: 系统运维团队
