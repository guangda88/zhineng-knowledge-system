#!/bin/bash
# 代码质量检查脚本

set -e

echo "======================================"
echo "   智能知识系统 - 代码质量检查"
echo "======================================"
echo ""

BACKEND_DIR="backend"

# 1. 格式检查
echo "[1/4] 代码格式检查..."
if isort "$BACKEND_DIR" --profile black --check-only; then
    echo "✅ isort 检查通过"
else
    echo "❌ isort 检查失败"
    echo "运行: isort $BACKEND_DIR --profile black"
    exit 1
fi

# 2. 代码规范检查
echo "[2/4] 代码规范检查..."
if flake8 "$BACKEND_DIR" --max-line-length=100 --ignore=E203,W503,E501; then
    echo "✅ flake8 检查通过"
else
    echo "❌ flake8 检查失败"
    exit 1
fi

# 3. 类型检查（可选）
echo "[3/4] 类型检查..."
if command -v mypy &> /dev/null; then
    if mypy "$BACKEND_DIR" --ignore-missing-imports 2>/dev/null; then
        echo "✅ mypy 检查通过"
    else
        echo "⚠️  mypy 检查有警告（非阻塞）"
    fi
else
    echo "⚠️  mypy 未安装（可选）"
fi

# 4. 测试检查
echo "[4/4] 测试检查..."
if pytest tests/ -v --tb=short -q 2>&1 | grep -q "passed"; then
    echo "✅ 测试检查通过"
else
    echo "❌ 测试检查失败"
    echo "运行: pytest tests/ -v"
    exit 1
fi

echo ""
echo "======================================"
echo "   ✅ 所有检查通过！"
echo "======================================"
