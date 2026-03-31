#!/bin/bash
# openlist 数据库优化脚本
# 执行 VACUUM 释放空间

set -e

echo "=========================================="
echo "openlist 数据库优化"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 错误: 此脚本需要 root 权限"
    echo "请使用: sudo bash $0"
    exit 1
fi

# 1. 停止 openlist 服务
echo "【1. 停止 openlist 服务】"
if systemctl is-active --quiet openlist; then
    systemctl stop openlist
    echo "✅ openlist 服务已停止"
    sleep 3
else
    echo "⚠️  openlist 服务未运行"
fi
echo ""

# 2. 备份数据库
echo "【2. 备份数据库】"
DB_FILE="/opt/openlist/data/data.db"
BACKUP_FILE="/opt/openlist/data/data.db.backup.$(date +%Y%m%d_%H%M%S)"

if [ -f "$DB_FILE" ]; then
    DB_SIZE=$(du -sh "$DB_FILE" | cut -f1)
    echo "当前数据库大小: $DB_SIZE"

    cp "$DB_FILE" "$BACKUP_FILE"
    echo "✅ 备份已创建: $BACKUP_FILE"
else
    echo "❌ 数据库文件不存在: $DB_FILE"
    exit 1
fi
echo ""

# 3. 清理 WAL 文件
echo "【3. 清理 WAL 文件】"
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

# 4. 执行 VACUUM
echo "【4. 执行 VACUUM】"
echo "这可能需要几分钟时间..."
echo ""

VACUUM_START=$(date +%s)

sqlite3 "$DB_FILE" 'VACUUM;'

VACUUM_END=$(date +%s)
VACUUM_DURATION=$((VACUUM_END - VACUUM_START))

NEW_DB_SIZE=$(du -sh "$DB_FILE" | cut -f1)
echo "✅ VACUUM 完成 (耗时: ${VACUUM_DURATION}秒)"
echo "新数据库大小: $NEW_DB_SIZE"
echo ""

# 5. 重启 openlist 服务
echo "【5. 重启 openlist 服务】"
systemctl start openlist
sleep 3

if systemctl is-active --quiet openlist; then
    echo "✅ openlist 服务已启动"
else
    echo "❌ openlist 服务启动失败"
    echo "请检查日志: sudo journalctl -u openlist -n 50"
    exit 1
fi
echo ""

# 6. 显示结果
echo "【6. 优化结果】"
echo "原始大小: $DB_SIZE"
echo "当前大小: $NEW_DB_SIZE"
echo "释放空间: $(echo $DB_SIZE | awk '{print $1}' | sed 's/G/*1024M/') → $(echo $NEW_DB_SIZE | awk '{print $1}')"
echo ""
echo "✅ openlist 数据库优化完成！"
echo ""
echo "=========================================="
echo "建议："
echo "1. 设置定期 VACUUM 任务 (每周一次)"
echo "2. 监控数据库大小增长"
echo "3. 如有必要，减少索引的云盘数量"
echo "=========================================="
