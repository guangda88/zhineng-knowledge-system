#!/bin/bash
# -*- coding: utf-8 -*-
# 快速修复 jdxb 服务和网络问题
# Quick Fix Script for jdxb Service and Network Issues
#
# 用途: 快速修复 jdxb 服务和 100.66.1.X 网段连接问题
# Usage: ./quick_fix_jdxb_and_network.sh

set -e  # 遇到错误立即退出

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
echo "  快速修复 jdxb 服务和网络问题"
echo "  Quick Fix Script for jdxb and Network"
echo "=========================================="
echo ""

# 1. 修复 jdxb 服务
log_info "Step 1: 检查 jdxb 服务..."
if ! docker ps | grep -q owjdxb; then
    if docker ps -a | grep -q owjdxb; then
        log_warning "容器存在但未运行，正在重启..."
        docker restart owjdxb
        log_success "jdxb 服务已重启"
    else
        log_warning "容器不存在，正在启动..."
        log_info "检查镜像是否存在..."
        if ! docker images | grep -q ionewu/owjdxb; then
            log_info "拉取镜像 ionewu/owjdxb:latest..."
            docker pull ionewu/owjdxb:latest || {
                log_error "镜像拉取失败，尝试使用 host 网络..."
                docker run -d \
                  --name owjdxb \
                  --net host \
                  --restart=unless-stopped \
                  ionewu/owjdxb:latest && log_success "jdxb 服务已启动"
                exit 0
            }
        fi
        
        docker run -d \
          --name owjdxb \
          --net host \
          --restart=unless-stopped \
          ionewu/owjdxb:latest && log_success "jdxb 服务已启动"
    fi
else
    log_success "jdxb 服务正在运行"
fi

# 2. 检查 VPN 连接
log_info "Step 2: 检查 VPN 连接..."
if ! ip link show | grep -q wg0; then
    log_warning "VPN 接口不存在"
    log_info "尝试启动 WireGuard..."
    if [ -f /etc/wireguard/wg0.conf ]; then
        sudo wg-quick up wg0 && log_success "VPN 已启动"
    else
        log_warning "WireGuard 配置文件不存在，跳过 VPN 启动"
    fi
else
    log_success "VPN 接口存在"
    if sudo wg show | grep -q "interface: wg0"; then
        log_success "VPN 正在运行"
    else
        log_warning "VPN 接口存在但未运行"
    fi
fi

# 3. 检查静态路由
log_info "Step 3: 检查静态路由..."
if ! ip route show | grep -q "100.66.1.0/24"; then
    log_warning "静态路由不存在"
    log_info "尝试添加静态路由..."
    sudo ip route add 100.66.1.0/24 via 192.168.2.1 2>/dev/null && log_success "静态路由已添加" || log_error "静态路由添加失败"
else
    log_success "静态路由已存在"
fi

# 4. 测试连接
log_info "Step 4: 测试连接..."
echo ""

# 测试 VPN 连接
log_info "测试 VPN 连接..."
if ping -c 1 -W 2 10.0.0.3 > /dev/null 2>&1; then
    log_success "VPN 连接正常 (10.0.0.3)"
else
    log_error "VPN 连接失败 (10.0.0.3)"
fi

# 测试远程服务器连接
log_info "测试远程服务器连接..."
if ping -c 1 -W 2 100.66.1.7 > /dev/null 2>&1; then
    log_success "远程服务器连接正常 (100.66.1.7)"
else
    log_error "远程服务器连接失败 (100.66.1.7)"
fi

# 测试 SSH 连接
log_info "测试 SSH 连接..."
if [ -f ~/.ssh/id_rsa_dell ]; then
    if ssh -p 2222 -i ~/.ssh/id_rsa_dell -o ConnectTimeout=5 -o BatchMode=yes ai@100.66.1.7 "echo 'SSH连接成功'" > /dev/null 2>&1; then
        log_success "SSH 连接正常 (100.66.1.7:2222)"
    else
        log_error "SSH 连接失败 (100.66.1.7:2222)"
    fi
else
    log_warning "SSH 密钥文件不存在 (~/.ssh/id_rsa_dell)"
fi

# 5. 服务状态汇总
echo ""
echo "=========================================="
echo "  服务状态汇总"
echo "=========================================="
echo ""

# Docker 容器状态
echo "【Docker 容器】"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAMES|owjdxb" || echo "  owjdxb 未运行"

# VPN 接口状态
echo ""
echo "【VPN 接口】"
ip link show | grep wg0 > /dev/null 2>&1 && echo "  wg0: 存在" || echo "  wg0: 不存在"

# 静态路由状态
echo ""
echo "【静态路由】"
ip route show | grep "100.66.1.0/24" > /dev/null 2>&1 && echo "  100.66.1.0/24: 已配置" || echo "  100.66.1.0/24: 未配置"

# 网络连接状态
echo ""
echo "【网络连接】"
ping -c 1 -W 2 10.0.0.3 > /dev/null 2>&1 && echo "  10.0.0.3: 通" || echo "  10.0.0.3: 不通"
ping -c 1 -W 2 100.66.1.7 > /dev/null 2>&1 && echo "  100.66.1.7: 通" || echo "  100.66.1.7: 不通"

echo ""
echo "=========================================="
echo "  修复完成"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  - jdxb 服务: http://192.168.2.1:9118"
echo "  - Prometheus: http://100.66.1.7:9090 (或 http://10.0.0.3:9090)"
echo "  - Grafana: http://100.66.1.7:3000 (或 http://10.0.0.3:3000)"
echo ""
echo "如果问题仍然存在，请查看详细报告:"
echo "  docs/troubleshooting/jdxb_and_network.md"
echo ""
