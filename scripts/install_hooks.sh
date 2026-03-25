#!/bin/bash
# 智能知识系统 - 预提交钩子安装脚本
# 用途: 快速安装/更新 pre-commit 钩子
# 使用: bash scripts/install_hooks.sh [选项]

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

# 显示帮助
show_help() {
    cat << EOF
预提交钩子安装脚本

用法: bash scripts/install_hooks.sh [选项]

选项:
    -h, --help      显示此帮助信息
    -u, --update    更新钩子版本
    -r, --run       安装后立即运行
    -c, --clean     清除旧钩子后重新安装

示例:
    bash scripts/install_hooks.sh        # 安装钩子
    bash scripts/install_hooks.sh -u     # 更新钩子
    bash scripts/install_hooks.sh -r     # 安装并运行

EOF
}

# 解析参数
UPDATE=false
RUN_AFTER=false
CLEAN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -u|--update)
            UPDATE=true
            shift
            ;;
        -r|--run)
            RUN_AFTER=true
            shift
            ;;
        -c|--clean)
            CLEAN=true
            shift
            ;;
        *)
            error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 检查是否在 git 仓库中
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    error "当前不是 git 仓库"
    exit 1
fi

# 清除旧钩子
if [[ "$CLEAN" == "true" ]]; then
    info "清除旧的预提交钩子..."
    rm -f .git/hooks/pre-commit
    rm -f .git/hooks/pre-push
    rm -f .git/hooks/commit-msg
    success "旧钩子已清除"
fi

# 更新钩子版本
if [[ "$UPDATE" == "true" ]]; then
    info "更新预提交钩子版本..."
    pre-commit autoupdate || {
        warn "自动更新失败，继续安装..."
    }
fi

# 安装 pre-commit
if ! command -v pre-commit &> /dev/null; then
    info "安装 pre-commit..."
    pip install pre-commit -q || {
        error "pre-commit 安装失败"
        exit 1
    }
else
    info "pre-commit 已安装: $(pre-commit --version | head -1)"
fi

# 安装钩子
info "安装预提交钩子..."
pre-commit install
pre-commit install-hooks

success "预提交钩子已安装"
echo

# 显示钩子列表
info "已配置的钩子:"
pre-commit run --all-files --show-diff-on-failure 2>&1 | grep -E "^- " || true
echo

# 运行钩子
if [[ "$RUN_AFTER" == "true" ]]; then
    info "运行钩子检查..."
    pre-commit run --all-files || {
        warn "部分钩子检查失败，请修复后重新提交"
    }
fi

info "完成！"
echo
info "提示:"
echo "  - 跳过钩子: git commit --no-verify -m 'msg'"
echo "  - 手动运行: pre-commit run --all-files"
echo "  - 更新钩子: bash scripts/install_hooks.sh -u"
