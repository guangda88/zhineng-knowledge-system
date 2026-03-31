# 🛡️ 安全防护长效机制

**创建日期**: 2026-03-31
**目标**: 杜绝安全问题和资源危机再次发生

---

## 📊 问题回顾

### 近期发生的P0危机

1. **内存危机**: 96% 使用率，仅剩1GB可用
2. **磁盘危机**: 86% 使用率，VACUUM失败
3. **安全漏洞**: 7个高危问题（硬编码密码、CORS错误等）

### 根本原因

| 问题 | 技术根因 | 管理根因 |
|------|----------|----------|
| 内存危机 | 容器无资源限制 | 缺少监控 |
| 磁盘危机 | 大文件在根分区 | 缺少容量规划 |
| 安全漏洞 | 开发流程缺失 | 无安全审查 |

---

## 🎯 长效防护机制

### 1. 自动化安全检查（技术层）

#### 1.1 Pre-commit Hook

```bash
# 安装 pre-commit hook
cp .git/hooks/pre-commit.security .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

**检查项**:
- ✅ 硬编码密码检测
- ✅ 危险CORS配置检测
- ✅ 裸异常处理检测
- ✅ SQL注入风险检测
- ✅ 容器资源限制验证

**执行时机**: 每次 `git commit` 前自动运行

#### 1.2 CI/CD 集成

```yaml
# .github/workflows/security-check.yml
name: Security Check

on: [push, pull_request]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run security check
        run: |
          bash scripts/security_check.sh
          exit $?
```

**阻止机制**: 检查失败则阻止合并

---

### 2. 资源监控与告警（运维层）

#### 2.1 实时监控配置

```bash
# 已配置的监控任务
*/10 * * * * /home/ai/zhineng-knowledge-system/scripts/emergency_memory_recovery.sh
0 * * * * /home/ai/zhineng-knowledge-system/scripts/monitor_disk.sh
*/30 * * * * /home/ai/zhineng-knowledge-system/scripts/monitor_docker.sh
0 0 * * * /home/ai/zhineng-knowledge-system/scripts/daily_health_check.sh
```

**监控指标**:
- 内存使用率（阈值: 85%警告, 90%紧急）
- 磁盘使用率（阈值: 80%警告, 85%紧急）
- 容器资源占用（阈值: 限制的90%）
- 僵尸进程数量（阈值: >10个）

#### 2.2 Prometheus 告警规则

```yaml
# monitoring/prometheus/alerts.yml
groups:
  - name: resource_alerts
    rules:
      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.85
        for: 5m
        annotations:
          summary: "内存使用率超过85%"

      - alert: CriticalMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.90
        for: 2m
        annotations:
          summary: "内存使用率超过90% - 紧急"

      - alert: HighDiskUsage
        expr: (node_filesystem_size_bytes{mountpoint="/"} - node_filesystem_avail_bytes{mountpoint="/"}) / node_filesystem_size_bytes{mountpoint="/"} > 0.85
        for: 5m
        annotations:
          summary: "根分区使用率超过85%"
```

---

### 3. 开发流程规范（管理层）

#### 3.1 代码审查检查清单

**安全检查**:
- [ ] 无硬编码密码/密钥
- [ ] CORS配置使用白名单
- [ ] 异常处理完善（无裸异常）
- [ ] 输入验证充分
- [ ] SQL查询使用参数化
- [ ] 敏感信息不记录到日志

**资源检查**:
- [ ] 新服务配置资源限制
- [ ] 内存使用合理（有基准测试）
- [ ] 日志文件有轮转配置
- [ ] 临时文件有清理机制

#### 3.2 部署前验证流程

```bash
# 1. 运行安全检查
bash scripts/security_check.sh

# 2. 运行测试
pytest tests/ -v --cov=backend

# 3. 检查资源配置
docker-compose config | grep -A 5 "deploy:"
  # 验证所有服务都有资源限制

# 4. 容量评估
bash scripts/create_capacity_baseline.sh
  # 对比当前使用与基线

# 5. 健康检查
bash scripts/health_check.sh
```

---

### 4. 容量规划与管理（规划层）

#### 4.1 容量基线

```bash
# 创建容量基线
bash scripts/create_capacity_baseline.sh
```

**基线内容**:
- 各服务资源使用情况
- 数据库大小趋势
- 日志增长速度
- 磁盘空间预测

#### 4.2 容量规划决策树

```
当前资源使用率:
  ↓
< 60%: 正常运行
  ↓
60-80%: 开始规划扩容
  ↓
80-90%: 立即扩容（P1）
  ↓
> 90%: 紧急扩容（P0）
```

#### 4.3 扩容流程

1. **评估**: 分析资源使用趋势
2. **方案**: 硬件扩容 vs 架构优化
3. **测试**: 在测试环境验证
4. **执行**: 在低峰时段实施
5. **验证**: 确认效果
6. **更新**: 更新容量基线

---

### 5. 应急响应机制（应急层）

#### 5.1 P0 事件自动响应

```python
# backend/core/urgency_guard.py
class UrgencyGuard:
    """紧急状态守卫 - 自动拦截非紧急操作"""

    P0_TRIGGERS = {
        "memory_critical": 90,  # 内存使用率 > 90%
        "disk_full": 85,        # 磁盘使用率 > 85%
        "service_down": False,  # 核心服务停止
    }

    def is_p0_emergency(self) -> bool:
        """检查是否处于P0紧急状态"""
        checks = [
            self._check_memory(),
            self._check_disk(),
            self._check_services(),
        ]
        return any(checks)

    def _check_memory(self) -> bool:
        """检查内存使用率"""
        import psutil
        usage = psutil.virtual_memory().percent
        return usage > self.P0_TRIGGERS["memory_critical"]

    def block_non_urgent_actions(self, action: str) -> bool:
        """拦截非紧急操作"""
        if self.is_p0_emergency():
            allowed = ["fix_urgent_issue", "restart_service", "cleanup_cache"]
            if action not in allowed:
                raise P0EmergencyError(
                    f"系统处于P0紧急状态，仅允许紧急操作。当前操作被拒绝: {action}"
                )
                return True
        return False
```

#### 5.2 自动恢复脚本

```bash
# scripts/emergency_memory_recovery.sh
THRESHOLD=85
MEMORY_USAGE=$(free | awk '/^Mem:/ {printf("%.0f", $3/$2*100)}')

if [ "$MEMORY_USAGE" -gt "$THRESHOLD" ]; then
    # 1. 停止非核心容器
    docker stop $(docker ps -q --filter "name=github-recommender")

    # 2. 清理Docker缓存
    docker system prune -f --volumes

    # 3. 清理僵尸进程
    ./scripts/cleanup_zombies.sh

    # 4. 清理系统缓存
    sudo sysctl -w vm.drop_caches=3
fi
```

---

### 6. 安全培训与意识（人员层）

#### 6.1 开发者安全培训

**必修内容**:
1. OWASP Top 10 安全风险
2. 安全编码规范
3. 密码管理最佳实践
4. API安全设计
5. 容器安全配置

**培训方式**:
- 新人入职培训
- 每季度安全讲座
- 安全案例分析

#### 6.2 安全意识提升

**定期活动**:
- 每月安全简报
- 季度安全演习
- 年度安全评估

---

## 🔄 持续改进机制

### 1. 定期审查

```bash
# 每周资源审查
0 9 * * 1 /home/ai/zhineng-knowledge-system/scripts/weekly_capacity_review.sh

# 每月安全审查
0 9 1 * * /home/ai/zhineng-knowledge-system/scripts/monthly_security_review.sh

# 每季度渗透测试
# 使用专业工具或第三方服务
```

### 2. 事件回顾

**每次P0事件后**:
1. 根因分析（5 Whys）
2. 制定改进措施
3. 更新检查清单
4. 培训相关人员
5. 更新文档

### 3. 技术债务管理

**每季度评估**:
- 安全漏洞修复进度
- 代码重构计划
- 架构优化建议
- 工具升级计划

---

## 📋 检查清单总览

### 开发阶段

- [ ] 代码符合安全规范
- [ ] 通过所有测试
- [ ] 资源使用评估
- [ ] 代码审查通过

### 提交阶段

- [ ] Pre-commit hook 检查通过
- [ ] 安全扫描无错误
- [ ] 敏感信息未提交

### 部署阶段

- [ ] 环境变量配置正确
- [ ] 容器资源限制已设置
- [ ] 监控告警已配置
- [ ] 回滚方案已准备

### 运行阶段

- [ ] 监控指标正常
- [ ] 日志正常输出
- [ ] 资源使用在基线内
- [ ] 无错误日志

---

## 🎯 成功指标

### 安全指标

| 指标 | 目标 | 当前 |
|------|------|------|
| 高危漏洞 | 0 | 7 |
| 硬编码密码 | 0 | 1 |
| 安全扫描通过率 | 100% | ? |
| 安全培训覆盖率 | 100% | ? |

### 资源指标

| 指标 | 目标 | 当前 |
|------|------|------|
| 内存使用率 | < 70% | 96% |
| 磁盘使用率 | < 70% | 38% ✅ |
| 容器资源限制覆盖率 | 100% | 100% ✅ |
| P0事件频率 | 0/年 | 2/月 |

### 流程指标

| 指标 | 目标 | 当前 |
|------|------|------|
| Pre-commit hook启用率 | 100% | ? |
| 代码审查覆盖率 | 100% | ? |
| 容量规划周期 | 季度 | ? |

---

## 📝 实施时间表

### 第1周（立即执行）

- [x] 修复7个高危安全漏洞
- [x] 添加容器资源限制
- [x] 创建安全检查脚本
- [ ] 安装pre-commit hook
- [ ] 配置监控告警

### 第2-4周

- [ ] 实施JWT认证
- [ ] 完善日志脱敏
- [ ] 创建容量基线
- [ ] 开发者安全培训

### 第2-3月

- [ ] 建立CI/CD安全检查
- [ ] 实施自动化测试
- [ ] 完善文档
- [ ] 定期安全演习

---

## 🚀 立即行动

### 1. 安装Pre-commit Hook

```bash
cp .git/hooks/pre-commit.security .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### 2. 运行安全检查

```bash
bash scripts/security_check.sh
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入真实值
```

### 4. 验证监控

```bash
crontab -l | grep -E "emergency_memory|monitor_disk"
```

---

**文档版本**: 1.0
**创建时间**: 2026-03-31
**下次审查**: 每月更新
