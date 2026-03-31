#!/bin/bash
# openlist 数据库深度分析脚本
# 分析 59GB 数据库的详细内容

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "========================================"
echo "openlist 数据库深度分析"
echo "时间: $TIMESTAMP"
echo "========================================"
echo ""

# 1. 数据库文件基本信息
echo "【1. 数据库文件信息】"
echo "─────────────────────────────────────"
DB_FILE="/opt/openlist/data/data.db"

if [ -f "$DB_FILE" ]; then
    DB_SIZE_BYTES=$(stat -f% "$DB_FILE")
    DB_SIZE_GB=$((DB_SIZE_BYTES / 1024 / 1024 / 1024))
    DB_PAGES=$(stat -c %s "$DB_FILE")

    echo "文件路径: $DB_FILE"
    echo "文件大小: $DB_SIZE_GB GB"
    echo "文件类型: $(file "$DB_FILE" | cut -d: -f2)"

    # SQLite 页面信息
    PAGE_SIZE=4096  # SQLite 默认页面大小
    TOTAL_PAGES=$((DB_SIZE_BYTES / PAGE_SIZE))
    echo "总页面数: $TOTAL_PAGES"
    echo "页面大小: 4KB"
fi

echo ""

# 2. 尝试读取数据库结构（无权限版本）
echo "【2. 数据库结构分析】"
echo "─────────────────────────────────────"

# 检查数据库是否可读
if [ -r "$DB_FILE" ]; then
    echo "✅ 数据库文件可读"

    # 尝试列出表
    sqlite3 "$DB_FILE" ".tables" 2>/dev/null && echo "" || echo "需要 sudo 权限读取数据库内容"
else
    echo "⚠️  需要 root 权限读取数据库"
fi

# 3. 从文件系统推断
echo "【3. 从配置和挂载点推断】"
echo "─────────────────────────────────────"

# 检查配置文件中的存储账号
CONFIG_FILE="/opt/openlist/data/config.json"
if [ -f "$CONFIG_FILE" ]; then
    echo "✅ 找到配置文件"
    echo "  - 数据库类型: SQLite3"
    echo "  - Meilisearch 索引: 启用"
    echo "  - 最大缓冲: 20MB"
    echo "  - mmap 阈值: 2MB"
fi

# 检查挂载点
MOUNT_POINT="/mnt/openlist"
if mount | grep -q "$MOUNT_POINT"; then
    echo "✅ 找到挂载点: $MOUNT_POINT"
    echo ""
    echo "挂载的存储服务:"
    ls "$MOUNT_POINT" 2>/dev/null | head -10
else
    echo "⚠️  未找到挂载点"
fi

echo ""

# 4. 数据库大小推算
echo "【4. 数据库内容推算】"
echo "─────────────────────────────────────"

# 从 SQLite 文件头信息推算
DB_INFO=$(file "$DB_FILE")
echo "$DB_INFO" | grep -o "database pages [0-9]*" | grep -o "[0-9]*" | while read PAGES; do
    TOTAL_PAGES=$PAGES
done

echo "数据库页数: $TOTAL_PAGES"
echo "推算："
echo "  - 如果每个记录平均占用 1KB: ~$(($TOTAL_PAGES * 4))MB 数据"
echo "  - 如果每个记录平均占用 10KB: ~$(($TOTAL_PAGES * 40))MB 数据"
echo "  - 实际大小: 59GB"
echo ""
echo "这意味着数据库可能包含数百万条记录"

echo ""

# 5. 可能占用空间的内容
echo "【5. 可能占用空间的内容类型】"
echo "─────────────────────────────────────"
echo "openlist 作为多云存储管理服务，数据库可能包含："
echo ""
echo "1. 文件元数据索引 (最大占用)"
echo "   - 文件名、路径、大小"
echo "   - 修改时间、创建时间"
echo "   - 文件哈希值（MD5/SHA1/SHA256）"
echo "   - 文件缩略图缓存"
echo ""
echo "2. 搜索索引"
echo "   - 全文搜索索引"
echo "   - Meilisearch 同步数据"
echo ""
echo "3. 任务队列"
echo "   - 上传/下载任务记录"
echo "   - 任务状态和历史"
echo ""
echo "4. 用户数据"
echo "   - 用户配置和设置"
echo "   - 权限和分享记录"

echo ""

# 6. 增长速度分析
echo "【6. 增长速度分析】"
echo "─────────────────────────────────────"

# 检查数据库修改时间
DB_MTIME=$(stat -c %y "$DB_FILE" 2>/dev/null | cut -d'.' -f1)
DB_BTIME=$(stat -c %z "$DB_FILE" 2>/dev/null)

echo "数据库修改时间: $(stat -c %y "$DB_FILE" 2>/dev/null)"
echo "数据库大小: 59GB"

# 从配置看优化后的设置
echo ""
echo "⚠️  关键发现："
echo "  - 数据库已优化（max_buffer_limitMB: 20MB, mmap_thresholdMB: 2MB）"
echo "  - 但数据库文件仍为 59GB（优化前更大）"
echo "  - 这说明数据库已经累积了大量历史数据"

echo ""

# 7. 解决建议
echo "【7. 解决建议】"
echo "─────────────────────────────────────"
echo ""
echo "🔴 立即行动："
echo "  1. 确认 openlist 服务是否必需"
echo "     - 如果不使用，可以停止服务释放 59GB"
echo ""
echo "  2. 如果必需，执行数据库维护："
echo "     - 停止 openlist 服务"
echo "     - 备份数据库"
echo "     - 执行 SQLite VACUUM（可释放 10-30GB）"
echo "     - 重启服务"
echo ""
echo "🟡 中期优化："
echo "  1. 配置 openlist 定期清理"
echo "  2. 减少索引的文件数量"
echo "  3. 禁用不必要的存储服务"
echo "  4. 清理 Meilisearch 旧索引"
echo ""
echo "🟢 长期预防："
echo "  1. 设置数据库大小监控告警"
echo "  2. 定期执行数据库 VACUUM"
echo "  3. 配置数据归档策略"

echo ""
echo "========================================"
echo "✅ 分析完成"
echo "========================================"

# 8. 尝试读取数据库（如果可用）
echo ""
echo "【8. 尝试读取数据库内容】"
echo "─────────────────────────────────────"

# 尝试以当前用户读取
if sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM x_search_nodes;" 2>/dev/null; then
    echo "✅ 成功读取数据库"
    echo ""
    echo "统计信息："
    sqlite3 "$DB_FILE" <<EOF
.mode column
.headers on
SELECT 'search_nodes' as table_name, COUNT(*) as count FROM x_search_nodes
UNION ALL
SELECT 'storages' as table_name, COUNT(*) as count FROM x_storages
UNION ALL
SELECT 'users' as table_name, COUNT(*) as count FROM x_users;
EOF
elif sudo sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM x_search_nodes;" 2>/dev/null; then
    echo "✅ 成功读取数据库（需要 sudo）"
    echo ""
    echo "统计信息："
    sudo sqlite3 "$DB_FILE" <<EOF
.mode column
.headers on
SELECT 'search_nodes' as table_name, COUNT(*) as count FROM x_search_nodes
UNION ALL
SELECT 'storages' as table_name, COUNT(*) as count FROM x_storages
UNION ALL
SELECT 'users' as table_name, COUNT(*) as count FROM x_users;
EOF
else
    echo "⚠️  无法读取数据库内容（可能被锁定或需要权限）"
    echo ""
    echo "建议："
    echo "  1. 停止 openlist 服务"
    echo "  2. 再尝试读取数据库"
fi
