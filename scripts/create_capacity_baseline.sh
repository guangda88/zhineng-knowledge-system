#!/bin/bash
# 创建容量规划基线
# 记录系统各组件的正常资源使用范围，作为未来容量规划的基准

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
BASELINE_DIR="baseline"
mkdir -p "$BASELINE_DIR"

BASELINE_FILE="$BASELINE_DIR/capacity_baseline_$(date +%Y%m%d_%H%M%S).txt"

echo "========================================" | tee "$BASELINE_FILE"
echo "系统容量基线报告" | tee -a "$BASELINE_FILE"
echo "时间: $TIMESTAMP" | tee -a "$BASELINE_FILE"
echo "========================================" | tee -a "$BASELINE_FILE"
echo "" | tee -a "$BASELINE_FILE"

# 1. 系统总体资源使用
echo "【1. 系统总体资源】" | tee -a "$BASELINE_FILE"
echo "────────────────────────────────────────" | tee -a "$BASELINE_FILE"
free -h | tee -a "$BASELINE_FILE"
echo "" | tee -a "$BASELINE_FILE"

# 2. CPU信息
echo "【2. CPU信息】" | tee -a "$BASELINE_FILE"
echo "────────────────────────────────────────" | tee -a "$BASELINE_FILE"
echo "CPU核心数: $(nproc)" | tee -a "$BASELINE_FILE"
echo "CPU负载:" | tee -a "$BASELINE_FILE"
uptime | tee -a "$BASELINE_FILE"
echo "" | tee -a "$BASELINE_FILE"

# 3. 本项目容器资源使用
echo "【3. 本项目容器资源使用】" | tee -a "$BASELINE_FILE"
echo "────────────────────────────────────────" | tee -a "$BASELINE_FILE"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep zhineng | tee -a "$BASELINE_FILE"
echo "" | tee -a "$BASELINE_FILE"

# 4. 其他项目容器资源使用
echo "【4. 其他项目容器资源使用】" | tee -a "$BASELINE_FILE"
echo "────────────────────────────────────────" | tee -a "$BASELINE_FILE"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep -v zhineng | grep -v NAMES | tee -a "$BASELINE_FILE"
echo "" | tee -a "$BASELINE_FILE"

# 5. 磁盘使用情况
echo "【5. 磁盘使用情况】" | tee -a "$BASELINE_FILE"
echo "────────────────────────────────────────" | tee -a "$BASELINE_FILE"
df -h | tee -a "$BASELINE_FILE"
echo "" | tee -a "$BASELINE_FILE"

# 6. Docker资源使用
echo "【6. Docker资源使用】" | tee -a "$BASELINE_FILE"
echo "────────────────────────────────────────" | tee -a "$BASELINE_FILE"
docker system df | tee -a "$BASELINE_FILE"
echo "" | tee -a "$BASELINE_FILE"

# 7. 进程统计
echo "【7. 进程统计】" | tee -a "$BASELINE_FILE"
echo "────────────────────────────────────────" | tee -a "$BASELINE_FILE"
TOTAL_PROCESSES=$(ps aux | wc -l)
ZOMBIE_PROCESSES=$(ps aux | grep defunct | grep -v grep | wc -l)
echo "总进程数: $TOTAL_PROCESSES" | tee -a "$BASELINE_FILE"
echo "僵尸进程数: $ZOMBIE_PROCESSES" | tee -a "$BASELINE_FILE"
echo "" | tee -a "$BASELINE_FILE"

# 8. 网络连接统计
echo "【8. 网络连接统计】" | tee -a "$BASELINE_FILE"
echo "────────────────────────────────────────" | tee -a "$BASELINE_FILE"
ESTABLISHED_CONNECTIONS=$(netstat -an 2>/dev/null | grep ESTABLISHED | wc -l)
LISTEN_PORTS=$(netstat -an 2>/dev/null | grep LISTEN | wc -l)
echo "活跃连接数: $ESTABLISHED_CONNECTIONS" | tee -a "$BASELINE_FILE"
echo "监听端口数: $LISTEN_PORTS" | tee -a "$BASELINE_FILE"
echo "" | tee -a "$BASELINE_FILE"

# 9. 容器资源限制配置
echo "【9. 容器资源限制配置】" | tee -a "$BASELINE_FILE"
echo "────────────────────────────────────────" | tee -a "$BASELINE_FILE"
docker inspect $(docker ps -q) --format '{{.Name}}: Memory={{.HostConfig.Memory}}, CPU={{.HostConfig.NanoCpus}}' 2>/dev/null | head -20 | tee -a "$BASELINE_FILE"
echo "" | tee -a "$BASELINE_FILE"

# 10. 容量建议
echo "【10. 容量规划建议】" | tee -a "$BASELINE_FILE"
echo "────────────────────────────────────────" | tee -a "$BASELINE_FILE"

MEMORY_USAGE=$(LC_ALL=C free | grep "^Mem:" | awk '{printf("%.0f", $3/$2*100)}')
TOTAL_MEMORY=$(LC_ALL=C free | grep "^Mem:" | awk '{printf("%.0f", $2/1024)}')
USED_MEMORY=$(LC_ALL=C free | grep "^Mem:" | awk '{printf("%.0f", $3/1024)}')

if [ "$MEMORY_USAGE" -lt 50 ]; then
    echo "✅ 内存使用率 ${MEMORY_USAGE}%：资源充足，可以考虑："
    echo "   - 增加容器实例数"
    echo "   - 运行更多服务"
    echo "   - 减少 reserve 容量"
elif [ "$MEMORY_USAGE" -lt 80 ]; then
    echo "✅ 内存使用率 ${MEMORY_USAGE}%：运行正常，建议："
    echo "   - 保持当前配置"
    echo "   - 持续监控"
    echo "   - 定期评估"
else
    echo "⚠️  内存使用率 ${MEMORY_USAGE}%：需要关注，建议："
    echo "   - 检查异常占用"
    echo "   - 考虑扩容"
    echo "   - 优化服务配置"
fi

echo "" | tee -a "$BASELINE_FILE"
echo "当前资源分配:" | tee -a "$BASELINE_FILE"
echo "  系统总内存: ${TOTAL_MEMORY}MB" | tee -a "$BASELINE_FILE"
echo "  已使用内存: ${USED_MEMORY}MB (${MEMORY_USAGE}%)" | tee -a "$BASELINE_FILE"
echo "  推荐预留: $(($TOTAL_MEMORY / 5))MB (20%)" | tee -a "$BASELINE_FILE"
echo "  可用于容器: $(($TOTAL_MEMORY - $TOTAL_MEMORY / 5))MB" | tee -a "$BASELINE_FILE"
echo "" | tee -a "$BASELINE_FILE"

# 11. 保存到数据库文件（用于趋势分析）
echo "$TIMESTAMP,$MEMORY_USAGE,$TOTAL_PROCESSES,$ZOMBIE_PROCESSES,$ESTABLISHED_CONNECTIONS" >> "$BASELINE_DIR/capacity_history.csv"

echo "========================================" | tee -a "$BASELINE_FILE"
echo "✅ 容量基线已保存到: $BASELINE_FILE" | tee -a "$BASELINE_FILE"
echo "✅ 历史数据已保存到: $BASELINE_DIR/capacity_history.csv" | tee -a "$BASELINE_FILE"
echo "========================================" | tee -a "$BASELINE_FILE"

# 创建简短的JSON版本供程序使用
JSON_FILE="$BASELINE_DIR/latest_baseline.json"
cat > "$JSON_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "memory": {
    "total_mb": $TOTAL_MEMORY,
    "used_mb": $USED_MEMORY,
    "usage_percent": $MEMORY_USAGE
  },
  "processes": {
    "total": $TOTAL_PROCESSES,
    "zombies": $ZOMBIE_PROCESSES
  },
  "network": {
    "established": $ESTABLISHED_CONNECTIONS,
    "listening": $LISTEN_PORTS
  },
  "containers": {
    "running": $(docker ps | wc -l),
    "total": $(docker ps -a | wc -l)
  }
}
EOF

echo "✅ JSON格式基线已保存到: $JSON_FILE"
