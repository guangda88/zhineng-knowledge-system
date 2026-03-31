# openlist 完整优化执行指南

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

**选项 B**: 清理空间后执行完整 VACUUM

---

## 📋 执行步骤

### 一键执行（推荐）

```bash
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_complete.sh
```

**脚本会自动执行**:
1. ✅ 清理系统日志（7天前）
2. ✅ 清理 APT 缓存
3. ✅ 清理 Docker（悬空镜像、未使用的卷）
4. ✅ 清理用户缓存
5. ✅ 备份数据库
6. ✅ 清理 WAL 文件
7. ✅ 执行完整 VACUUM
8. ✅ 优化数据库
9. ✅ 重启 openlist 服务

---

## 📊 预期清理效果

| 清理项 | 预计释放空间 |
|--------|------------|
| 系统日志（7天前） | 5-10 GB |
| APT 缓存 | 1-2 GB |
| Docker（悬空镜像等） | 6-10 GB |
| 用户缓存 | 1-3 GB |
| **总计** | **13-25 GB** |

加上原有的 39GB 可用空间，清理后应该有 **52-64GB** 可用空间，足够执行完整 VACUUM。

---

## ⏱️ 预计执行时间

| 步骤 | 预计时间 |
|------|---------|
| 清理磁盘空间 | 5-10 分钟 |
| 备份数据库 | 2-5 分钟 |
| 执行 VACUUM | 10-30 分钟 |
| 优化数据库 | 5-10 分钟 |
| **总计** | **22-55 分钟** |

---

## 🚀 手动执行（如果脚本失败）

### 步骤 1: 清理系统日志

```bash
# 查看日志占用
sudo journalctl --disk-usage

# 清理 7 天前的日志
sudo journalctl --vacuum-time=7d

# 或者限制日志大小为 1GB
sudo journalctl --vacuum-size=1G
```

### 步骤 2: 清理 APT 缓存

```bash
sudo apt clean
sudo apt autoremove -y
```

### 步骤 3: 清理 Docker

```bash
# 查看 Docker 占用
docker system df

# 清理悬空镜像、未使用的容器、未使用的卷、构建缓存
docker system prune -a --volumes -f
```

### 步骤 4: 清理用户缓存

```bash
# 清理缩略图
rm -rf ~/.cache/thumbnails/*

# 清理 pip 缓存
rm -rf ~/.cache/pip/*

# 清理 Node.js 缓存
rm -rf ~/.cache/node/*
```

### 步骤 5: 检查可用空间

```bash
df -h /
```

确保至少有 **60GB** 可用空间。

### 步骤 6: 执行完整 VACUUM

```bash
# 停止 openlist
sudo systemctl stop openlist

# 备份数据库
sudo cp /opt/openlist/data/data.db /opt/openlist/data/data.db.backup.$(date +%Y%m%d_%H%M%S)

# 清理 WAL 文件
sudo rm -f /opt/openlist/data/data.db-wal
sudo rm -f /opt/openlist/data/data.db-shm

# 执行 VACUUM（可能需要 10-30 分钟）
sudo sqlite3 /opt/openlist/data/data.db 'VACUUM;'

# 优化数据库
sudo sqlite3 /opt/openlist/data/data.db 'PRAGMA optimize;'
sudo sqlite3 /opt/openlist/data/data.db 'ANALYZE;'

# 重启 openlist
sudo systemctl start openlist
```

---

## ✅ 验证优化结果

### 检查数据库大小

```bash
ls -lh /opt/openlist/data/data.db
```

**预期**: 从 59GB 降至 30-40GB

### 检查磁盘空间

```bash
df -h /
```

**预期**: 有更多可用空间

### 检查 openlist 服务

```bash
sudo systemctl status openlist
```

**预期**: 服务正常运行

---

## ⚠️ 重要提示

1. **执行时间**: 完整流程需要 22-55 分钟
2. **不要中断**: VACUUM 过程中不要中断，可能导致数据库损坏
3. **备份已创建**: 脚本会自动创建备份
4. **服务停止**: 优化期间 openlist 服务不可用

---

## 🔄 如果出现错误

### 错误 1: 磁盘空间仍然不足

```bash
# 查找大文件
sudo find / -type f -size +1G -exec ls -lh {} \; 2>/dev/null | head -20

# 删除不需要的文件（请谨慎操作）
```

### 错误 2: VACUUM 过程中断

```bash
# 恢复备份
sudo systemctl stop openlist
sudo rm /opt/openlist/data/data.db
sudo cp /opt/openlist/data/data.db.backup.YYYYMMDD_HHMMSS /opt/openlist/data/data.db
sudo systemctl start openlist
```

### 错误 3: openlist 服务启动失败

```bash
# 查看错误日志
sudo journalctl -u openlist -n 50

# 检查数据库文件
ls -lh /opt/openlist/data/data.db*
```

---

## 📞 获取帮助

如果遇到问题：
1. 查看日志: `sudo journalctl -u openlist -n 100`
2. 检查数据库: `sqlite3 /opt/openlist/data/data.db 'PRAGMA integrity_check;'`
3. 查看磁盘: `df -h /`

---

**准备就绪？执行命令：**

```bash
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_complete.sh
```
