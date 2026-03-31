#!/bin/bash
# 每周容量评估脚本
# 分析系统容量使用趋势，提供扩容或优化建议

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DATE=$(date '+%Y-%m-%d')
WEEK=$(date '+%Y-W%V')
LOG_FILE="logs/weekly_capacity_$DATE.log"
BASELINE_JSON="baseline/latest_baseline.json"

echo "==========================================" | tee "$LOG_FILE"
echo "系统容量周报" | tee -a "$LOG_FILE"
echo "周期: $WEEK" | tee -a "$LOG_FILE"
echo "时间: $TIMESTAMP" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 1. 容器内存使用趋势
echo "【1. 容器内存使用 Top 10】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}" | \
    sort -k3 -hr | head -11 | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 2. 超过资源限制的容器
echo "【2. 超过资源限制 80% 的容器】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
docker stats --no-stream --format "{{.Name}}\t{{.MemPerc}}" | \
    awk -F'\t' '$2 ~ /([8-9][0-9]\.|100)%/ {print}' | tee -a "$LOG_FILE"
if [ $? -ne 0 ] || [ $(docker stats --no-stream --format "{{.MemPerc}}" | \
    awk -F'\t' '$2 ~ /([8-9][0-9]\.|100)%/' | wc -l) -eq 0 ]; then
    echo "✅ 无容器超过80%资源限制" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 3. 无资源限制的容器
echo "【3. 无资源限制的容器】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
UNLIMITED_CONTAINERS=$(docker inspect $(docker ps -q) --format '{{.Name}}: {{.HostConfig.Memory}}' 2>/dev/null | grep ": 0" | cut -d: -f1)
if [ -n "$UNLIMITED_CONTAINERS" ]; then
    echo "⚠️  以下容器没有内存限制：" | tee -a "$LOG_FILE"
    echo "$UNLIMITED_CONTAINERS" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    echo "建议：为这些容器添加资源限制" | tee -a "$LOG_FILE"
else
    echo "✅ 所有容器都已设置资源限制" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 4. 系统资源使用趋势
echo "【4. 系统资源使用趋势】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
MEMORY_USAGE=$(LC_ALL=C free | grep "^Mem:" | awk '{printf("%.0f", $3/$2*100)}')
TOTAL_MEMORY=$(LC_ALL=C free | grep "^Mem:" | awk '{print $2}')
USED_MEMORY=$(LC_ALL=C free | grep "^Mem:" | awk '{print $3}')
AVAILABLE_MEMORY=$(LC_ALL=C free | grep "^Mem:" | awk '{print $7}')

echo "内存使用率: ${MEMORY_USAGE}%" | tee -a "$LOG_FILE"
echo "总内存: $(($TOTAL_MEMORY / 1024 / 1024)) GB" | tee -a "$LOG_FILE"
echo "已用内存: $(($USED_MEMORY / 1024 / 1024)) GB" | tee -a "$LOG_FILE"
echo "可用内存: $AVAILABLE_MEMORY" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 5. 历史数据对比
echo "【5. 容量使用历史对比】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
if [ -f "$BASELINE_JSON" ]; then
    BASELINE_MEMORY=$(jq -r '.memory.usage_percent' "$BASELINE_JSON" 2>/dev/null)
    if [ -n "$BASELINE_MEMORY" ]; then
        DIFFERENCE=$((MEMORY_USAGE - BASELINE_MEMORY))
        echo "基线内存使用率: ${BASELINE_MEMORY}%" | tee -a "$LOG_FILE"
        echo "当前内存使用率: ${MEMORY_USAGE}%" | tee -a "$LOG_FILE"
        echo "变化: ${DIFFERENCE}%" | tee -a "$LOG_FILE"
        if [ "$DIFFERENCE" -gt 10 ]; then
            echo "⚠️  警告：内存使用率上升 ${DIFFERENCE}%" | tee -a "$LOG_FILE"
        elif [ "$DIFFERENCE" -lt -10 ]; then
            echo "✅ 改善：内存使用率下降 $((DIFFERENCE * -1))%" | tee -a "$LOG_FILE"
        fi
    fi
else
    echo "ℹ️  未找到基线数据，请运行 ./scripts/create_capacity_baseline.sh" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 6. 容量规划建议
echo "【6. 容量规划建议】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"

if [ "$MEMORY_USAGE" -lt 50 ]; then
    echo "✅ 资源充足，建议：" | tee -a "$LOG_FILE"
    echo "   - 可以增加容器实例数" | tee -a "$LOG_FILE"
    echo "   - 可以部署更多服务" | tee -a "$LOG_FILE"
    echo "   - 可以降低容器资源预留" | tee -a "$LOG_FILE"
    CAPACITY_STATUS="资源充足"
elif [ "$MEMORY_USAGE" -lt 80 ]; then
    echo "✅ 运行正常，建议：" | tee -a "$LOG_FILE"
    echo "   - 保持当前配置" | tee -a "$LOG_FILE"
    echo "   - 持续监控资源使用" | tee -a "$LOG_FILE"
    echo "   - 定期评估容量需求" | tee -a "$LOG_FILE"
    CAPACITY_STATUS="运行正常"
elif [ "$MEMORY_USAGE" -lt 90 ]; then
    echo "⚠️  需要关注，建议：" | tee -a "$LOG_FILE"
    echo "   - 检查异常占用进程" | tee -a "$LOG_FILE"
    echo "   - 考虑优化配置" | tee -a "$LOG_FILE"
    echo "   - 准备扩容方案" | tee -a "$LOG_FILE"
    CAPACITY_STATUS="需要关注"
else
    echo "🚨 需要紧急处理，建议：" | tee -a "$LOG_FILE"
    echo "   - 立即停止非核心服务" | tee -a "$LOG_FILE"
    echo "   - 清理系统缓存" | tee -a "$LOG_FILE"
    echo "   - 考虑扩容" | tee -a "$LOG_FILE"
    echo "   - 优化高内存占用服务" | tee -a "$LOG_FILE"
    CAPACITY_STATUS="紧急"
fi
echo "" | tee -a "$LOG_FILE"

# 7. Docker资源清理建议
echo "【7. Docker资源清理建议】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
DOCKER_RECLAIMABLE=$(docker system df --format "{{.Reclaimable}}" | grep -v "false" | wc -l)
if [ "$DOCKER_RECLAIMABLE" -gt 0 ]; then
    RECLAIMABLE_SIZE=$(docker system df --format "{{.Reclaimable}}" | grep -v "0B" | head -1)
    echo "⚠️  可清理资源: $RECLAIMABLE_SIZE" | tee -a "$LOG_FILE"
    echo "建议执行: docker system prune -f" | tee -a "$LOG_FILE"
else
    echo "✅ Docker资源使用合理" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 8. 下周行动计划
echo "【8. 下周行动计划】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
if [ "$CAPACITY_STATUS" = "资源充足" ]; then
    echo "📈 增长阶段：" | tee -a "$LOG_FILE"
    echo "   1. 评估是否需要新增服务" | tee -a "$LOG_FILE"
    echo "   2. 考虑增加容器副本数" | tee -a "$LOG_FILE"
    echo "   3. 优化资源分配" | tee -a "$LOG_FILE"
elif [ "$CAPACITY_STATUS" = "运行正常" ]; then
    echo "📊 稳定阶段：" | tee -a "$LOG_FILE"
    echo "   1. 持续监控资源使用" | tee -a "$LOG_FILE"
    echo "   2. 定期更新容量基线" | tee -a "$LOG_FILE"
    echo "   3. 评估性能优化空间" | tee -a "$LOG_FILE"
elif [ "$CAPACITY_STATUS" = "需要关注" ]; then
    echo "⚠️  优化阶段：" | tee -a "$LOG_FILE"
    echo "   1. 分析高内存占用原因" | tee -a "$LOG_FILE"
    echo "   2. 优化应用配置" | tee -a "$LOG_FILE"
    echo "   3. 准备扩容方案" | tee -a "$LOG_FILE"
    echo "   4. 更新容量基线" | tee -a "$LOG_FILE"
else
    echo "🚨 应急阶段：" | tee -a "$LOG_FILE"
    echo "   1. 立即执行应急恢复" | tee -a "$LOG_FILE"
    echo "   2. 停止非核心服务" | tee -a "$LOG_FILE"
    echo "   3. 清理系统资源" | tee -a "$LOG_FILE"
    echo "   4. 评估扩容需求" | tee -a "$LOG_FILE"
    echo "   5. 优化架构设计" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 9. 保存周报摘要
WEEKLY_SUMMARY="logs/weekly_summary.txt"
echo "[$WEEK] 内存使用率: ${MEMORY_USAGE}%, 状态: $CAPACITY_STATUS" >> "$WEEKLY_SUMMARY"

echo "==========================================" | tee -a "$LOG_FILE"
echo "报告已保存到: $LOG_FILE" | tee -a "$LOG_FILE"
echo "周报摘要已保存到: $WEEKLY_SUMMARY" | tee -a "$LOG_FILE"
echo "容量状态: $CAPACITY_STATUS" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
