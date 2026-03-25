#!/bin/bash
# 环境检查脚本 - 阶段0
# 遵循开发规则：环境准备验收标准

echo "=== 智能知识系统 - 环境检查 ==="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查函数
check_pass() { echo -e "${GREEN}✅ $1${NC}"; }
check_fail() { echo -e "${RED}❌ $1${NC}"; }
check_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# 1. 检查 Docker
echo "1. 检查 Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    check_pass "Docker: $DOCKER_VERSION"
else
    check_fail "Docker 未安装"
fi
echo ""

# 2. 检查 Python
echo "2. 检查 Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    check_pass "Python: $PYTHON_VERSION"
    if command -v pip3 &> /dev/null; then
        check_pass "pip3 可用"
    else
        check_fail "pip3 未安装"
    fi
else
    check_fail "Python 未安装"
fi
echo ""

# 3. 检查 Node.js
echo "3. 检查 Node.js..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    check_pass "Node.js: $NODE_VERSION"
    if command -v npm &> /dev/null; then
        check_pass "npm: $(npm --version)"
    fi
else
    check_warn "Node.js 未安装 (前端开发需要)"
fi
echo ""

# 4. 检查端口占用
echo "4. 检查端口占用..."
for port in 5436 6381 8001 8008; do
    if ss -tlnp 2>/dev/null | grep -q ":$port " || netstat -tlnp 2>/dev/null | grep -q ":$port "; then
        check_warn "端口 $port 已被占用"
    else
        check_pass "端口 $port 可用"
    fi
done
echo ""

# 5. 检查项目目录结构
echo "5. 检查项目目录结构..."
cd /home/ai/zhineng-knowledge-system
for dir in backend frontend tests scripts data docs; do
    if [ -d "$dir" ]; then
        check_pass "目录 $dir/ 存在"
    else
        check_fail "目录 $dir/ 不存在"
    fi
done
echo ""

# 6. 检查配置文件
echo "6. 检查配置文件..."
for file in backend/config.py backend/requirements.txt tests/conftest.py DEVELOPMENT_RULES.md PHASED_IMPLEMENTATION_PLAN.md; do
    if [ -f "$file" ]; then
        check_pass "配置文件 $file 存在"
    else
        check_fail "配置文件 $file 不存在"
    fi
done
echo ""

echo "=== 环境检查完成 ==="
