# openlist 数据库完整优化指南（使用 /data/sda1）

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

**方案**: 备份到 `/data` (sda1 分区，833GB 可用空间)

---

## 💡 为什么备份到 /data/sda1？

### 优势

| 项目 | 根分区 (/) | 数据分区 (/data) |
|------|------------|------------------|
| 总大小 | 197GB | 916GB |
| 已使用 | 149GB (80%) | 37GB (5%) |
| 可用空间 | 39GB | **833GB** ✅ |
| 能否备份 59GB | ❌ 不能 | ✅ 能 ✅ |

**结论**: `/data` 有充足空间，可以安全备份

---

## 🚀 执行步骤

### 一键执行（推荐）

```bash
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_to_sda1.sh
```

---

## 📋 脚本执行流程

### 第一步：清理磁盘空间（5-10 分钟）

1. ✅ 清理系统日志（7天前）
   - 预计释放：5-10 GB

2. ✅ 清理 APT 缓存
   - 预计释放：1-2 GB

3. ✅ 清理 Docker
   - 预计释放：6-10 GB

4. ✅ 清理用户缓存
   - 预计释放：1-3 GB

**小计释放**: 13-25 GB

### 第二步：完整 VACUUM（15-40 分钟）

1. ✅ **备份数据库到 /data**
   ```bash
   /data/openlist_backup/data.db.backup.YYYYMMDD_HHMMSS
   ```

2. ✅ 清理 WAL 文件

3. ✅ 执行完整 VACUUM
   - 数据库从 59GB → 30-40GB
   - 释放 19-29GB

4. ✅ 优化数据库

5. ✅ **创建优化后备份**
   ```bash
   /data/openlist_backup/data.db.optimized.YYYYMMDD_HHMMSS
   ```

6. ✅ 重启 openlist 服务

---

## 📊 预期效果

| 指标 | 优化前 | 优化后 | 改善 |
|------|--------|--------|------|
| 根分区可用空间 | 39GB | 52-64GB | +13-25GB |
| 数据库大小 | 59GB | 30-40GB | -19-29GB |
| 数据分区使用率 | 5% | ~11% | +6% |

---

## 📁 备份文件位置

```
/data/openlist_backup/
├── data.db.backup.20260330_223311    # 原有备份（13GB）
├── data.db.backup.YYYYMMDD_HHMMSS     # 优化前备份（59GB）
└── data.db.optimized.YYYYMMDD_HHMMSS  # 优化后备份（30-40GB）
```

---

## ⏱️ 预计执行时间

- 清理磁盘空间：5-10 分钟
- 备份数据库：2-5 分钟
- 执行 VACUUM：10-30 分钟
- 优化数据库：5-10 分钟
- **总计：22-55 分钟**

---

## ✅ 执行命令

### 完整流程（推荐）

```bash
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_to_sda1.sh
```

### 仅清理磁盘空间

```bash
sudo bash /home/ai/zhineng-knowledge-system/scripts/cleanup_disk_only.sh
```

---

## 🔍 验证优化结果

### 检查数据库大小

```bash
ls -lh /opt/openlist/data/data.db
```

**预期**: 从 59GB 降至 30-40GB

### 检查备份文件

```bash
ls -lh /data/openlist_backup/
```

**预期**:
- 优化前备份：~59GB
- 优化后备份：~30-40GB

### 检查磁盘空间

```bash
df -h /
df -h /data
```

**预期**: 根分区可用空间增加

### 检查 openlist 服务

```bash
sudo systemctl status openlist
```

**预期**: 服务正常运行

---

## 🔄 回滚方案

如果出现问题，可以从备份恢复：

```bash
# 停止 openlist
sudo systemctl stop openlist

# 恢复备份
sudo cp /data/openlist_backup/data.db.backup.YYYYMMDD_HHMMSS /opt/openlist/data/data.db

# 重启 openlist
sudo systemctl start openlist
```

---

## 📝 后续维护

### 1. 定期清理（每周）

```bash
# 添加到 crontab
0 2 * * 0 /home/ai/zhineng-knowledge-system/scripts/cleanup_disk_only.sh
```

### 2. 定期 VACUUM（每月）

```bash
# 添加到 crontab
0 3 1 * * /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_to_sda1.sh
```

### 3. 清理旧备份（每周）

```bash
# 删除 7 天前的备份
find /data/openlist_backup/ -name "data.db.*" -mtime +7 -delete
```

---

## ⚠️ 重要提示

1. **备份位置**: `/data/openlist_backup/`
2. **备份验证**: 脚本会自动验证 MD5
3. **双重备份**: 同时保留优化前和优化后的备份
4. **服务停止**: VACUUM 期间 openlist 不可用
5. **不要中断**: VACUUM 过程中不要中断

---

## 🎯 准备执行

**立即执行完整优化**：

```bash
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_to_sda1.sh
```

**预计时间**: 22-55 分钟

**预期效果**:
- ✅ 数据库从 59GB 降至 30-40GB
- ✅ 释放 19-29GB 空间
- ✅ 安全备份到 /data
- ✅ 双重备份保护

---

**准备好了吗？执行上面的命令即可开始优化！**
