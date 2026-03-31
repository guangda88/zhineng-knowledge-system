#!/bin/bash
# 自动清理僵尸进程脚本
# 作者: Claude Code
# 创建日期: 2026-03-30

LOG_FILE="logs/cleanup_zombies.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 创建日志目录
mkdir -p "$(dirname "$LOG_FILE")"

# 统计僵尸进程数量
ZOMBIE_COUNT=$(ps aux | grep defunct | grep -v grep | wc -l)

echo "[$TIMESTAMP] 开始僵尸进程检查，当前数量: $ZOMBIE_COUNT" | tee -a "$LOG_FILE"

# 如果僵尸进程数量超过阈值，执行清理
if [ "$ZOMBIE_COUNT" -gt 10 ]; then
    echo "[$TIMESTAMP] ⚠️  发现 $ZOMBIE_COUNT 个僵尸进程，开始清理..." | tee -a "$LOG_FILE"

    # 查找所有僵尸进程的父进程ID（去重）
    ps -ef | grep defunct | grep -v grep | awk '{print $3}' | sort -u | while read PPID; do
        if [ -n "$PPID" ] && [ "$PPID" != "1" ] && [ "$PPID" != "" ]; then
            echo "[$TIMESTAMP] 检查父进程 PID: $PPID" | tee -a "$LOG_FILE"

            # 获取父进程详情
            PARENT_CMD=$(ps -p "$PPID" -o cmd= 2>/dev/null)

            # 检查是否是 Docker 容器进程
            CONTAINER_INFO=$(docker ps --filter "id=$PPID" --format "{{.Names}}" 2>/dev/null)

            if [ -n "$CONTAINER_INFO" ]; then
                echo "[$TIMESTAMP] 重启 Docker 容器: $CONTAINER_INFO" | tee -a "$LOG_FILE"
                docker restart "$CONTAINER_INFO" 2>&1 | tee -a "$LOG_FILE"
                sleep 2
            else
                # 非容器进程，检查父进程是否还存在
                if ps -p "$PPID" > /dev/null 2>&1; then
                    echo "[$TIMESTAMP] 父进程仍在运行: $PPID ($PARENT_CMD)" | tee -a "$LOG_FILE"
                    echo "[$TIMESTAMP] 发送 SIGCHLD 信号让父进程回收子进程" | tee -a "$LOG_FILE"
                    kill -CHLD "$PPID" 2>/dev/null
                    sleep 1
                fi
            fi
        fi
    done

    # 等待进程清理
    sleep 5

    # 统计清理后的僵尸进程数量
    NEW_COUNT=$(ps aux | grep defunct | grep -v grep | wc -l)
    CLEANED=$((ZOMBIE_COUNT - NEW_COUNT))

    echo "[$TIMESTAMP] ✅ 清理完成：$ZOMBIE_COUNT → $NEW_COUNT (清理了 $CLEANED 个)" | tee -a "$LOG_FILE"

    # 如果还有僵尸进程，记录详细信息
    if [ "$NEW_COUNT" -gt 0 ]; then
        echo "[$TIMESTAMP] 剩余僵尸进程详情：" | tee -a "$LOG_FILE"
        ps aux | grep defunct | grep -v grep | head -10 | tee -a "$LOG_FILE"
    fi
else
    echo "[$TIMESTAMP] ✅ 僵尸进程数量正常 ($ZOMBIE_COUNT 个)" | tee -a "$LOG_FILE"
fi

echo "========================================" | tee -a "$LOG_FILE"
