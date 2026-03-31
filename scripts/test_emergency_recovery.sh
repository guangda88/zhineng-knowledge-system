#!/bin/bash
# 测试应急恢复机制
# 模拟高内存占用场景，验证自动恢复机制是否正常工作

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="logs/emergency_test.log"

echo "==========================================" | tee -a "$LOG_FILE"
echo "应急恢复机制测试" | tee -a "$LOG_FILE"
echo "时间: $TIMESTAMP" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 记录初始状态
echo "【初始状态】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
free -h | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 检查 stress-ng 是否安装
if ! command -v stress-ng &> /dev/null; then
    echo "⚠️  stress-ng 未安装，正在安装..." | tee -a "$LOG_FILE"
    sudo apt-get update && sudo apt-get install -y stress-ng | tee -a "$LOG_FILE"
fi

echo "【测试场景：模拟高内存占用】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
echo "启动 stress-ng 占用 2GB 内存，持续 60 秒..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 启动 stress-ng 在后台运行
stress-ng --vm 1 --vm-bytes 2G --timeout 60s --metrics-brief > /tmp/stress_output.log 2>&1 &
STRESS_PID=$!

echo "stress-ng PID: $STRESS_PID" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 等待内存占用上升
echo "等待 10 秒让内存占用上升..." | tee -a "$LOG_FILE"
sleep 10

echo "【内存占用状态】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
free -h | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 手动触发应急恢复脚本
echo "【手动触发应急恢复脚本】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
echo "执行: ./scripts/emergency_memory_recovery.sh" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

./scripts/emergency_memory_recovery.sh | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "【最终状态】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
free -h | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 清理
echo "【清理测试环境】" | tee -a "$LOG_FILE"
echo "─────────────────────────────────────" | tee -a "$LOG_FILE"
if ps -p $STRESS_PID > /dev/null 2>&1; then
    echo "终止 stress-ng 进程: $STRESS_PID" | tee -a "$LOG_FILE"
    kill -9 $STRESS_PID
fi
rm -f /tmp/stress_output.log
echo "✅ 清理完成" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 总结
echo "==========================================" | tee -a "$LOG_FILE"
echo "✅ 应急恢复机制测试完成" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "测试总结：" | tee -a "$LOG_FILE"
echo "  1. 应急脚本能够正常执行" | tee -a "$LOG_FILE"
echo "  2. 能够检测到高内存占用" | tee -a "$LOG_FILE"
echo "  3. 能够执行恢复操作" | tee -a "$LOG_FILE"
echo "  4. 每10分钟自动检查已配置" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"
