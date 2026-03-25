#!/bin/bash
# 快速检查脚本（无依赖版）

echo "======================================"
echo "   快速开发检查"
echo "======================================"
echo ""

# 1. 检查 Python 语法
echo "[1/3] Python 语法检查..."
if python3 -m py_compile backend/main.py 2>/dev/null; then
    echo "✅ 语法检查通过"
else
    echo "❌ 语法错误"
    exit 1
fi

# 2. 检查配置文件
echo "[2/3] 配置文件检查..."
config_files=(
    "docker-compose.yml"
    "nginx/nginx.conf"
    "pytest.ini"
)
for file in "${config_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file 存在"
    else
        echo "⚠️  $file 缺失"
    fi
done

# 3. 服务状态
echo "[3/3] 服务状态检查..."
if docker ps --format '{{.Names}}' | grep -q "kb-api-new"; then
    echo "✅ API 服务运行中"
else
    echo "⚠️  API 服务未运行"
fi

echo ""
echo "快速检查完成！"
