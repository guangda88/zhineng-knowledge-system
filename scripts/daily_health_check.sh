#!/bin/bash
# 每日系统健康检查脚本
# 生成系统健康日报，帮助及时发现潜在问题

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DATE=$(date '+%Y-%m-%d')
LOG_FILE="logs/daily_health_$DATE.log"

echo "==========================================" | tee "$LOG_FILE"
echo "系统健康日报" | tee -a "$LOG_FILE"
echo "时间: $TIMESTAMP" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 1. 内存检查
echo "【1. 内存使用情况】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
free -h | tee -a "$LOG_FILE"
MEMORY_USAGE=$(LC_ALL=C free | grep "^Mem:" | awk '{printf("%.0f", $3/$2*100)}')
if [ "$MEMORY_USAGE" -gt 80 ]; then
    echo "⚠️  警告：内存使用率 ${MEMORY_USAGE}% 超过 80%" | tee -a "$LOG_FILE"
elif [ "$MEMORY_USAGE" -gt 90 ]; then
    echo "🚨 严重：内存使用率 ${MEMORY_USAGE}% 超过 90%" | tee -a "$LOG_FILE"
else
    echo "✅ 正常：内存使用率 ${MEMORY_USAGE}%" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 2. Docker 容器状态
echo "【2. Docker 容器状态】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
RUNNING_CONTAINERS=$(docker ps | wc -l)
TOTAL_CONTAINERS=$(docker ps -a | wc -l)
echo "运行中: $((RUNNING_CONTAINERS - 1)) / 总数: $((TOTAL_CONTAINERS - 1))" | tee -a "$LOG_FILE"
docker ps --format "table {{.Names}}\t{{.Status}}" | head -10 | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 3. 异常容器检测
echo "【3. 异常容器检测】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
ABNORMAL_CONTAINERS=$(docker ps -a --format "{{.Names}}: {{.Status}}" | grep -E "(exited|dead|restarting)")
if [ -n "$ABNORMAL_CONTAINERS" ]; then
    echo "⚠️  发现异常容器：" | tee -a "$LOG_FILE"
    echo "$ABNORMAL_CONTAINERS" | tee -a "$LOG_FILE"
else
    echo "✅ 无异常容器" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 4. 僵尸进程检测
echo "【4. 僵尸进程检测】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
ZOMBIE_COUNT=$(ps aux | grep defunct | grep -v grep | wc -l)
echo "僵尸进程数量: $ZOMBIE_COUNT" | tee -a "$LOG_FILE"
if [ "$ZOMBIE_COUNT" -gt 10 ]; then
    echo "⚠️  警告：僵尸进程过多 ($ZOMBIE_COUNT 个)" | tee -a "$LOG_FILE"
elif [ "$ZOMBIE_COUNT" -gt 5 ]; then
    echo "⚠️  注意：僵尸进程偏多 ($ZOMBIE_COUNT 个)" | tee -a "$LOG_FILE"
else
    echo "✅ 正常：僵尸进程数量 ($ZOMBIE_COUNT 个)" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 5. 磁盘使用情况
echo "【5. 磁盘使用情况】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
df -h | grep -E "(Filesystem|/dev/)" | tee -a "$LOG_FILE"
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "⚠️  警告：根分区使用率 ${DISK_USAGE}%" | tee -a "$LOG_FILE"
elif [ "$DISK_USAGE" -gt 90 ]; then
    echo "🚨 严重：根分区使用率 ${DISK_USAGE}%" | tee -a "$LOG_FILE"
else
    echo "✅ 正常：根分区使用率 ${DISK_USAGE}%" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 6. 容器资源使用 Top 10
echo "【6. 容器资源使用 Top 10】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | head -11 | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 7. 网络连接统计
echo "【7. 网络连接统计】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
ESTABLISHED=$(netstat -an 2>/dev/null | grep ESTABLISHED | wc -l)
TIME_WAIT=$(netstat -an 2>/dev/null | grep TIME_WAIT | wc -l)
echo "ESTABLISHED: $ESTABLISHED" | tee -a "$LOG_FILE"
echo "TIME_WAIT: $TIME_WAIT" | tee -a "$LOG_FILE"
if [ "$TIME_WAIT" -gt 1000 ]; then
    echo "⚠️  注意：TIME_WAIT 连接过多 ($TIME_WAIT)" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 8. 系统负载
echo "【8. 系统负载】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
uptime | tee -a "$LOG_FILE"
LOAD_1MIN=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
LOAD_5MIN=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $2}' | sed 's/,//')
CPU_CORES=$(nproc)
LOAD_1MIN_INT=${LOAD_1MIN%.*}
if [ "$LOAD_1MIN_INT" -gt "$CPU_CORES" ]; then
    echo "⚠️  警告：1分钟负载 ($LOAD_1MIN) 超过CPU核心数 ($CPU_CORES)" | tee -a "$LOG_FILE"
else
    echo "✅ 正常：负载在合理范围内" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 9. 最近错误日志（最近10条）
echo "【9. 最近错误日志（最近 10 条）】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
journalctl --since "1 hour ago" --priority=err -n 10 --no-pager | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 10. 健康评分
echo "【10. 系统健康评分】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
SCORE=100

# 扣分项
[ "$MEMORY_USAGE" -gt 80 ] && SCORE=$((SCORE - 20))
[ "$MEMORY_USAGE" -gt 90 ] && SCORE=$((SCORE - 20))
[ "$ZOMBIE_COUNT" -gt 10 ] && SCORE=$((SCORE - 10))
[ "$ZOMBIE_COUNT" -gt 20 ] && SCORE=$((SCORE - 10))
[ "$DISK_USAGE" -gt 80 ] && SCORE=$((SCORE - 15))
[ "$DISK_USAGE" -gt 90 ] && SCORE=$((SCORE - 15))
[ -n "$ABNORMAL_CONTAINERS" ] && SCORE=$((SCORE - 10))
[ "$TIME_WAIT" -gt 1000 ] && SCORE=$((SCORE - 10))

if [ $SCORE -ge 90 ]; then
    echo "✅ 优秀：$SCORE/100 分" | tee -a "$LOG_FILE"
elif [ $SCORE -ge 70 ]; then
    echo "✅ 良好：$SCORE/100 分" | tee -a "$LOG_FILE"
elif [ $SCORE -ge 50 ]; then
    echo "⚠️  一般：$SCORE/100 分，需要关注" | tee -a "$LOG_FILE"
else
    echo "🚨 差：$SCORE/100 分，需要立即处理" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
echo "报告已保存到: $LOG_FILE" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
