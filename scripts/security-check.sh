#!/bin/bash
# Source Map安全检查脚本
# 检查项目中是否意外包含Source Map文件

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "🔒 项目路径: $PROJECT_ROOT"
echo ""

# 检查函数
check_sourcemaps() {
    local dir=$1
    local desc=$2

    echo "📂 检查 $desc..."

    if [ ! -d "$dir" ]; then
        echo "⏭️  目录不存在，跳过"
        return
    fi

    # 查找.map文件（排除node_modules和.git）
    local found_files=$(find "$dir" -name "*.map" \
        -not -path "*/node_modules/*" \
        -not -path "*/.git/*" \
        -not -path "*/.claude/*" 2>/dev/null || true)

    if [ -n "$found_files" ]; then
        echo "❌ 发现Source Map文件！"
        echo "$found_files"
        return 1
    else
        echo "✅ 未发现Source Map文件"
        return 0
    fi
}

# 检查各目录
all_passed=true

# 检查前端构建目录
if ! check_sourcemaps "$PROJECT_ROOT/frontend-vue/dist" "前端构建目录 (frontend-vue/dist)"; then
    all_passed=false
fi
echo ""

# 检查项目根目录
if ! check_sourcemaps "$PROJECT_ROOT" "项目根目录"; then
    all_passed=false
fi
echo ""

# 总结
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$all_passed" = true ]; then
    echo "✅ 安全检查通过：未发现Source Map泄露"
    exit 0
else
    echo "❌ 安全检查失败：发现Source Map文件"
    echo ""
    echo "⚠️  请立即采取行动："
    echo "1. 删除发现的.map文件"
    echo "2. 检查.gitignore是否包含*.map规则"
    echo "3. 重新构建项目（使用--no-source-map）"
    echo "4. 清除CDN缓存"
    exit 1
fi
