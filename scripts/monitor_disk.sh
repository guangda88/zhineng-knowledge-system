#!/bin/bash
# 磁盘空间监控脚本
# 当磁盘使用率超过阈值时发送告警

THRESHOLD=80
LOG_FILE="logs/monitor.log"

# 创建日志目录
mkdir -p "$(dirname "$LOG_FILE")"

# 获取根分区使用率
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 检查是否超过阈值
if [ "$DISK_USAGE" -gt "$THRESHOLD" ]; then
    echo "[$TIMESTAMP] WARNING: 磁盘使用率过高: ${DISK_USAGE}% (阈值: ${THRESHOLD}%)" | tee -a "$LOG_FILE"
    # 可以在这里添加告警通知逻辑，如发送邮件或webhook
else
    echo "[$TIMESTAMP] INFO: 磁盘使用率正常: ${DISK_USAGE}%" | tee -a "$LOG_FILE"
fi

# 检查数据分区（如果存在）
if [ -d /data ]; then
    DATA_USAGE=$(df /data | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$DATA_USAGE" -gt "$THRESHOLD" ]; then
        echo "[$TIMESTAMP] WARNING: /data 分区使用率过高: ${DATA_USAGE}%" | tee -a "$LOG_FILE"
    fi
fi

# 检查Docker磁盘使用
DOCKER_USAGE=$(docker system df 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//')
if [ -n "$DOCKER_USAGE" ] && [[ "$DOCKER_USAGE" =~ ^[0-9]+$ ]] && [ "$DOCKER_USAGE" -gt "$THRESHOLD" ]; then
    echo "[$TIMESTAMP] WARNING: Docker磁盘使用率过高: ${DOCKER_USAGE}%" | tee -a "$LOG_FILE"
fi
