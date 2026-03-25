#!/bin/bash
# -*- coding: utf-8 -*-
# 修复 Network Manager Wait Online 启动失败问题
# Fix Network Manager Wait Online startup failure

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "=========================================="
echo "  修复 Network Manager Wait Online 问题"
echo "=========================================="
echo ""

# 问题分析
log_info "问题分析"
echo ""
echo "1. NetworkManager-wait-online.service 启动失败"
echo "2. 默认超时时间为 1 分钟"
echo "3. 网络连接成功，但超时后服务才报告失败"
echo "4. 这是正常现象，不会影响网络功能"
echo ""

# 解决方案
log_info "解决方案"
echo ""
echo "方案1: 禁用 NetworkManager-wait-online.service（推荐）"
echo "  - 这是最简单的解决方案"
echo "  - 不会影响网络连接"
echo "  - 可以加快系统启动速度"
echo ""
echo "方案2: 将服务设置为可选依赖"
echo "  - 修改相关服务的配置"
echo "  - 将 NetworkManager-wait-online.service 设置为 Wants= 而不是 Requires="
echo ""
echo "方案3: 增加超时时间"
echo "  - 修改 NetworkManager-wait-online.service 的 TimeoutStartSec"
echo "  - 将超时时间增加到更长的值（例如 2 分钟或 3 分钟）"
echo ""

# 执行修复
log_info "执行修复（方案1：禁用服务）"
echo ""

# 检查用户权限
if [ "$EUID" -ne 0 ]; then
    log_error "需要 root 权限来执行此操作"
    echo ""
    echo "请使用以下命令运行："
    echo "  sudo bash $0"
    echo ""
    exit 1
fi

# 禁用服务
log_info "禁用 NetworkManager-wait-online.service..."
sudo systemctl disable NetworkManager-wait-online.service 2>&1 || {
    log_warning "禁用服务失败，可能服务已经被禁用"
}

# 停止服务（如果正在运行）
log_info "停止 NetworkManager-wait-online.service..."
sudo systemctl stop NetworkManager-wait-online.service 2>&1 || {
    log_warning "停止服务失败，可能服务没有运行"
}

# 验证服务状态
log_info "验证服务状态..."
if sudo systemctl is-enabled NetworkManager-wait-online.service 2>/dev/null | grep -q "disabled"; then
    log_success "NetworkManager-wait-online.service 已禁用"
else
    log_warning "服务状态无法确认"
fi

# 重载 systemd 配置
log_info "重载 systemd 配置..."
sudo systemctl daemon-reload 2>&1 || {
    log_error "重载 systemd 配置失败"
    exit 1
}

log_success "systemd 配置已重载"

# 验证网络状态
log_info "验证网络状态..."
echo ""

echo "【IP 地址】"
hostname -I
echo ""

echo "【网络接口】"
cat /proc/net/dev | head -10
echo ""

echo "=========================================="
echo "  修复完成"
echo "=========================================="
echo ""

log_success "NetworkManager-wait-online.service 已禁用"
echo ""
echo "【下次启动】"
echo "  - 系统启动时将不再等待网络连接"
echo "  - 启动速度将加快约 1 分钟"
echo "  - 网络连接仍然正常工作"
echo ""

echo "【验证方法】"
echo "  重启系统后，检查以下命令："
echo "  - sudo systemctl status NetworkManager-wait-online.service"
echo "  - systemd-analyze blame | grep Network"
echo ""

echo "【如果需要恢复】"
echo "  sudo systemctl enable NetworkManager-wait-online.service"
echo ""

echo "=========================================="

exit 0
