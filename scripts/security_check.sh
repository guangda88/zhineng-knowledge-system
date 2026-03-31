#!/bin/bash
# 安全检查脚本 - 在部署前自动运行
# 检查代码中的安全问题

set -e

echo "=========================================="
echo "安全检查脚本"
echo "=========================================="

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

# 1. 检查硬编码密码
echo ""
echo -e "${YELLOW}【1. 检查硬编码密码】${NC}"
if grep -r "zhineng123\|password.*=.*['\"]" \
    --include="*.py" \
    --exclude-dir=".git" \
    --exclude-dir="venv" \
    backend/ 2>/dev/null; then
    echo -e "${RED}❌ 发现硬编码密码${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✅ 未发现硬编码密码${NC}"
fi

# 2. 检查危险的CORS配置
echo ""
echo -e "${YELLOW}【2. 检查CORS配置】${NC}"
if grep -r 'allow_origins=\["\*"\]' \
    --include="*.py" \
    backend/ 2>/dev/null; then
    echo -e "${RED}❌ 发现危险的CORS配置${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✅ CORS配置安全${NC}"
fi

# 3. 检查裸异常处理
echo ""
echo -e "${YELLOW}【3. 检查裸异常处理】${NC}"
BARE_EXCEPTIONS=$(grep -rn 'except:' \
    --include="*.py" \
    backend/ 2>/dev/null | wc -l)
if [ "$BARE_EXCEPTIONS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  发现 $BARE_EXCEPTIONS 处裸异常处理${NC}"
    WARNINGS=$((WARNINGS + BARE_EXCEPTIONS))
else
    echo -e "${GREEN}✅ 未发现裸异常处理${NC}"
fi

# 4. 检查SQL注入风险
echo ""
echo -e "${YELLOW}【4. 检查SQL注入风险】${NC}"
if grep -r 'f".*SELECT.*{' \
    --include="*.py" \
    backend/ 2>/dev/null | grep -v "fetchval\|fetchrow"; then
    echo -e "${YELLOW}⚠️  可能存在SQL注入风险${NC}"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✅ 未发现明显的SQL注入风险${NC}"
fi

# 5. 检查容器资源限制
echo ""
echo -e "${YELLOW}【5. 检查容器资源限制】${NC}"
SERVICES_WITHOUT_LIMITS=$(grep -A 10 "services:" docker-compose.yml | \
    grep -B 10 "image:" | \
    grep -c "deploy:" || echo "0")
TOTAL_SERVICES=$(grep -c "image:" docker-compose.yml || echo "0")

if [ "$SERVICES_WITHOUT_LIMITS" -lt "$TOTAL_SERVICES" ]; then
    echo -e "${YELLOW}⚠️  有 $((TOTAL_SERVICES - SERVICES_WITHOUT_LIMITS)) 个服务缺少资源限制${NC}"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✅ 所有服务都有资源限制${NC}"
fi

# 6. 检查环境变量配置
echo ""
echo -e "${YELLOW}【6. 检查环境变量配置】${NC}"
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env 文件不存在${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✅ .env 文件存在${NC}"

    # 检查关键配置
    if grep -q "DATABASE_URL.*zhineng123" .env 2>/dev/null; then
        echo -e "${RED}❌ .env 包含默认密码${NC}"
        ERRORS=$((ERRORS + 1))
    fi
fi

# 总结
echo ""
echo "=========================================="
echo "检查结果"
echo "=========================================="
echo -e "错误: ${RED}$ERRORS${NC}"
echo -e "警告: ${YELLOW}$WARNINGS${NC}"

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}❌ 安全检查失败！请修复错误后再部署。${NC}"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  发现 $WARNINGS 个警告，建议修复。${NC}"
    exit 0
else
    echo -e "${GREEN}✅ 安全检查通过！${NC}"
    exit 0
fi
