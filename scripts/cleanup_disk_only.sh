#!/bin/bash
# 清理快速脚本（不执行 VACUUM，只清理空间）

set -e

echo "=========================================="
echo "磁盘空间快速清理"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 错误: 此脚本需要 root 权限"
    echo "请使用: sudo bash $0"
    exit 1
fi

echo "【清理前的磁盘使用情况】"
df -h /
df -h /data
echo ""

echo "【1. 清理系统日志】"
echo "清理前日志占用："
sudo journalctl --disk-usage

echo "正在清理 7 天前的日志..."
sudo journalctl --vacuum-time=7d

echo "清理后日志占用："
sudo journalctl --disk-usage
echo ""

echo "【2. 清理 APT 缓存】"
sudo apt clean
sudo apt autoremove -y
echo "✅ APT 缓存已清理"
echo ""

echo "【3. 清理 Docker】"
echo "清理前 Docker 占用："
docker system df

echo "正在清理 Docker..."
docker system prune -a --volumes -f

echo "清理后 Docker 占用："
docker system df
echo ""

echo "【4. 清理用户缓存】"
rm -rf ~/.cache/thumbnails/*
rm -rf ~/.cache/pip/*
rm -rf ~/.cache/node/*
rm -rf ~/.cache/mozilla/firefox/*/cache2
echo "✅ 用户缓存已清理"
echo ""

echo "【清理后的磁盘使用情况】"
df -h /
df -h /data
echo ""

echo "=========================================="
echo "✅ 磁盘空间清理完成！"
echo "=========================================="
