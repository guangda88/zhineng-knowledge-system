#!/bin/bash
# -*- coding: utf-8 -*-
# SafeLine 安装脚本
# 适用于 Ubuntu/Debian/CentOS

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

if [ "$EUID" -ne 0 ]; then 
    log_error "请使用 root 权限运行此脚本"
    exit 1
fi

log_info "开始安装 SafeLine..."

# 下载并安装
log_info "下载安装脚本..."
curl -fsSLk https://waf-ce.chaitin.cn/release/latest/setup.sh -o /tmp/safeline_install.sh && \
bash /tmp/safeline_install.sh || {
    log_error "SafeLine 安装失败"
    exit 1
}

log_info "SafeLine 安装成功！"
echo "访问地址: https://$(hostname -I | awk '{print $1}):9443"
echo "默认端口: 9443"
echo "请根据控制台提示完成初始化配置。"
