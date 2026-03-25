#!/bin/bash
# 智能知识系统 - 代码自动格式化脚本
# 用途: 自动格式化 Python 代码
# 使用: bash scripts/format_code.sh [选项]

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
代码自动格式化脚本

用法: bash scripts/format_code.sh [选项] [路径...]

选项:
    -h, --help          显示此帮助信息
    -c, --check         仅检查，不修改文件
    -v, --verbose       详细输出

示例:
    bash scripts/format_code.sh              # 格式化所有目录
    bash scripts/format_code.sh -c           # 仅检查格式
    bash scripts/format_code.sh backend/     # 格式化特定目录

EOF
}

# 解析参数
CHECK_ONLY=false
VERBOSE=false
FORMAT_PATHS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--check)
            CHECK_ONLY=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -*)
            error "未知选项: $1"
            show_help
            exit 1
            ;;
        *)
            FORMAT_PATHS+=("$1")
            shift
            ;;
    esac
done

# 使用指定路径或默认路径
if [[ ${#FORMAT_PATHS[@]} -eq 0 ]]; then
    FORMAT_PATHS=("${PYTHON_DIRS[@]}")
fi

# 过滤不存在的路径
EXISTING_PATHS=()
for path in "${FORMAT_PATHS[@]}"; do
    if [[ -d "$path" ]] || [[ -f "$path" ]]; then
        EXISTING_PATHS+=("$path")
    else
        warn "路径不存在，跳过: $path"
    fi
done
FORMAT_PATHS=("${EXISTING_PATHS[@]}")

if [[ ${#FORMAT_PATHS[@]} -eq 0 ]]; then
    error "没有有效的路径可格式化"
    exit 1
fi

echo
echo "======================================"
echo "   智能知识系统 - 代码格式化"
echo "======================================"
echo

if [[ "$CHECK_ONLY" == "true" ]]; then
    info "模式: 仅检查（不修改文件）"
else
    info "模式: 自动格式化"
fi
info "路径: ${FORMAT_PATHS[*]}"
echo

# 格式化函数
format_path() {
    local path="$1"
    local tool="$2"
    local args="$3"

    if [[ ! -d "$path" ]] && [[ ! -f "$path" ]]; then
        return 1
    fi

    local cmd="$tool $args $path"

    if [[ "$VERBOSE" == "true" ]]; then
        info "运行: $cmd"
    fi

    if bash -c "$cmd" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 统计
CHANGED_COUNT=0
NO_CHANGE_COUNT=0

# 1. Black 格式化
if command -v black &> /dev/null; then
    info "[1/2] Black 格式化..."

    local black_args="--line-length=$MAX_LINE_LENGTH --target-version=py312"
    if [[ "$CHECK_ONLY" == "true" ]]; then
        black_args="--check $black_args"
    fi

    for path in "${FORMAT_PATHS[@]}"; do
        if format_path "$path" "black" "$black_args"; then
            if [[ "$CHECK_ONLY" == "true" ]]; then
                success "Black ($path): 格式正确"
                ((NO_CHANGE_COUNT++))
            else
                success "Black ($path): 已格式化"
                ((CHANGED_COUNT++))
            fi
        else
            if [[ "$CHECK_ONLY" == "true" ]]; then
                error "Black ($path): 格式不正确"
                if [[ "$VERBOSE" == "true" ]]; then
                    black --check --diff $black_args "$path" 2>&1 | head -20 || true
                fi
            else
                warn "Black ($path): 部分文件需要手动检查"
            fi
        fi
    done
else
    warn "black 未安装，跳过。安装: pip install black"
fi
echo

# 2. isort 格式化
if command -v isort &> /dev/null; then
    info "[2/2] isort 格式化..."

    local isort_args="--profile=black --line-length=$MAX_LINE_LENGTH"
    if [[ "$CHECK_ONLY" == "true" ]]; then
        isort_args="--check $isort_args"
    fi

    for path in "${FORMAT_PATHS[@]}"; do
        if format_path "$path" "isort" "$isort_args"; then
            if [[ "$CHECK_ONLY" == "true" ]]; then
                success "isort ($path): 格式正确"
                ((NO_CHANGE_COUNT++))
            else
                success "isort ($path): 已格式化"
                ((CHANGED_COUNT++))
            fi
        else
            if [[ "$CHECK_ONLY" == "true" ]]; then
                error "isort ($path): 格式不正确"
                if [[ "$VERBOSE" == "true" ]]; then
                    isort --check --diff $isort_args "$path" 2>&1 | head -20 || true
                fi
            else
                warn "isort ($path): 部分文件需要手动检查"
            fi
        fi
    done
else
    warn "isort 未安装，跳过。安装: pip install isort"
fi
echo

# 显示结果
echo "======================================"
if [[ "$CHECK_ONLY" == "true" ]]; then
    if [[ $CHANGED_COUNT -eq 0 ]]; then
        success "所有文件格式正确！"
    else
        error "部分文件需要格式化"
        info "运行 'bash scripts/format_code.sh' 自动修复"
    fi
else
    if [[ $CHANGED_COUNT -gt 0 ]]; then
        success "已格式化 $CHANGED_COUNT 个路径"
    else
        success "所有文件格式已正确"
    fi
fi
echo "======================================"
