#!/bin/bash
# 系统磁盘空间清理脚本
# 用于清理占用大量空间的文件和目录

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="logs/disk_cleanup_$TIMESTAMP.log"

echo "==========================================" | tee "$LOG_FILE"
echo "磁盘空间清理工具" | tee -a "$LOG_FILE"
echo "时间: $TIMESTAMP" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 记录清理前状态
echo "【清理前磁盘使用情况】" | tee -a "$LOG_FILE"
df -h | grep -E "(Filesystem|/dev/)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

TOTAL_FREED=0

# 1. 清理 systemd journal (保留最近7天)
echo "【1. 清理 systemd journal】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
JOURNAL_SIZE_BEFORE=$(du -sb /var/log/journal 2>/dev/null | cut -f1)
echo "清理前 journal 大小: $(($JOURNAL_SIZE_BEFORE / 1024 / 1024))MB" | tee -a "$LOG_FILE"

# 清理超过7天的journal
sudo journalctl --vacuum-time=7d | tee -a "$LOG_FILE"
JOURNAL_SIZE_AFTER=$(du -sb /var/log/journal 2>/dev/null | cut -f1)
JOURNAL_FREED=$((($JOURNAL_SIZE_BEFORE - $JOURNAL_SIZE_AFTER) / 1024 / 1024))
TOTAL_FREED=$((TOTAL_FREED + JOURNAL_FREED))
echo "清理后 journal 大小: $(($JOURNAL_SIZE_AFTER / 1024 / 1024))MB" | tee -a "$LOG_FILE"
echo "释放空间: ${JOURNAL_FREED}MB" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 2. 清理旧日志文件
echo "【2. 清理系统日志文件】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
# 清理旧的 syslog 文件 (保留最近2个)
sudo find /var/log -name "syslog.*.gz" -mtime +30 -delete 2>/dev/null
sudo find /var/log -name "*.gz" -mtime +30 -delete 2>/dev/null
echo "✅ 已清理超过30天的压缩日志" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 3. 清理 npm 缓存
echo "【3. 清理 npm 缓存】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
NPM_CACHE_BEFORE=$(du -sb ~/.npm 2>/dev/null | cut -f1)
if [ -n "$NPM_CACHE_BEFORE" ] && [ "$NPM_CACHE_BEFORE" -gt 0 ]; then
    echo "清理前 npm 缓存: $(($NPM_CACHE_BEFORE / 1024 / 1024))MB" | tee -a "$LOG_FILE"
    npm cache clean --force 2>/dev/null
    NPM_CACHE_AFTER=$(du -sb ~/.npm 2>/dev/null | cut -f1)
    NPM_FREED=$((($NPM_CACHE_BEFORE - $NPM_CACHE_AFTER) / 1024 / 1024))
    TOTAL_FREED=$((TOTAL_FREED + NPM_FREED))
    echo "清理后 npm 缓存: $(($NPM_CACHE_AFTER / 1024 / 1024))MB" | tee -a "$LOG_FILE"
    echo "释放空间: ${NPM_FREED}MB" | tee -a "$LOG_FILE"
else
    echo "npm 缓存不存在或已为空" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 4. 清理 Docker 未使用资源
echo "【4. 清理 Docker 未使用资源】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
DOCKER_BEFORE=$(docker system df --format "{{.Reclaimable}}" | grep -v "false" | head -1)
if [ -n "$DOCKER_BEFORE" ]; then
    echo "可清理的 Docker 资源: $DOCKER_BEFORE" | tee -a "$LOG_FILE"
    docker system prune -f --volumes | tee -a "$LOG_FILE"
    echo "✅ Docker 清理完成" | tee -a "$LOG_FILE"
else
    echo "没有可清理的 Docker 资源" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 5. 清理临时文件
echo "【5. 清理临时文件】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
# 清理 /tmp
TMP_BEFORE=$(du -sb /tmp 2>/dev/null | cut -f1)
sudo find /tmp -type f -atime +7 -delete 2>/dev/null
TMP_AFTER=$(du -sb /tmp 2>/dev/null | cut -f1)
TMP_FREED=$((($TMP_BEFORE - $TMP_AFTER) / 1024 / 1024))
TOTAL_FREED=$((TOTAL_FREED + TMP_FREED))
echo "从 /tmp 释放: ${TMP_FREED}MB" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 6. 清理 openlist 数据库 WAL 文件 (谨慎)
echo "【6. openlist 数据库维护】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
echo "⚠️  警告：openlist 数据库占用 59GB" | tee -a "$LOG_FILE"
echo "建议操作：" | tee -a "$LOG_FILE"
echo "  1. 检查是否可以删除旧数据" | tee -a "$LOG_FILE"
echo "  2. 执行数据库 VACUUM" | tee -a "$LOG_FILE"
echo "  3. 清理 WAL 文件" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "当前 openlist 数据库文件：" | tee -a "$LOG_FILE"
ls -lh /opt/openlist/data/data.db* | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 7. 清理备份文件
echo "【7. 清理旧备份文件】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
# 清理超过30天的备份
find /backup -type f -mtime +30 -delete 2>/dev/null
find /home/ai/zhineng-knowledge-system/backups -type f -mtime +30 -delete 2>/dev/null
echo "✅ 已清理超过30天的备份文件" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 记录清理后状态
echo "【清理后磁盘使用情况】" | tee -a "$LOG_FILE"
df -h | grep -E "(Filesystem|/dev/)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

echo "==========================================" | tee -a "$LOG_FILE"
echo "✅ 磁盘清理完成" | tee -a "$LOG_FILE"
echo "总计释放空间: ${TOTAL_FREED}MB" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
