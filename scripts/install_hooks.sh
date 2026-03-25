#!/bin/bash
# 安装 pre-commit 钩子

echo "安装 pre-commit..."
pip install pre-commit -q

echo "配置 pre-commit..."
pre-commit install --config .pre-commit-config.yaml

echo "✅ Pre-commit 钩子已安装"
