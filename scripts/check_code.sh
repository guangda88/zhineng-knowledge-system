#!/bin/bash
# 智能知识系统 - 代码质量检查脚本
# 用途: 运行所有代码检查工具
# 使用: bash scripts/check_code.sh [选项]

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 切换到项目根目录
cd "$(dirname "$0")/.."

# 配置
PYTHON_DIRS=("backend" "services" "middleware" "analytics" "scripts")
MAX_LINE_LENGTH=100

# 显示帮助
show_help() {
    cat << EOF
代码质量检查脚本

用法: bash scripts/check_code.sh [选项] [路径...]

选项:
    -h, --help          显示此帮助信息
    -f, --fix           自动修复问题
    -v, --verbose       详细输出
    --no-format         跳过格式检查
    --no-lint           跳过代码规范检查
    --no-security       跳过安全检查
    --no-type           跳过类型检查

示例:
    bash scripts/check_code.sh              # 检查所有目录
    bash scripts/check_code.sh -f           # 自动修复问题
    bash scripts/check_code.sh backend/     # 检查特定目录

EOF
}

# 解析参数
AUTO_FIX=false
VERBOSE=false
SKIP_FORMAT=false
SKIP_LINT=false
SKIP_SECURITY=false
SKIP_TYPE=false
CHECK_PATHS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -f|--fix)
            AUTO_FIX=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --no-format)
            SKIP_FORMAT=true
            shift
            ;;
        --no-lint)
            SKIP_LINT=true
            shift
            ;;
        --no-security)
            SKIP_SECURITY=true
            shift
            ;;
        --no-type)
            SKIP_TYPE=true
            shift
            ;;
        -*)
            error "未知选项: $1"
            show_help
            exit 1
            ;;
        *)
            CHECK_PATHS+=("$1")
            shift
            ;;
    esac
done

# 使用指定路径或默认路径
if [[ ${#CHECK_PATHS[@]} -eq 0 ]]; then
    CHECK_PATHS=("${PYTHON_DIRS[@]}")
fi

# 过滤不存在的路径
EXISTING_PATHS=()
for path in "${CHECK_PATHS[@]}"; do
    if [[ -d "$path" ]] || [[ -f "$path" ]]; then
        EXISTING_PATHS+=("$path")
    else
        warn "路径不存在，跳过: $path"
    fi
done
CHECK_PATHS=("${EXISTING_PATHS[@]}")

if [[ ${#CHECK_PATHS[@]} -eq 0 ]]; then
    error "没有有效的路径可检查"
    exit 1
fi

echo
echo "======================================"
echo "   智能知识系统 - 代码质量检查"
echo "======================================"
echo
info "检查路径: ${CHECK_PATHS[*]}"
echo

# 统计变量
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# 检查函数
run_check() {
    local name="$1"
    local cmd="$2"
    local fix_cmd="${3:-}"

    info "检查: $name"

    if [[ "$AUTO_FIX" == "true" ]] && [[ -n "$fix_cmd" ]]; then
        if bash -c "$fix_cmd" > /dev/null 2>&1; then
            success "$name: 已自动修复"
            ((PASS_COUNT++))
        else
            warn "$name: 修复失败"
            ((WARN_COUNT++))
        fi
    else
        if bash -c "$cmd" > /dev/null 2>&1; then
            success "$name: 通过"
            ((PASS_COUNT++))
        else
            error "$name: 失败"
            if [[ "$VERBOSE" == "true" ]]; then
                bash -c "$cmd" || true
            fi
            ((FAIL_COUNT++))
            return 1
        fi
    fi
    echo
}

# 1. 格式检查 (Black + isort)
if [[ "$SKIP_FORMAT" == "false" ]]; then
    info "[1/4] 格式检查..."
    echo

    for path in "${CHECK_PATHS[@]}"; do
        if [[ ! -d "$path" ]]; then
            continue
        fi

        # Black 检查
        if command -v black &> /dev/null; then
            run_check "Black ($path)" \
                "black --check --line-length=$MAX_LINE_LENGTH $path" \
                "black --line-length=$MAX_LINE_LENGTH $path"
        else
            warn "black 未安装，跳过"
        fi

        # isort 检查
        if command -v isort &> /dev/null; then
            run_check "isort ($path)" \
                "isort --check --profile black $path" \
                "isort --profile black $path"
        else
            warn "isort 未安装，跳过"
        fi
    done
else
    info "[1/4] 格式检查: 已跳过"
    echo
fi

# 2. 代码规范检查 (flake8)
if [[ "$SKIP_LINT" == "false" ]]; then
    info "[2/4] 代码规范检查..."
    echo

    if command -v flake8 &> /dev/null; then
        for path in "${CHECK_PATHS[@]}"; do
            if [[ ! -d "$path" ]]; then
                continue
            fi
            run_check "flake8 ($path)" "flake8 --config=.flake8 $path"
        done
    else
        warn "flake8 未安装，跳过"
    fi
else
    info "[2/4] 代码规范检查: 已跳过"
    echo
fi

# 3. 安全检查 (bandit)
if [[ "$SKIP_SECURITY" == "false" ]]; then
    info "[3/4] 安全检查..."
    echo

    if command -v bandit &> /dev/null; then
        for path in "${CHECK_PATHS[@]}"; do
            if [[ ! -d "$path" ]]; then
                continue
            fi
            # 跳过测试目录
            if [[ "$path" == *"test"* ]]; then
                continue
            fi
            run_check "bandit ($path)" "bandit -c pyproject.toml -r $path"
        done
    else
        warn "bandit 未安装，跳过"
    fi
else
    info "[3/4] 安全检查: 已跳过"
    echo
fi

# 4. 类型检查 (mypy)
if [[ "$SKIP_TYPE" == "false" ]]; then
    info "[4/4] 类型检查..."
    echo

    if command -v mypy &> /dev/null; then
        for path in "${CHECK_PATHS[@]}"; do
            if [[ ! -d "$path" ]]; then
                continue
            fi
            if run_check "mypy ($path)" "mypy --config-file=pyproject.toml $path 2>&1 | head -20"; then
                ((PASS_COUNT++))
            else
                ((WARN_COUNT++))
            fi
        done
    else
        warn "mypy 未安装，跳过（可选）"
    fi
else
    info "[4/4] 类型检查: 已跳过"
    echo
fi

# 显示结果
echo "======================================"
echo "   检查结果摘要"
echo "======================================"
echo
success "通过: $PASS_COUNT"
if [[ $WARN_COUNT -gt 0 ]]; then
    warn "警告: $WARN_COUNT"
fi
if [[ $FAIL_COUNT -gt 0 ]]; then
    error "失败: $FAIL_COUNT"
fi
echo

if [[ $FAIL_COUNT -gt 0 ]]; then
    error "代码检查未通过"
    info "运行 'bash scripts/check_code.sh -f' 自动修复部分问题"
    exit 1
elif [[ $WARN_COUNT -gt 0 ]]; then
    warn "代码检查通过，但有警告"
    exit 0
else
    success "所有检查通过！"
    exit 0
fi
