#!/bin/bash
# 快速修复和启动脚本

echo "=== TCM系统快速修复和启动 ==="
echo ""

echo "1. 停止所有服务..."
docker-compose down

echo ""
echo "2. 重新构建Backend（包含修复）..."
docker-compose build --no-cache backend

echo ""
echo "3. 启动所有服务..."
docker-compose up -d

echo ""
echo "4. 等待服务启动..."
sleep 30

echo ""
echo "5. 检查服务状态..."
docker-compose ps

echo ""
echo "6. 查看Backend日志..."
docker logs tcm-backend --tail 50

echo ""
echo "7. 运行健康检查..."
./scripts/health_check.sh
