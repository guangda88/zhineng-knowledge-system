#!/bin/bash
# 代码自动格式化脚本

echo "======================================"
echo "   智能知识系统 - 代码格式化"
echo "======================================"
echo ""

BACKEND_DIR="backend"

echo "[1/2] 格式化代码..."
isort "$BACKEND_DIR" --profile black
echo "✅ isort 格式化完成"

echo "[2/2] 排序导入..."
isort "$BACKEND_DIR" --profile black
echo "✅ 导入排序完成"

echo ""
echo "代码格式化完成！"
