#!/bin/bash
# -*- coding: utf-8 -*-
# 服务加固脚本

set -e

echo "=========================================="
echo "  服务安全加固"
echo "=========================================="
echo ""

echo "【1. 更新系统包】"
apt update && apt upgrade -y

echo "【2. 配置 UFW 防火墙】"
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 9443/tcp  # SafeLine
ufw allow 9100/tcp  # Node Exporter
echo "✅ UFW 已配置"

echo "【3. 修改 SSH 配置】"
if [ -f /etc/ssh/sshd_config ]; then
    sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
    systemctl restart sshd
    echo "✅ SSH 已配置 (禁止Root密码登录)"
else
    echo "⚠️ SSH 配置文件未找到"
fi

echo "【4. 安装 Fail2ban】"
apt install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban
echo "✅ Fail2ban 已启动"

echo ""
echo "=========================================="
echo "  加固完成"
echo "=========================================="
