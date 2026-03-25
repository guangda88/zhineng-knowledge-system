#!/bin/bash
# -*- coding: utf-8 -*-
# Node Exporter 部署脚本

set -e

VERSION="1.7.0"
USER="node_exporter"

echo "=========================================="
echo "  部署 Node Exporter"
echo "=========================================="
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo "请使用 root 权限运行此脚本"
    exit 1
fi

echo "【创建用户】"
if ! id "$USER" &>/dev/null; then
    useradd -rs $USER
fi

echo "【下载 Node Exporter】"
wget https://github.com/prometheus/node_exporter/releases/download/v${VERSION}/node_exporter-${VERSION}.linux-amd64.tar.gz -O /tmp/node_exporter.tar.gz

echo "【解压并安装】"
tar xvfz /tmp/node_exporter.tar.gz -C /tmp/
mv /tmp/node_exporter-${VERSION}.linux-amd64/node_exporter /usr/local/bin/
chown $USER:$USER /usr/local/bin/node_exporter

echo "【创建 Systemd 服务】"
cat <<SERVICE >/etc/systemd/system/node_exporter.service
[Unit]
Description=Node Exporter
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=/usr/local/bin/node_exporter --web.listen-address=:9100

[Install]
WantedBy=multi-user.target
SERVICE

echo "【启动服务】"
systemctl daemon-reload
systemctl enable node_exporter
systemctl restart node_exporter

echo "【检查状态】"
systemctl status node_exporter | head -10

echo ""
echo "✅ Node Exporter 部署完成"
echo "   监听端口: 9100"
