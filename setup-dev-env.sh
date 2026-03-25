#!/bin/bash
# 智能知识系统 - 开发环境自动安装脚本
# 用途: 安装预提交钩子和开发依赖
# 使用: bash setup-dev-env.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查命令是否存在
command_exists() {
    command -v "$1" &> /dev/null
}

# 显示帮助信息
show_help() {
    cat << EOF
智能知识系统 - 开发环境安装脚本

用法: bash setup-dev-env.sh [选项]

选项:
    -h, --help          显示此帮助信息
    -s, --skip-hooks    跳过预提交钩子安装
    -c, --check-only    仅检查环境，不安装
    -v, --verbose       详细输出

示例:
    bash setup-dev-env.sh           # 完整安装
    bash setup-dev-env.sh -s        # 跳过钩子安装
    bash setup-dev-env.sh -c        # 仅检查环境

EOF
}

# 解析参数
SKIP_HOOKS=false
CHECK_ONLY=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -s|--skip-hooks)
            SKIP_HOOKS=true
            shift
            ;;
        -c|--check-only)
            CHECK_ONLY=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        *)
            error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 检查环境
check_environment() {
    info "检查开发环境..."

    local all_good=true

    # 检查 Python
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        success "Python: $PYTHON_VERSION"
    else
        error "Python3 未安装"
        all_good=false
    fi

    # 检查虚拟环境
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        success "虚拟环境已激活: $VIRTUAL_ENV"
    elif [[ -d "venv" ]]; then
        success "虚拟环境存在: venv/"
    else
        warn "虚拟环境不存在"
        all_good=false
    fi

    # 检查工具
    local tools=(black isort flake8 bandit mypy pre-commit)
    for tool in "${tools[@]}"; do
        if command_exists "$tool"; then
            VERSION=$($tool --version 2>&1 | head -1)
            success "$tool: $VERSION"
        else
            warn "$tool: 未安装"
            all_good=false
        fi
    done

    if [[ "$all_good" == "true" ]]; then
        success "环境检查完成 - 所有工具已安装"
        return 0
    else
        warn "环境检查完成 - 部分工具缺失"
        return 1
    fi
}

# 安装开发依赖
install_dependencies() {
    info "安装开发依赖..."

    # 核心依赖
    local core_deps=(
        "black>=25.0.0"
        "isort>=6.0.0"
        "flake8>=7.0.0"
        "flake8-docstrings"
        "flake8-bugbear"
        "flake8-comprehensions"
        "bandit[toml]>=1.8.0"
        "mypy>=1.0.0"
        "pre-commit>=4.0.0"
        "types-requests"
        "types-PyYAML"
    )

    for dep in "${core_deps[@]}"; do
        if [[ "$VERBOSE" == "true" ]]; then
            info "安装: $dep"
        fi
    done

    pip install -q "${core_deps[@]}" || {
        error "依赖安装失败"
        return 1
    }

    success "开发依赖安装完成"
}

# 安装预提交钩子
install_hooks() {
    if [[ "$SKIP_HOOKS" == "true" ]]; then
        info "跳过预提交钩子安装"
        return 0
    fi

    info "安装预提交钩子..."

    if ! command_exists pre-commit; then
        error "pre-commit 未安装，请检查安装步骤"
        return 1
    fi

    # 安装钩子
    pre-commit install
    pre-commit install-hooks

    # 检查是否在 git 仓库中
    if git rev-parse --git-dir > /dev/null 2>&1; then
        success "预提交钩子已安装到 .git/hooks/"
    else
        warn "当前不是 git 仓库，跳过钩子安装"
        return 1
    fi
}

# 验证配置
verify_config() {
    info "验证配置文件..."

    local config_files=(
        ".pre-commit-config.yaml:预提交配置"
        ".flake8:Flake8配置"
        "pyproject.toml:项目配置"
        "pytest.ini:Pytest配置"
    )

    for config in "${config_files[@]}"; do
        file="${config%%:*}"
        desc="${config##*:}"
        if [[ -f "$file" ]]; then
            success "$desc: $file"
        else
            warn "$desc: $file (不存在)"
        fi
    done
}

# 主流程
main() {
    echo
    echo "======================================"
    echo "   智能知识系统 - 开发环境配置"
    echo "======================================"
    echo

    # 仅检查模式
    if [[ "$CHECK_ONLY" == "true" ]]; then
        check_environment
        exit $?
    fi

    # 1. 检查 Python 环境
    info "[1/6] 检查 Python 环境..."
    if ! command_exists python3; then
        error "未找到 Python3，请先安装 Python 3.12+"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    success "Python 版本: $PYTHON_VERSION"
    echo

    # 2. 检查虚拟环境
    info "[2/6] 检查虚拟环境..."
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        if [[ ! -d "venv" ]]; then
            info "创建虚拟环境..."
            python3 -m venv venv
            success "虚拟环境创建完成"
        fi
        info "激活虚拟环境..."
        source venv/bin/activate
    else
        success "虚拟环境已激活: $VIRTUAL_ENV"
    fi
    echo

    # 3. 升级 pip
    info "[3/6] 升级 pip..."
    pip install --upgrade pip -q
    success "pip 已升级到最新版本"
    echo

    # 4. 安装开发依赖
    info "[4/6] 安装开发依赖..."
    install_dependencies
    echo

    # 5. 安装预提交钩子
    info "[5/6] 安装预提交钩子..."
    install_hooks
    echo

    # 6. 验证配置
    info "[6/6] 验证配置..."
    verify_config
    echo

    # 显示摘要
    echo "======================================"
    success "开发环境配置完成！"
    echo "======================================"
    echo
    info "已安装的工具:"
    echo "  - black:    代码格式化"
    echo "  - isort:    Import 排序"
    echo "  - flake8:   代码规范检查"
    echo "  - bandit:   安全检查"
    echo "  - mypy:     类型检查"
    echo "  - pre-commit: 预提交钩子"
    echo
    info "常用命令:"
    echo "  source venv/bin/activate          # 激活虚拟环境"
    echo "  pre-commit run --all-files        # 手动运行所有钩子"
    echo "  pre-commit run black --all-files  # 运行特定钩子"
    echo "  git commit --no-verify -m 'msg'   # 跳过钩子提交"
    echo "  pre-commit autoupdate             # 更新钩子版本"
    echo "  bash $0 -c                        # 检查环境"
    echo
    info "更多信息请参考:"
    echo "  - README.md"
    echo "  - DEVELOPMENT_RULES.md"
    echo "  - .pre-commit-config.yaml"
    echo
}

# 执行主流程
main "$@"
