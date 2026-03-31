#!/bin/bash
# Docker容器资源监控脚本
# 监控容器CPU、内存和状态

LOG_FILE="logs/docker_monitor.log"
ALERT_CPU=50      # CPU使用率告警阈值(%)
ALERT_MEM=80      # 内存使用率告警阈值(%)

# 创建日志目录
mkdir -p "$(dirname "$LOG_FILE")"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "==========================================" | tee -a "$LOG_FILE"
echo "[$TIMESTAMP] Docker 容器监控报告" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"

# 获取所有容器的统计信息
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.Status}}" 2>/dev/null | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"

# 检查异常容器
echo "=== 异常检测 ===" | tee -a "$LOG_FILE"

# 检查高CPU使用率
docker stats --no-stream --format "{{.Name}}: {{.CPUPerc}}" 2>/dev/null | while read line; do
    CPU_PERCENT=$(echo "$line" | grep -oP '\d+\.\d+' | head -1)
    CONTAINER_NAME=$(echo "$line" | cut -d: -f1)
    if [ -n "$CPU_PERCENT" ]; then
        CPU_INT=${CPU_PERCENT%.*}
        if [ "$CPU_INT" -gt "$ALERT_CPU" ]; then
            echo "[$TIMESTAMP] WARNING: $CONTAINER_NAME CPU使用率过高: ${CPU_PERCENT}%" | tee -a "$LOG_FILE"
        fi
    fi
done

# 检查高内存使用率
docker stats --no-stream --format "{{.Name}}: {{.MemPerc}}" 2>/dev/null | while read line; do
    MEM_PERCENT=$(echo "$line" | grep -oP '\d+\.\d+' | head -1)
    CONTAINER_NAME=$(echo "$line" | cut -d: -f1)
    if [ -n "$MEM_PERCENT" ]; then
        MEM_INT=${MEM_PERCENT%.*}
        if [ "$MEM_INT" -gt "$ALERT_MEM" ]; then
            echo "[$TIMESTAMP] WARNING: $CONTAINER_NAME 内存使用率过高: ${MEM_PERCENT}%" | tee -a "$LOG_FILE"
        fi
    fi
done

# 检查重启中的容器
docker ps -a --format "{{.Names}}: {{.Status}}" 2>/dev/null | grep -i restarting | while read line; do
    echo "[$TIMESTAMP] WARNING: 容器持续重启 - $line" | tee -a "$LOG_FILE"
done

# 检查退出的容器
docker ps -a --format "{{.Names}}: {{.Status}}" 2>/dev/null | grep -i "exited\|dead" | while read line; do
    echo "[$TIMESTAMP] INFO: 容器已停止 - $line" | tee -a "$LOG_FILE"
done

echo "" | tee -a "$LOG_FILE"
