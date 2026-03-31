#!/bin/bash
# 内存应急恢复脚本
# 当内存使用率超过阈值时自动执行恢复操作
# 作者: Claude Code
# 创建日期: 2026-03-30

THRESHOLD=85
LOG_FILE="logs/emergency_recovery.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 创建日志目录
mkdir -p "$(dirname "$LOG_FILE")"

# 获取当前内存使用率（支持中文和英文环境）
MEMORY_USAGE=$(LC_ALL=C free | grep "^Mem:" | awk '{printf("%.0f", $3/$2*100)}')
MEMORY_AVAILABLE=$(free -h | awk '/^内存:/ {print $7}; /^Mem:/ {print $7}')

echo "[$TIMESTAMP] ========================================" | tee -a "$LOG_FILE"
echo "[$TIMESTAMP] 内存应急恢复检查" | tee -a "$LOG_FILE"
echo "[$TIMESTAMP] 当前内存使用率: ${MEMORY_USAGE}%, 可用: $MEMORY_AVAILABLE" | tee -a "$LOG_FILE"

if [ "$MEMORY_USAGE" -gt "$THRESHOLD" ]; then
    echo "[$TIMESTAMP] 🚨 内存使用率 ${MEMORY_USAGE}% 超过阈值 (${THRESHOLD}%)，执行应急恢复..." | tee -a "$LOG_FILE"

    # 1. 停止非核心容器
    echo "" | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] 步骤1: 停止非核心容器..." | tee -a "$LOG_FILE"

    NON_ESSENTIAL_CONTAINERS="github-recommender-web github-recommender-scheduler safeline-tengine"
    for container in $NON_ESSENTIAL_CONTAINERS; do
        if docker ps -q -f name="$container" | grep -q .; then
            echo "[$TIMESTAMP] 停止容器: $container" | tee -a "$LOG_FILE"
            docker stop "$container" 2>&1 | tee -a "$LOG_FILE"
        fi
    done

    # 2. 清理 Docker 未使用的资源
    echo "" | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] 步骤2: 清理 Docker 缓存..." | tee -a "$LOG_FILE"
    docker system prune -f --volumes 2>&1 | tee -a "$LOG_FILE"

    # 3. 清理僵尸进程
    echo "" | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] 步骤3: 清理僵尸进程..." | tee -a "$LOG_FILE"
    if [ -f "./scripts/cleanup_zombies.sh" ]; then
        ./scripts/cleanup_zombies.sh | tee -a "$LOG_FILE"
    fi

    # 4. 清理系统页面缓存（需要 root 权限）
    echo "" | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] 步骤4: 清理系统缓存..." | tee -a "$LOG_FILE"
    sync
    if sudo sysctl -w vm.drop_caches=3 2>&1 | tee -a "$LOG_FILE"; then
        echo "[$TIMESTAMP] ✅ 系统缓存已清理" | tee -a "$LOG_FILE"
    else
        echo "[$TIMESTAMP] ⚠️  需要 root 权限清理系统缓存" | tee -a "$LOG_FILE"
    fi

    # 5. 等待系统稳定
    sleep 5

    # 6. 报告结果
    NEW_MEMORY_USAGE=$(LC_ALL=C free | grep "^Mem:" | awk '{printf("%.0f", $3/$2*100)}')
    NEW_MEMORY_AVAILABLE=$(free -h | awk '/^内存:/ {print $7}; /^Mem:/ {print $7}')

    echo "" | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] ========================================" | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] 应急恢复完成！" | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] 内存使用率: ${MEMORY_USAGE}% → ${NEW_MEMORY_USAGE}%" | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] 可用内存: $MEMORY_AVAILABLE → $NEW_MEMORY_AVAILABLE" | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] 释放内存: $((MEMORY_USAGE - NEW_MEMORY_USAGE))%" | tee -a "$LOG_FILE"

    # 如果内存使用率仍然很高，发送告警
    if [ "$NEW_MEMORY_USAGE" -gt 90 ]; then
        echo "[$TIMESTAMP] ⚠️  警告：内存使用率仍然很高 (${NEW_MEMORY_USAGE}%)，需要人工介入！" | tee -a "$LOG_FILE"
        # 这里可以添加发送邮件或webhook通知的逻辑
    fi
else
    echo "[$TIMESTAMP] ✅ 内存使用率正常 (${MEMORY_USAGE}% < ${THRESHOLD}%)" | tee -a "$LOG_FILE"
fi

echo "[$TIMESTAMP] ========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
