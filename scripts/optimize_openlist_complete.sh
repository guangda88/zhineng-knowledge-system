#!/bin/bash
# openlist 完整优化流程
# 1. 清理磁盘空间
# 2. 执行完整 VACUUM

set -e

echo "=========================================="
echo "openlist 完整优化流程"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 错误: 此脚本需要 root 权限"
    echo "请使用: sudo bash $0"
    exit 1
fi

# ========== 第一步：清理磁盘空间 ==========

echo "=========================================="
echo "第一步：清理磁盘空间"
echo "=========================================="
echo ""

echo "【1.1 清理前的磁盘使用情况】"
df -h /
echo ""

echo "【1.2 清理系统日志】"
echo "清理前日志占用："
sudo journalctl --disk-usage

echo ""
echo "正在清理 7 天前的日志..."
sudo journalctl --vacuum-time=7d

echo ""
echo "清理后日志占用："
sudo journalctl --disk-usage
echo ""

echo "【1.3 清理 APT 缓存】"
echo "清理前 APT 缓存："
du -sh /var/cache/apt/archives 2>/dev/null || echo "无法计算"

sudo apt clean
sudo apt autoremove -y

echo ""
echo "清理后 APT 缓存："
du -sh /var/cache/apt/archives 2>/dev/null || echo "无法计算"
echo ""

echo "【1.4 清理 Docker】"
echo "清理前 Docker 占用："
docker system df

echo ""
echo "正在清理 Docker（悬空镜像、未使用的容器、未使用的卷）..."
docker system prune -a --volumes -f

echo ""
echo "清理后 Docker 占用："
docker system df
echo ""

echo "【1.5 清理用户缓存】"
echo "清理用户缓存..."
rm -rf ~/.cache/thumbnails/*
rm -rf ~/.cache/pip/*
rm -rf ~/.cache/node/*
rm -rf ~/.cache/mozilla/firefox/*/cache2
echo "✅ 用户缓存已清理"
echo ""

echo "【1.6 查找大文件（可选）】"
echo "大于 1GB 的文件："
find / -type f -size +1G -exec ls -lh {} \; 2>/dev/null | awk '{print $5, $9}' | head -10
echo ""

echo "【1.7 清理后的磁盘使用情况】"
df -h /
echo ""

AVAILABLE_SPACE=$(df / | tail -1 | awk '{print $4}')
echo "✅ 当前可用空间: $AVAILABLE_SPACE"
echo ""

# 检查是否有足够空间
AVAILABLE_GB=$(df / | tail -1 | awk '{print int($4)}')
if [ $AVAILABLE_GB -lt 60 ]; then
    echo "⚠️  警告: 可用空间仍然不足 60GB"
    echo "建议继续清理或手动删除不需要的文件"
    echo ""
    read -p "是否继续执行 VACUUM？(y/n): " continue_confirm
    if [ "$continue_confirm" != "y" ] && [ "$continue_confirm" != "Y" ]; then
        echo "❌ 用户取消操作"
        exit 1
    fi
fi

# ========== 第二步：执行完整 VACUUM ==========

echo ""
echo "=========================================="
echo "第二步：执行 openlist 完整优化"
echo "=========================================="
echo ""

echo "【2.1 确认 openlist 服务状态】"
if systemctl is-active --quiet openlist; then
    echo "停止 openlist 服务..."
    sudo systemctl stop openlist
    sleep 3
    echo "✅ openlist 服务已停止"
else
    echo "✅ openlist 服务未运行（可以继续）"
fi
echo ""

echo "【2.2 备份数据库】"
DB_FILE="/opt/openlist/data/data.db"
BACKUP_FILE="/opt/openlist/data/data.db.backup.$(date +%Y%m%d_%H%M%S)"

DB_SIZE=$(du -sh "$DB_FILE" | cut -f1)
echo "当前数据库大小: $DB_SIZE"

echo "正在创建备份: $BACKUP_FILE"
cp "$DB_FILE" "$BACKUP_FILE"
BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
echo "✅ 备份已创建: $BACKUP_FILE ($BACKUP_SIZE)"
echo ""

echo "【2.3 清理 WAL 文件】"
WAL_FILE="/opt/openlist/data/data.db-wal"
SHM_FILE="/opt/openlist/data/data.db-shm"

if [ -f "$WAL_FILE" ]; then
    WAL_SIZE=$(du -sh "$WAL_FILE" | cut -f1)
    rm -f "$WAL_FILE"
    echo "✅ WAL 文件已删除 (大小: $WAL_SIZE)"
else
    echo "⚠️  WAL 文件不存在"
fi

if [ -f "$SHM_FILE" ]; then
    rm -f "$SHM_FILE"
    echo "✅ SHM 文件已删除"
else
    echo "⚠️  SHM 文件不存在"
fi
echo ""

echo "【2.4 执行 VACUUM】"
echo "⏳ 这可能需要 10-30 分钟，请耐心等待..."
echo ""

VACUUM_START=$(date +%s)

sqlite3 "$DB_FILE" 'VACUUM;'

VACUUM_END=$(date +%s)
VACUUM_DURATION=$((VACUUM_END - VACUUM_START))
VACUUM_MINUTES=$((VACUUM_DURATION / 60))

NEW_DB_SIZE=$(du -sh "$DB_FILE" | cut -f1)
echo "✅ VACUUM 完成 (耗时: ${VACUUM_MINUTES}分钟)"
echo "新数据库大小: $NEW_DB_SIZE"
echo ""

echo "【2.5 优化数据库】"
echo "正在执行 PRAGMA optimize..."
sqlite3 "$DB_FILE" "PRAGMA optimize;"
echo "✅ PRAGMA optimize 完成"
echo ""

echo "正在分析数据库..."
sqlite3 "$DB_FILE" "ANALYZE;"
echo "✅ ANALYZE 完成"
echo ""

echo "【2.6 重启 openlist 服务】"
read -p "是否重启 openlist 服务？(y/n): " restart_confirm

if [ "$restart_confirm" = "y" ] || [ "$restart_confirm" = "Y" ]; then
    sudo systemctl start openlist
    sleep 3

    if systemctl is-active --quiet openlist; then
        echo "✅ openlist 服务已启动"
    else
        echo "❌ openlist 服务启动失败"
        echo "请检查日志: sudo journalctl -u openlist -n 50"
    fi
else
    echo "⚠️  openlist 服务未启动"
    echo "稍后可以手动启动: sudo systemctl start openlist"
fi
echo ""

# ========== 总结 ==========

echo "=========================================="
echo "✅ openlist 完整优化完成！"
echo "=========================================="
echo ""
echo "优化结果："
echo "原始大小: $DB_SIZE"
echo "当前大小: $NEW_DB_SIZE"
echo "耗时: ${VACUUM_MINUTES}分钟"
echo ""
echo "磁盘使用情况："
df -h / | tail -1
echo ""
echo "备份文件位置："
ls -lh /opt/openlist/data/data.db.backup.* 2>/dev/null | tail -3
echo ""
echo "=========================================="
echo "后续建议："
echo "1. 设置定期 VACUUM 任务（每周一次）"
echo "2. 监控数据库大小增长"
echo "3. 如有必要，减少索引的云盘数量"
echo "4. 定期清理系统日志和 Docker 镜像"
echo "=========================================="
