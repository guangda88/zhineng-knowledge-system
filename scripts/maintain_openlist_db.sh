#!/bin/bash
# openlist 数据库维护脚本
# 用于清理和优化 openlist 的数据库

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="logs/openlist_db_maintenance_$TIMESTAMP.log"

echo "==========================================" | tee "$LOG_FILE"
echo "openlist 数据库维护" | tee -a "$LOG_FILE"
echo "时间: $TIMESTAMP" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 检查数据库文件大小
echo "【数据库文件状态】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
DB_FILE="/opt/openlist/data/data.db"
DB_WAL="/opt/openlist/data/data.db-wal"
DB_SHM="/opt/openlist/data/data.db-shm"

if [ -f "$DB_FILE" ]; then
    DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
    echo "数据库文件: $DB_SIZE" | tee -a "$LOG_FILE"
fi

if [ -f "$DB_WAL" ]; then
    WAL_SIZE=$(du -h "$DB_WAL" | cut -f1)
    echo "WAL 文件: $WAL_SIZE" | tee -a "$LOG_FILE"
fi

if [ -f "$DB_SHM" ]; then
    SHM_SIZE=$(du -h "$DB_SHM" | cut -f1)
    echo "SHM 文件: $SHM_SIZE" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"

# 检查 openlist 服务状态
echo "【openlist 服务状态】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
if systemctl is-active --quiet openlist; then
    echo "✅ openlist 服务正在运行" | tee -a "$LOG_FILE"

    # 获取 openlist 统计信息
    echo "" | tee -a "$LOG_FILE"
    echo "【数据库统计信息】" | tee -a "$LOG_FILE"
    echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
    # 这里可以调用 openlist API 获取统计信息
    echo "提示: 检查 openlist Web 界面查看详细统计" | tee -a "$LOG_FILE"
else
    echo "⚠️  openlist 服务未运行" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 建议的维护操作
echo "【建议的维护操作】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 检查是否需要清理
TOTAL_SIZE=$(du -sb /opt/openlist/data 2>/dev/null | cut -f1)
TOTAL_SIZE_GB=$((TOTAL_SIZE / 1024 / 1024 / 1024))

if [ $TOTAL_SIZE_GB -gt 50 ]; then
    echo "⚠️  openlist 数据目录占用超过 50GB: ${TOTAL_SIZE_GB}GB" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    echo "建议操作：" | tee -a "$LOG_FILE"
    echo "  1. 检查是否有大量无效的文件索引" | tee -a "$LOG_FILE"
    echo "  2. 清理已删除但未扫描的文件记录" | tee -a "$LOG_FILE"
    echo "  3. 优化数据库 (VACUUM)" | tee -a "$LOG_FILE"
    echo "  4. 考虑删除不需要的存储账号" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    echo "执行方式：" | tee -a "$LOG_FILE"
    echo "  sudo systemctl stop openlist" | tee -a "$LOG_FILE"
    echo "  # 备份数据库" | tee -a "$LOG_FILE"
    echo "  cp /opt/openlist/data/data.db /opt/openlist/data/data.db.backup" | tee -a "$LOG_FILE"
    echo "  # 删除 WAL 和 SHM 文件" | tee -a "$LOG_FILE"
    echo "  rm -f /opt/openlist/data/data.db-wal /opt/openlist/data/data.db-shm" | tee -a "$LOG_FILE"
    echo "  # SQLite VACUUM (需要很长时间)" | tee -a "$LOG_FILE"
    echo "  sqlite3 /opt/openlist/data/data.db 'VACUUM;'" | tee -a "$LOG_FILE"
    echo "  sudo systemctl start openlist" | tee -a "$LOG_FILE"
else
    echo "✅ openlist 数据库大小在合理范围" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
echo "✅ 维护检查完成" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "注意：数据库操作需要谨慎，建议先备份！" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
