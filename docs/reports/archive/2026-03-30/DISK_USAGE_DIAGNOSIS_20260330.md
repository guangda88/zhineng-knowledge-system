# 硬盘使用率升高问题诊断报告

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

**诊断时间**: 2026-03-30 18:47
**诊断人**: Claude Code
**问题**: 硬盘使用率升高很快

---

## 📊 当前磁盘使用情况

### 根分区状态
```
文件系统: /dev/mapper/ubuntu--vg-ubuntu--lv
总容量: 197GB
已使用: 137GB (73%)
可用:   51GB
```

### 磁盘占用 Top 5 目录

| 目录 | 大小 | 占比 | 说明 |
|------|------|------|------|
| **/opt** | **60GB** | **44%** | 🔴 主要问题 |
| /data | 24GB | 18% | 数据目录 |
| /home | 23GB | 17% | 用户目录 |
| /usr | 21GB | 15% | 系统程序 |
| /var | 11GB | 8% | 日志和运行时数据 |

---

## 🔍 问题根因分析

### 🔴 主要问题：openlist 数据库占用 59GB

**问题详情**：
```bash
/opt/openlist/data/data.db    59GB  # 主数据库文件
/opt/openlist/data/data.db-wal 40KB  # Write-Ahead Log
/opt/openlist/data/data.db-shm 32KB  # 共享内存
```

**原因分析**：

1. **数据库持续增长**
   - openlist 作为多云存储管理服务
   - 索引了大量云盘文件（百度网盘、阿里云盘等）
   - 数据库包含了所有文件的元数据和索引

2. **WAL 文件未清理**
   - `data.db-wal` 是 Write-Ahead Log，记录数据库变更
   - 正常情况下会在检查点后清理
   - 但文件很小 (40KB)，不是主要问题

3. **未进行数据库优化**
   - SQLite 数据库需要定期 VACUUM 操作
   - VACUUM 可以回收已删除数据占用的空间
   - 长期未执行导致数据库文件持续增长

---

### 🟡 次要问题：systemd journal 占用 4GB

```bash
/var/log/journal/  4.0GB  # systemd 日志
```

**原因**：
- systemd journal 默认不限制日志大小
- 保留了大量的历史日志
- 没有配置日志轮转

---

### 🟢 其他占用

| 项目 | 大小 | 说明 |
|------|------|------|
| npm 缓存 | 511MB | `~/.npm` |
| Docker 镜像 | 6.8GB | 可清理部分 |
| 系统日志 | 8.5GB | `/var/log` |
| 临时文件 | 1.2GB | `/tmp` |

---

## 🛠️ 解决方案

### 方案1：清理 systemd journal（立即执行）

**效果**: 释放约 2-3GB

```bash
# 清理超过7天的journal
sudo journalctl --vacuum-time=7d

# 或者限制journal最大大小
sudo journalctl --vacuum-size=1G

# 设置持久化限制
sudo nano /etc/systemd/journald.conf
# 添加：
# SystemMaxUse=1G
# SystemMaxFiles=100
```

---

### 方案2：清理 openlist 数据库（谨慎操作）

**⚠️ 警告**: 这会影响 openlist 服务，需要停机维护

**效果**: 可释放 10-30GB

**步骤**：

1. **停止服务**
   ```bash
   sudo systemctl stop openlist
   ```

2. **备份数据库**
   ```bash
   sudo cp /opt/openlist/data/data.db /opt/openlist/data/data.db.backup.$(date +%Y%m%d)
   ```

3. **清理 WAL 和 SHM 文件**
   ```bash
   sudo rm -f /opt/openlist/data/data.db-wal
   sudo rm -f /opt/openlist/data/data.db-shm
   ```

4. **执行数据库 VACUUM**
   ```bash
   # 安装 sqlite3
   sudo apt-get install sqlite3

   # 执行 VACUUM (可能需要几个小时)
   sudo sqlite3 /opt/openlist/data/data.db 'VACUUM;'
   ```

5. **重启服务**
   ```bash
   sudo systemctl start openlist
   ```

**注意**：
- ⚠️ VACUUM 操作可能需要几个小时（59GB的数据库）
- ⚠️ 在此期间 openlist 服务不可用
- ⚠️ 建议在低峰时段执行

---

### 方案3：定期清理脚本（推荐）

我已经创建了自动化清理脚本：

```bash
# 立即执行清理
./scripts/cleanup_disk_space.sh

# 查看 openlist 数据库状态
./scripts/maintain_openlist_db.sh

# 添加到定期任务（每月执行一次）
0 0 1 * * /home/ai/zhineng-knowledge-system/scripts/cleanup_disk_space.sh >> logs/cleanup_monthly.log 2>&1
```

---

### 方案4：配置日志轮转（预防）

**systemd journal 配置**：
```bash
sudo nano /etc/systemd/journald.conf
```

添加：
```ini
[Journal]
SystemMaxUse=1G
SystemMaxFiles=100
RuntimeMaxUse=100M
```

**重启 journald**：
```bash
sudo systemctl restart systemd-journald
```

---

## 📋 推荐执行步骤

### 立即执行（安全操作）

```bash
# 1. 清理 systemd journal (安全)
sudo journalctl --vacuum-time=7d

# 2. 清理 npm 缓存 (安全)
npm cache clean --force

# 3. 清理 Docker 未使用资源 (安全)
docker system prune -f

# 4. 清理临时文件 (安全)
sudo find /tmp -type f -atime +7 -delete

# 5. 验证效果
df -h
```

### 计划执行（需要维护窗口）

```bash
# 查看 openlist 维护脚本
./scripts/maintain_openlist_db.sh

# 根据建议决定是否执行数据库 VACUUM
# 注意：需要停机维护，可能需要几个小时
```

---

## 📊 预期效果

| 操作 | 释放空间 | 风险 | 建议时间 |
|------|---------|------|---------|
| 清理 journal | 2-3GB | 低 | 立即 ✅ |
| 清理 npm 缓存 | 500MB | 低 | 立即 ✅ |
| 清理 Docker | 1-2GB | 低 | 立即 ✅ |
| 清理临时文件 | 500MB | 低 | 立即 ✅ |
| openlist VACUUM | 10-30GB | **高** | 维护窗口 ⚠️ |
| **总计** | **14-36GB** | - | - |

---

## ⚠️ 重要提示

1. **openlist 数据库是主要问题源头**
   - 占用 59GB 空间
   - 需要停机维护
   - 建议在低峰时段执行 VACUUM

2. **定期维护很重要**
   - 建议每月执行一次清理脚本
   - 配置 journal 日志轮转
   - 监控数据库增长趋势

3. **预防措施**
   - 配置 openlist 定期数据清理
   - 限制索引的文件数量
   - 考虑归档旧数据

---

## 📅 后续建议

### 短期（本周）
1. ✅ 执行安全清理操作
2. ⏳ 配置 journal 日志轮转
3. ⏳ 评估 openlist 数据维护时机

### 中期（本月）
1. ⏳ 执行 openlist 数据库 VACUUM
2. ⏳ 优化 openlist 配置
3. ⏳ 建立定期清理机制

### 长期（持续）
1. ⏳ 监控磁盘使用趋势
2. ⏳ 设置容量告警（>80%）
3. ⏳ 考虑数据归档策略

---

**立即执行安全的清理操作可以释放 4-6GB 空间！** 🚀

**需要 openlist 数据库维护吗？我可以帮你规划维护窗口。**
