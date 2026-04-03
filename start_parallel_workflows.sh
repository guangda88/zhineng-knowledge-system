#!/bin/bash
#
# 启动双团队并行工作流
#
# 使用方法:
#   ./start_parallel_workflows.sh [options]
#
# 选项:
#   --coordinator-only    仅启动协调器
#   --team-a-only         仅启动团队A
#   --team-b-only         仅启动团队B
#   --detach              后台运行
#   --help                显示帮助信息
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="/home/ai/zhineng-knowledge-system"
WORKFLOWS_DIR="$PROJECT_ROOT/.lingflow/workflows"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查LingFlow是否安装
check_lingflow() {
    if ! command -v lingflow &> /dev/null; then
        log_error "LingFlow未安装"
        echo "请安装LingFlow: pip install lingflow"
        exit 1
    fi
    log_success "LingFlow已安装: $(lingflow --version)"
}

# 检查项目环境
check_project_env() {
    log_info "检查项目环境..."

    # 检查Docker
    if ! docker-compose ps &> /dev/null; then
        log_error "Docker Compose未运行"
        echo "请先启动: docker-compose up -d"
        exit 1
    fi

    # 检查数据库连接
    if ! docker-compose exec -T postgres pg_isready -U lingzhi &> /dev/null; then
        log_error "数据库未就绪"
        exit 1
    fi

    log_success "项目环境检查通过"
}

# 创建必要的目录
setup_directories() {
    log_info "创建工作目录..."

    mkdir -p "$PROJECT_ROOT/.lingflow/workflows"
    mkdir -p "$PROJECT_ROOT/backend/migrations"
    mkdir -p "$PROJECT_ROOT/data/audio/test"
    mkdir -p "$PROJECT_ROOT/models"
    mkdir -p "$PROJECT_ROOT/docs"

    log_success "工作目录创建完成"
}

# 显示启动信息
show_banner() {
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║    灵知系统 - 双团队并行工作流启动器                 ║"
    echo "║    LingZhi System - Parallel Teams Launcher          ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    echo "版本: 1.0.0"
    echo "日期: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
}

# 显示工作流信息
show_workflows() {
    echo ""
    echo "可用的工作流:"
    echo ""
    echo "  1. 团队A - 文字数据处理 (14天)"
    echo "     - 正则检索、意图识别、推理路由"
    echo ""
    echo "  2. 团队B - 音频处理 (14天)"
    echo "     - ASR引擎集成、转写标注、标注界面"
    echo ""
    echo "  3. 协调器 - 并行管理 (28天)"
    echo "     - 管理双团队、集成测试、性能优化"
    echo ""
}

# 启动工作流
start_workflow() {
    local workflow_file=$1
    local workflow_name=$2
    local detach=$3

    log_info "启动工作流: $workflow_name"

    local cmd="lingflow run \"$workflow_file\""
    if [ "$detach" = "true" ]; then
        cmd="$cmd > /tmp/lingflow_${workflow_name}.log 2>&1 &"
        log_info "后台运行，日志: /tmp/lingflow_${workflow_name}.log"
    fi

    eval $cmd

    if [ $? -eq 0 ]; then
        log_success "工作流 '$workflow_name' 启动成功"
    else
        log_error "工作流 '$workflow_name' 启动失败"
        return 1
    fi
}

# 显示工作流状态
show_status() {
    log_info "查询工作流状态..."
    echo ""
    lingflow status
}

# 主函数
main() {
    local coordinator_only=false
    local team_a_only=false
    local team_b_only=false
    local detach=false

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --coordinator-only)
                coordinator_only=true
                shift
                ;;
            --team-a-only)
                team_a_only=true
                shift
                ;;
            --team-b-only)
                team_b_only=true
                shift
                ;;
            --detach)
                detach=true
                shift
                ;;
            --help)
                echo "用法: $0 [选项]"
                echo ""
                echo "选项:"
                echo "  --coordinator-only    仅启动协调器"
                echo "  --team-a-only         仅启动团队A"
                echo "  --team-b-only         仅启动团队B"
                echo "  --detach              后台运行"
                echo "  --help                显示帮助信息"
                echo ""
                echo "示例:"
                echo "  $0                    # 启动所有工作流"
                echo "  $0 --coordinator-only # 仅启动协调器"
                echo "  $0 --detach           # 后台运行所有工作流"
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                echo "使用 --help 查看帮助信息"
                exit 1
                ;;
        esac
    done

    # 显示启动信息
    show_banner
    show_workflows

    # 检查环境
    check_lingflow
    check_project_env
    setup_directories

    # 启动工作流
    echo ""
    log_info "准备启动工作流..."
    echo ""

    if [ "$coordinator_only" = "true" ]; then
        # 仅启动协调器
        start_workflow \
            "$WORKFLOWS_DIR/parallel_teams_coordinator.yaml" \
            "协调器" \
            "$detach"
    elif [ "$team_a_only" = "true" ]; then
        # 仅启动团队A
        start_workflow \
            "$WORKFLOWS_DIR/team_a_text_processing.yaml" \
            "团队A" \
            "$detach"
    elif [ "$team_b_only" = "true" ]; then
        # 仅启动团队B
        start_workflow \
            "$WORKFLOWS_DIR/team_b_audio_processing.yaml" \
            "团队B" \
            "$detach"
    else
        # 启动协调器（推荐）
        log_info "启动协调器（会自动管理两个团队的工作流）..."
        start_workflow \
            "$WORKFLOWS_DIR/parallel_teams_coordinator.yaml" \
            "协调器" \
            "$detach"
    fi

    # 显示状态
    if [ "$detach" = "false" ]; then
        echo ""
        sleep 2
        show_status
    fi

    # 提示信息
    echo ""
    log_success "工作流启动完成！"
    echo ""
    echo "查看状态:"
    echo "  lingflow status"
    echo ""
    echo "查看日志:"
    echo "  lingflow logs --follow"
    echo ""
    echo "停止工作流:"
    echo "  lingflow stop --all"
    echo ""
}

# 运行主函数
main "$@"
