# openlist 数据库优化指南（磁盘空间不足）

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

**问题**: 根分区只有 39GB 可用空间，无法备份 59GB 数据库

**当前状态**:
- 数据库大小: 59GB
- 可用空间: 39GB
- 已有备份: 13GB (data.db.backup.20260330_223311)

---

## 🚀 解决方案

### 方案 1: 快速优化（推荐，立即可执行）

**特点**: 跳过备份，执行轻量级优化

**执行命令**:
```bash
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_db_quick.sh
```

**效果**:
- ✅ 清理 WAL 文件（可能释放数 GB）
- ✅ 优化数据库结构
- ✅ 更新统计信息
- ⚠️  不会大幅减小数据库大小（因为没有完整 VACUUM）

**适用场景**:
- 磁盘空间不足
- 需要立即优化
- 已有备份文件

---

### 方案 2: 释放空间后完整优化（推荐最佳效果）

**步骤 1: 释放磁盘空间**

```bash
# 查找可以删除的大文件
sudo du -sh /var/log/* | sort -hr | head -20

# 清理系统日志
sudo journalctl --vacuum-time=7d

# 清理 apt 缓存
sudo apt clean
sudo apt autoremove

# 清理 Docker 镜像和容器
docker system prune -a

# 查找大文件
sudo find / -size +1G -exec ls -lh {} \; 2>/dev/null | head -20
```

**步骤 2: 删除旧备份（如果需要）**

```bash
# 删除旧的备份文件（13GB）
sudo rm /opt/openlist/data/data.db.backup.20260330_223311

# 现在有 52GB 可用空间
```

**步骤 3: 执行完整 VACUUM**

```bash
# 停止 openlist
sudo systemctl stop openlist

# 备份数据库（现在有足够空间）
sudo cp /opt/openlist/data/data.db /opt/openlist/data/data.db.backup.$(date +%Y%m%d_%H%M%S)

# 执行 VACUUM（可能需要 10-30 分钟）
sudo sqlite3 /opt/openlist/data/data.db 'VACUUM;'

# 重启 openlist
sudo systemctl start openlist
```

**预期效果**:
- 数据库从 59GB 降至 30-40GB
- 释放 20-30GB 空间

---

### 方案 3: 外部存储备份（安全但需要外部设备）

**步骤**:

```bash
# 挂载外部存储
sudo mount /dev/sdX1 /mnt/external

# 备份到外部存储
sudo cp /opt/openlist/data/data.db /mnt/external/data.db.backup.$(date +%Y%m%d_%H%M%S)

# 执行 VACUUM
sudo sqlite3 /opt/openlist/data/data.db 'VACUUM;'

# 重启 openlist
sudo systemctl start openlist
```

---

## 📊 当前磁盘使用情况

```
根分区 (/dev/mapper/ubuntu--vg-ubuntu--lv):
  总大小: 197G
  已使用: 149G
  可用空间: 39G (80% 使用率)
```

**建议**: 至少释放 20GB 空间，使使用率降至 70% 以下

---

## 🎯 立即可执行的命令

### 选项 A: 快速优化（无需释放空间）

```bash
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_db_quick.sh
```

**优点**:
- ✅ 立即可执行
- ✅ 清理 WAL 文件
- ✅ 优化性能

**缺点**:
- ❌ 不会大幅减小文件大小

---

### 选项 B: 清理日志后完整优化

```bash
# 1. 清理系统日志（约 5-10GB）
sudo journalctl --vacuum-time=3d
sudo journalctl --vacuum-size=1G

# 2. 清理 Docker（约 5-10GB）
docker system prune -a --volumes

# 3. 检查可用空间
df -h /

# 4. 如果有 60GB+ 空间，执行完整优化
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_db.sh
```

**优点**:
- ✅ 完整 VACUUM
- ✅ 最大化释放空间
- ✅ 有备份保护

**缺点**:
- ❌ 需要先释放空间
- ❌ 耗时较长（10-30 分钟）

---

## ⚠️ 重要提示

1. **备份已存在**:
   - `/opt/openlist/data/data.db.backup.20260330_223311` (13GB)
   - 可以安全地跳过备份步骤

2. **服务已停止**:
   - openlist 服务未运行
   - 可以安全地优化数据库

3. **优化后效果**:
   - 快速优化: 清理 WAL，性能提升
   - 完整 VACUUM: 释放 20-30GB 空间

---

## 🚀 推荐执行顺序

### 立即执行（今天）:

```bash
# 方案 A: 快速优化
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_db_quick.sh
```

### 本周执行（有充足时间时）:

```bash
# 方案 B: 完整优化
# 1. 清理空间
sudo journalctl --vacuum-time=3d
docker system prune -a --volumes

# 2. 执行完整 VACUUM
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_db.sh
```

---

**建议**: 先执行快速优化（方案 A），确保 openlist 可以正常运行，然后在周末或维护窗口执行完整优化（方案 B）。
