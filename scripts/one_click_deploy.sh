#!/bin/bash
# ==============================================================================
# 智能知识系统 - 一键部署脚本
# ==============================================================================
# 功能：
#   - 一键部署应用
#   - 版本管理
#   - 健康检查
#   - 回滚支持
#   - 配置管理
#   - 日志记录
#   - 错误处理
#
# 用法:
#   ./one_click_deploy.sh deploy [env]         # 部署应用
#   ./one_click_deploy.sh rollback [version]   # 回滚版本
#   ./one_click_deploy.sh status               # 查看状态
#   ./one_click_deploy.sh health               # 健康检查
#   ./one_click_deploy.sh logs [service]       # 查看日志
#   ./one_click_deploy.sh stop                 # 停止服务
#   ./one_click_deploy.sh restart              # 重启服务
#   ./one_click_deploy.sh update               # 更新代码并部署
#   ./one_click_deploy.sh backup               # 部署前备份
#   ./one_click_deploy.sh version              # 查看当前版本
#
# 环境变量:
#   DEPLOY_ENV              部署环境 (dev/staging/prod)
#   AUTO_BACKUP             部署前自动备份 (默认: true)
#   HEALTH_CHECK_TIMEOUT    健康检查超时时间 (默认: 300秒)
#   LOG_FILE                日志文件路径
# ==============================================================================

set -euo pipefail

# ==============================================================================
# 配置部分
# ==============================================================================

# 颜色输出
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly MAGENTA='\033[0;35m'
readonly NC='\033[0m'

# 目录配置
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly DEPLOY_DIR="${DEPLOY_DIR:-$PROJECT_DIR/.deploy}"
readonly VERSION_FILE="$DEPLOY_DIR/version.json"
readonly LOG_DIR="${LOG_DIR:-$PROJECT_DIR/logs}"

# 部署配置
DEPLOY_ENV="${DEPLOY_ENV:-dev}"
AUTO_BACKUP=${AUTO_BACKUP:-true}
HEALTH_CHECK_TIMEOUT=${HEALTH_CHECK_TIMEOUT:-300}
HEALTH_CHECK_INTERVAL=${HEALTH_CHECK_INTERVAL:-5}

# 服务列表
readonly SERVICES=("postgres" "redis" "api" "nginx" "prometheus" "grafana")

# 时间戳
readonly TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 日志文件
LOG_FILE="${LOG_FILE:-$LOG_DIR/deploy_$(date +%Y%m%d).log}"

# ==============================================================================
# 日志函数
# ==============================================================================

# 初始化日志目录
init_logging() {
    mkdir -p "$LOG_DIR" "$DEPLOY_DIR"
    touch "$LOG_FILE"
}

# 日志输出
log_info() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $*"
    echo -e "${GREEN}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_warn() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $*"
    echo -e "${YELLOW}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_error() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*"
    echo -e "${RED}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [DEBUG] $*"
        echo -e "${BLUE}${msg}${NC}"
        echo "$msg" >> "$LOG_FILE"
    fi
}

log_step() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [STEP] $*"
    echo -e "${CYAN}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_success() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [SUCCESS] $*"
    echo -e "${MAGENTA}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

# ==============================================================================
# 错误处理
# ==============================================================================

# 错误处理器
error_handler() {
    local line_number=$1
    local error_code=$2
    log_error "部署在第 ${line_number} 行失败，错误码: ${error_code}"
    log_error "请检查日志: $LOG_FILE"
    exit "$error_code"
}

# 设置错误陷阱
trap 'error_handler ${LINENO} $?' ERR

# ==============================================================================
# 确认函数
# ==============================================================================

confirm() {
    local prompt=$1
    local default=${2:-n}

    if [[ "${FORCE_CONFIRM:-false}" == "true" ]]; then
        return 0
    fi

    local prompt_text="$prompt"
    if [[ "$default" == "y" ]]; then
        prompt_text="$prompt [Y/n]: "
    else
        prompt_text="$prompt [y/N]: "
    fi

    read -p "$prompt_text" response
    response=${response:-$default}

    [[ "$response" =~ ^[Yy]$ ]]
}

# ==============================================================================
# 版本管理
# ==============================================================================

# 获取当前版本
get_current_version() {
    if [[ -f "$VERSION_FILE" ]]; then
        grep -oP '"current":\s*"\K[^"]+' "$VERSION_FILE" 2>/dev/null || echo "unknown"
    else
        echo "unknown"
    fi
}

# 获取上一个版本
get_previous_version() {
    if [[ -f "$VERSION_FILE" ]]; then
        grep -oP '"previous":\s*"\K[^"]+' "$VERSION_FILE" 2>/dev/null || echo ""
    else
        echo ""
    fi
}

# 生成版本号
generate_version() {
    local prefix="v"
    local date=$(date +%Y%m%d)
    local time=$(date +%H%M%S)
    local git_commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    echo "${prefix}${date}.${time}+${git_commit}"
}

# 保存版本信息
save_version() {
    local current_version=$1
    local previous_version=$(get_current_version)

    cat > "$VERSION_FILE" << EOF
{
  "current": "$current_version",
  "previous": "$previous_version",
  "deploy_time": "$(date -Iseconds)",
  "environment": "$DEPLOY_ENV",
  "user": "$(whoami)",
  "hostname": "$(hostname)"
}
EOF

    log_info "版本信息已保存: $current_version"
}

# ==============================================================================
# 备份函数
# ==============================================================================

# 部署前备份
create_deployment_backup() {
    if [[ "$AUTO_BACKUP" != "true" ]]; then
        return 0
    fi

    log_step "创建部署前备份..."

    local backup_dir="$DEPLOY_DIR/backups/pre_deploy_${TIMESTAMP}"

    # 备份数据库
    log_info "备份数据库..."
    docker-compose exec -T postgres pg_dump -U zhineng zhineng_kb \
        --no-owner --no-acl 2>/dev/null | gzip > "$backup_dir.db.sql.gz" || {
        log_warn "数据库备份失败"
    }

    # 备份配置
    log_info "备份配置..."
    mkdir -p "$backup_dir"
    cp -f "$PROJECT_DIR/docker-compose.yml" "$backup_dir/" 2>/dev/null || true
    cp -f "$PROJECT_DIR/.env" "$backup_dir/" 2>/dev/null || true

    # 保存备份信息
    cat > "$DEPLOY_DIR/last_backup.info" << EOF
backup_dir=$backup_dir
timestamp=$TIMESTAMP
version=$(get_current_version)
EOF

    log_info "部署前备份完成: $backup_dir"
}

# ==============================================================================
# 检查函数
# ==============================================================================

# 检查前置条件
check_prerequisites() {
    log_step "检查前置条件..."

    local checks_failed=0

    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        ((checks_failed++))
    fi

    # 检查 Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装"
        ((checks_failed++))
    fi

    # 检查 Docker 守护进程
    if ! docker ps &> /dev/null; then
        log_error "Docker 守护进程未运行"
        ((checks_failed++))
    fi

    # 检查配置文件
    if [[ ! -f "$PROJECT_DIR/docker-compose.yml" ]]; then
        log_error "docker-compose.yml 不存在"
        ((checks_failed++))
    fi

    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        log_warn ".env 文件不存在，将从 .env.example 创建"
        if [[ -f "$PROJECT_DIR/.env.example" ]]; then
            cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        else
            log_error ".env.example 不存在"
            ((checks_failed++))
        fi
    fi

    if [[ $checks_failed -gt 0 ]]; then
        log_error "前置条件检查失败: $checks_failed 项检查未通过"
        return 1
    fi

    log_info "前置条件检查通过"
    return 0
}

# 检查端口占用
check_ports() {
    log_step "检查端口占用..."

    local ports=(5436 6381 8001 8008 9090 3000 9121 9187)
    local occupied=0

    for port in "${ports[@]}"; do
        if docker ps --format '{{.Ports}}' | grep -q ":$port->"; then
            log_warn "端口 $port 已被容器使用"
        elif netstat -tuln 2>/dev/null | grep -q ":$port "; then
            log_warn "端口 $port 已被占用"
            ((occupied++))
        fi
    done

    if [[ $occupied -gt 0 ]]; then
        log_warn "有 $occupied 个端口被占用"
        if ! confirm "是否继续部署?" n; then
            return 1
        fi
    fi

    return 0
}

# ==============================================================================
# 部署函数
# ==============================================================================

# 构建镜像
build_images() {
    log_step "构建 Docker 镜像..."

    cd "$PROJECT_DIR"

    # 构建后端镜像
    log_info "构建后端 API 镜像..."
    if docker-compose build --no-cache api 2>&1 | tee -a "$LOG_FILE"; then
        log_info "后端镜像构建成功"
    else
        log_error "后端镜像构建失败"
        return 1
    fi

    return 0
}

# 启动服务
start_services() {
    log_step "启动服务..."

    cd "$PROJECT_DIR"

    # 拉取最新镜像
    log_info "拉取最新镜像..."
    docker-compose pull -q 2>/dev/null || true

    # 启动服务
    log_info "启动服务..."
    if docker-compose up -d 2>&1 | tee -a "$LOG_FILE"; then
        log_info "服务启动成功"
    else
        log_error "服务启动失败"
        return 1
    fi

    return 0
}

# 停止服务
stop_services() {
    log_step "停止服务..."

    cd "$PROJECT_DIR"

    if docker-compose down 2>&1 | tee -a "$LOG_FILE"; then
        log_info "服务已停止"
    else
        log_warn "停止服务时出现警告"
    fi

    return 0
}

# 重启服务
restart_services() {
    log_step "重启服务..."

    cd "$PROJECT_DIR"

    if docker-compose restart 2>&1 | tee -a "$LOG_FILE"; then
        log_info "服务已重启"
    else
        log_error "服务重启失败"
        return 1
    fi

    return 0
}

# ==============================================================================
# 健康检查
# ==============================================================================

# 检查单个服务健康状态
check_service_health() {
    local service=$1
    local timeout=$2

    log_info "检查 ${service} 服务健康状态..."

    local start_time=$(date +%s)
    local end_time=$((start_time + timeout))

    while [[ $(date +%s) -lt $end_time ]]; do
        local container_id=$(docker ps -q -f "name=zhineng-${service}" 2>/dev/null || echo "")

        if [[ -z "$container_id" ]]; then
            log_warn "容器 zhineng-${service} 未运行"
            return 1
        fi

        local health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_id" 2>/dev/null || echo "none")

        case "$health_status" in
            healthy)
                log_info "✓ ${service} 服务健康"
                return 0
                ;;
            unhealthy)
                log_error "✗ ${service} 服务不健康"
                return 1
                ;;
            none|starting)
                # 容器没有健康检查或正在启动，检查容器是否在运行
                if docker exec "$container_id" echo "ok" &>/dev/null; then
                    log_info "✓ ${service} 服务运行中"
                    return 0
                fi
                ;;
        esac

        sleep "$HEALTH_CHECK_INTERVAL"
    done

    log_error "✗ ${service} 服务健康检查超时"
    return 1
}

# 执行健康检查
health_check() {
    log_step "执行健康检查..."

    local critical_failed=0
    local optional_failed=0

    # 关键服务检查
    for service in postgres redis api; do
        if ! check_service_health "$service" "$HEALTH_CHECK_TIMEOUT"; then
            if [[ "$service" == "postgres" ]] || [[ "$service" == "redis" ]] || [[ "$service" == "api" ]]; then
                ((critical_failed++))
            else
                ((optional_failed++))
            fi
        fi
    done

    # 可选服务检查
    for service in nginx prometheus grafana; do
        if ! check_service_health "$service" 60; then
            ((optional_failed++))
        fi
    done

    # API 端点检查
    log_info "检查 API 端点..."
    if curl -sf http://localhost:8001/health &>/dev/null; then
        log_info "✓ API 健康检查端点正常"
    else
        log_warn "✗ API 健康检查端点无响应"
        ((optional_failed++))
    fi

    if [[ $critical_failed -gt 0 ]]; then
        log_error "关键服务健康检查失败: $critical_failed 个"
        return 1
    fi

    if [[ $optional_failed -gt 0 ]]; then
        log_warn "可选服务健康检查失败: $optional_failed 个"
    fi

    log_success "健康检查完成"
    return 0
}

# ==============================================================================
# 状态查询
# ==============================================================================

# 查看服务状态
show_status() {
    echo ""
    echo -e "${CYAN}=== 智能知识系统 - 服务状态 ===${NC}"
    echo ""

    cd "$PROJECT_DIR"

    # 容器状态
    echo -e "${BLUE}--- 容器状态 ---${NC}"
    docker-compose ps 2>/dev/null || echo "无法获取容器状态"

    # 资源使用
    echo -e "\n${BLUE}--- 资源使用 ---${NC}"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" \
        $(docker ps -q --filter "name=zhineng-") 2>/dev/null || echo "无法获取资源使用"

    # 版本信息
    echo -e "\n${BLUE}--- 版本信息 ---${NC}"
    local current_version=$(get_current_version)
    echo "当前版本: ${current_version}"
    if [[ -f "$VERSION_FILE" ]]; then
        local deploy_time=$(grep -oP '"deploy_time":\s*"\K[^"]+' "$VERSION_FILE" 2>/dev/null || echo "unknown")
        echo "部署时间: ${deploy_time}"
        local environment=$(grep -oP '"environment":\s*"\K[^"]+' "$VERSION_FILE" 2>/dev/null || echo "unknown")
        echo "部署环境: ${environment}"
    fi

    # 端口监听
    echo -e "\n${BLUE}--- 端口监听 ---${NC}"
    echo "  PostgreSQL: 5436"
    echo "  Redis:      6381"
    echo "  API:        8001"
    echo "  Nginx:      8008"
    echo "  Prometheus: 9090"
    echo "  Grafana:    3000"

    echo ""
}

# 查看日志
show_logs() {
    local service=${1:-""}

    cd "$PROJECT_DIR"

    if [[ -n "$service" ]]; then
        log_info "查看 $service 服务日志..."
        docker-compose logs -f --tail=100 "$service"
    else
        log_info "查看所有服务日志..."
        docker-compose logs -f --tail=50
    fi
}

# 显示版本
show_version() {
    echo ""
    echo -e "${CYAN}=== 版本信息 ===${NC}"
    echo ""

    local current=$(get_current_version)
    local previous=$(get_previous_version)

    echo "当前版本: ${current}"
    echo "上一个版本: ${previous:-无}"

    if [[ -f "$VERSION_FILE" ]]; then
        echo ""
        cat "$VERSION_FILE" | jq . 2>/dev/null || cat "$VERSION_FILE"
    fi

    echo ""
}

# ==============================================================================
# 回滚函数
# ==============================================================================

# 执行回滚
rollback() {
    local target_version=${1:-""}

    log_warn "========================================="
    log_warn "回滚操作"
    log_warn "========================================="

    if [[ -z "$target_version" ]]; then
        target_version=$(get_previous_version)
        if [[ -z "$target_version" ]]; then
            log_error "没有可回滚的版本"
            return 1
        fi
    fi

    log_warn "将回滚到版本: $target_version"
    confirm "确认回滚?" n || return 0

    # 查找版本对应的备份
    local backup_dir=""
    if [[ -d "$DEPLOY_DIR/backups" ]]; then
        backup_dir=$(find "$DEPLOY_DIR/backups" -name "*${target_version}*" | head -1)
    fi

    if [[ -z "$backup_dir" && -f "$DEPLOY_DIR/last_backup.info" ]]; then
        source "$DEPLOY_DIR/last_backup.info"
        backup_dir="$backup_dir"
    fi

    # 执行回滚
    log_step "停止当前服务..."
    stop_services

    # 恢复数据库（如果存在备份）
    if [[ -n "$backup_dir" && -f "${backup_dir}.db.sql.gz" ]]; then
        log_step "恢复数据库..."
        # 启动数据库
        docker-compose up -d postgres
        sleep 5

        # 恢复数据
        gunzip -c "${backup_dir}.db.sql.gz" | \
            docker-compose exec -T postgres psql -U zhineng zhineng_kb 2>/dev/null || {
            log_warn "数据库恢复失败"
        }
    fi

    # 恢复配置（如果存在）
    if [[ -n "$backup_dir" && -f "${backup_dir}/docker-compose.yml" ]]; then
        log_step "恢复配置..."
        cp -f "${backup_dir}/docker-compose.yml" "$PROJECT_DIR/"
        cp -f "${backup_dir}/.env" "$PROJECT_DIR/" 2>/dev/null || true
    fi

    # 启动服务
    log_step "启动服务..."
    start_services

    # 健康检查
    sleep 5
    if health_check; then
        log_success "回滚完成"
    else
        log_error "回滚后健康检查失败"
        return 1
    fi
}

# ==============================================================================
# 更新函数
# ==============================================================================

# 更新代码并部署
update_and_deploy() {
    log_step "更新代码..."

    cd "$PROJECT_DIR"

    # 检查是否是 git 仓库
    if [[ ! -d ".git" ]]; then
        log_error "不是 git 仓库，无法更新"
        return 1
    fi

    # 拉取最新代码
    local current_branch=$(git branch --show-current)
    log_info "当前分支: $current_branch"
    log_info "拉取最新代码..."

    if git pull origin "$current_branch" 2>&1 | tee -a "$LOG_FILE"; then
        log_info "代码更新成功"
    else
        log_error "代码更新失败"
        return 1
    fi

    # 安装依赖
    if [[ -f "backend/requirements.txt" ]]; then
        log_info "更新 Python 依赖..."
        pip install -r backend/requirements.txt -q 2>/dev/null || true
    fi

    # 执行部署
    deploy
}

# ==============================================================================
# 部署主流程
# ==============================================================================

deploy() {
    log_info "========================================="
    log_info "开始部署"
    log_info "环境: $DEPLOY_ENV"
    log_info "========================================="

    local start_time=$(date +%s)

    # 检查前置条件
    if ! check_prerequisites; then
        log_error "前置条件检查失败"
        return 1
    fi

    # 检查端口
    check_ports

    # 创建备份
    create_deployment_backup

    # 构建镜像
    if ! build_images; then
        log_error "镜像构建失败"
        return 1
    fi

    # 启动服务
    if ! start_services; then
        log_error "服务启动失败"
        return 1
    fi

    # 等待服务就绪
    log_step "等待服务就绪..."
    sleep 10

    # 健康检查
    if ! health_check; then
        log_error "健康检查失败"
        if confirm "健康检查失败，是否回滚?" y; then
            rollback
        fi
        return 1
    fi

    # 保存版本信息
    local new_version=$(generate_version)
    save_version "$new_version"

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_success "========================================="
    log_success "部署成功!"
    log_success "版本: $new_version"
    log_success "耗时: ${duration} 秒"
    log_success "========================================="

    return 0
}

# ==============================================================================
# 显示帮助
# ==============================================================================

show_help() {
    cat << EOF
智能知识系统 - 一键部署脚本

用法: $0 [命令] [参数]

命令:
    deploy [env]          部署应用 (环境: dev/staging/prod)
    rollback [version]    回滚到指定版本
    status                查看服务状态
    health                执行健康检查
    logs [service]        查看服务日志
    stop                  停止所有服务
    restart               重启所有服务
    update                更新代码并部署
    backup                创建部署前备份
    version               查看当前版本
    help                  显示此帮助信息

参数:
    env       部署环境 (默认: dev)
    version   目标版本号
    service   服务名称 (api/postgres/redis/nginx等)

环境变量:
    DEPLOY_ENV             部署环境 (默认: dev)
    AUTO_BACKUP            部署前自动备份 (默认: true)
    HEALTH_CHECK_TIMEOUT   健康检查超时时间 (默认: 300秒)
    FORCE_CONFIRM          强制确认，跳过提示 (默认: false)
    DEBUG                  启用调试输出 (默认: false)

示例:
    $0 deploy              # 部署到开发环境
    $0 deploy prod         # 部署到生产环境
    $0 status              # 查看服务状态
    $0 health              # 执行健康检查
    $0 logs api            # 查看 API 日志
    $0 rollback            # 回滚到上一个版本
    $0 update              # 更新代码并部署

EOF
}

# ==============================================================================
# 主函数
# ==============================================================================

main() {
    init_logging

    local command=${1:-""}
    local param=${2:-""}

    case "$command" in
        deploy)
            if [[ -n "$param" ]]; then
                DEPLOY_ENV="$param"
            fi
            deploy
            ;;
        rollback)
            rollback "$param"
            ;;
        status)
            show_status
            ;;
        health)
            health_check
            ;;
        logs)
            show_logs "$param"
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        update)
            update_and_deploy
            ;;
        backup)
            create_deployment_backup
            ;;
        version|--version|-v)
            show_version
            ;;
        help|--help|-h)
            show_help
            ;;
        "")
            log_error "请指定命令"
            echo ""
            show_help
            exit 1
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
