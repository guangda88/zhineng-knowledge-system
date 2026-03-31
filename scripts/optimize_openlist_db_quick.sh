#!/bin/bash
# openlist 数据库快速优化脚本（跳过备份）
# 适用于磁盘空间不足的情况

set -e

echo "=========================================="
echo "openlist 数据库快速优化"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 错误: 此脚本需要 root 权限"
    echo "请使用: sudo bash $0"
    exit 1
fi

# 1. 确认 openlist 服务已停止
echo "【1. 确认 openlist 服务状态】"
if systemctl is-active --quiet openlist; then
    echo "❌ openlist 服务正在运行，请先停止："
    echo "   sudo systemctl stop openlist"
    exit 1
else
    echo "✅ openlist 服务未运行（可以继续）"
fi
echo ""

# 2. 显示当前数据库大小
echo "【2. 当前数据库状态】"
DB_FILE="/opt/openlist/data/data.db"
DB_SIZE=$(du -sh "$DB_FILE" | cut -f1)
echo "数据库大小: $DB_SIZE"

# 检查 WAL 文件
WAL_FILE="/opt/openlist/data/data.db-wal"
if [ -f "$WAL_FILE" ]; then
    WAL_SIZE=$(du -sh "$WAL_FILE" | cut -f1)
    echo "WAL 文件大小: $WAL_SIZE"
fi
echo ""

# 3. 询问是否继续（无备份）
echo "【3. 重要提示】"
echo "⚠️  由于磁盘空间不足，将跳过备份步骤"
echo "⚠️  如果您已有备份文件，可以继续"
echo ""
echo "现有备份文件："
ls -lh /opt/openlist/data/data.db.backup* 2>/dev/null || echo "  无备份文件"
echo ""
read -p "是否继续优化？(输入 YES 继续): " confirm

if [ "$confirm" != "YES" ]; then
    echo "❌ 用户取消操作"
    exit 1
fi
echo ""

# 4. 清理 WAL 文件
echo "【4. 清理 WAL 文件】"
SHM_FILE="/opt/openlist/data/data.db-shm"

if [ -f "$WAL_FILE" ]; then
    rm -f "$WAL_FILE"
    echo "✅ WAL 文件已删除"
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

# 5. 执行 PRAGMA 优化（不使用 VACUUM）
echo "【5. 执行数据库优化】"
echo "正在执行 PRAGMA optimize..."
sqlite3 "$DB_FILE" "PRAGMA optimize;"
echo "✅ PRAGMA optimize 完成"
echo ""

# 6. 分析数据库
echo "【6. 分析数据库】"
echo "正在分析数据库..."
sqlite3 "$DB_FILE" "ANALYZE;"
echo "✅ ANALYZE 完成"
echo ""

# 7. 显示结果
echo "【7. 优化结果】"
NEW_DB_SIZE=$(du -sh "$DB_FILE" | cut -f1)
echo "原始大小: $DB_SIZE"
echo "当前大小: $NEW_DB_SIZE"
echo ""

# 8. 重启 openlist 服务（可选）
echo "【8. 重启 openlist 服务】"
read -p "是否重启 openlist 服务？(y/n): " restart_confirm

if [ "$restart_confirm" = "y" ] || [ "$restart_confirm" = "Y" ]; then
    systemctl start openlist
    sleep 3

    if systemctl is-active --quiet openlist; then
        echo "✅ openlist 服务已启动"
    else
        echo "❌ openlist 服务启动失败"
        echo "请检查日志: sudo journalctl -u openlist -n 50"
    fi
else
    echo "⚠️  openlist 服务未启动"
fi
echo ""

echo "=========================================="
echo "✅ openlist 数据库快速优化完成！"
echo ""
echo "说明："
echo "- 由于空间不足，未执行完整的 VACUUM"
echo "- 已执行 PRAGMA optimize 和 ANALYZE"
echo "- 建议释放磁盘空间后执行完整 VACUUM"
echo ""
echo "完整 VACUUM 步骤："
echo "1. 释放至少 60GB 磁盘空间"
echo "2. 停止 openlist: sudo systemctl stop openlist"
echo "3. 执行 VACUUM: sudo sqlite3 /opt/openlist/data/data.db 'VACUUM;'"
echo "4. 重启服务: sudo systemctl start openlist"
echo "=========================================="
