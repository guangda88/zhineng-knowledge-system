#!/bin/bash
# ==============================================================================
# 智能知识系统 - 部署回滚脚本
# ==============================================================================
# 功能：
#   - Docker容器回滚
#   - 数据库迁移回滚
#   - 快速恢复命令
#   - 版本管理
#   - 回滚前后验证
#
# 用法:
#   ./rollback.sh list                    # 列出可用版本
#   ./rollback.sh rollback <version>      # 回滚到指定版本
#   ./rollback.sh rollback-last           # 回滚到上一版本
#   ./rollback.sh db-rollback <version>   # 仅回滚数据库
#   ./rollback.sh container-rollback      # 仅回滚容器
#   ./rollback.sh verify                  # 验证当前版本
#   ./rollback.sh status                  # 显示当前状态
#
# 环境变量:
#   VERSION_DIR         - 版本存储目录
#   BACKUP_DIR          - 备份目录
#   FORCE_ROLLBACK      - 强制回滚（跳过确认）
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
readonly NC='\033[0m'

# 目录配置
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly VERSION_DIR="${VERSION_DIR:-$PROJECT_DIR/versions}"
readonly BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
readonly LOG_DIR="${LOG_DIR:-$PROJECT_DIR/logs}"

# Docker配置
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
DB_CONTAINER="${DB_CONTAINER:-zhineng-postgres}"
DB_NAME="${DB_NAME:-zhineng_kb}"
DB_USER="${DB_USER:-zhineng}"

# 回滚配置
FORCE_ROLLBACK=${FORCE_ROLLBACK:-false}
MAX_VERSIONS=${MAX_VERSIONS:-5}

# 日志文件
LOG_FILE="${LOG_FILE:-$LOG_DIR/rollback_$(date +%Y%m%d_%H%M%S).log}"

# 当前版本文件
CURRENT_VERSION_FILE="$VERSION_DIR/.current"
VERSION_HISTORY_FILE="$VERSION_DIR/.history"

# ==============================================================================
# 日志函数
# ==============================================================================

# 初始化
init() {
    mkdir -p "$LOG_DIR" "$VERSION_DIR" "$BACKUP_DIR"
    touch "$LOG_FILE"
}

# 日志输出
log() {
    local level=$1
    shift
    local msg="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "[${timestamp}] [${level}] ${msg}" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $*" | tee -a "$LOG_FILE"
}

log_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $*" | tee -a "$LOG_FILE"
    fi
}

# ==============================================================================
# 错误处理
# ==============================================================================

error_handler() {
    local line_number=$1
    local error_code=$2
    log_error "脚本在第 ${line_number} 行退出，错误码: ${error_code}"
    log_error "回滚过程中发生错误，请检查日志: $LOG_FILE"
    exit "$error_code"
}

trap 'error_handler ${LINENO} $?' ERR

# ==============================================================================
# 确认函数
# ==============================================================================

confirm() {
    local prompt=$1
    local default=${2:-n}

    if [[ "$FORCE_ROLLBACK" == "true" ]]; then
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

    if [[ "$response" =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

# ==============================================================================
# 版本管理
# ==============================================================================

# 获取当前版本
get_current_version() {
    if [[ -f "$CURRENT_VERSION_FILE" ]]; then
        cat "$CURRENT_VERSION_FILE"
    else
        echo "unknown"
    fi
}

# 设置当前版本
set_current_version() {
    local version=$1
    echo "$version" > "$CURRENT_VERSION_FILE"
    log_info "当前版本已设置为: $version"
    record_history "$version"
}

# 记录版本历史
record_history() {
    local version=$1
    local timestamp=$(date -Iseconds)
    echo "$timestamp|$version" >> "$VERSION_HISTORY_FILE"
}

# 获取版本列表
get_version_list() {
    if [[ ! -d "$VERSION_DIR" ]]; then
        return
    fi

    find "$VERSION_DIR" -maxdepth 1 -type d -name "v_*" | sort -r | while read -r dir; do
        basename "$dir"
    done
}

# 获取版本信息
get_version_info() {
    local version=$1
    local version_dir="$VERSION_DIR/$version"

    if [[ ! -d "$version_dir" ]]; then
        return
    fi

    local info_file="$version_dir/.info"
    if [[ -f "$info_file" ]]; then
        cat "$info_file"
    else
        echo "版本: $version"
        echo "创建时间: $(stat -c %y "$version_dir" | cut -d'.' -f1)"
    fi
}

# ==============================================================================
# 版本创建
# ==============================================================================

# 创建版本快照
create_version() {
    local version=${1:-"v_$(date +%Y%m%d_%H%M%S)"}
    local version_dir="$VERSION_DIR/$version"

    log_step "创建版本快照: $version"

    if [[ -d "$version_dir" ]]; then
        log_warn "版本目录已存在: $version"
        return 1
    fi

    mkdir -p "$version_dir"

    # 备份docker-compose配置
    if [[ -f "$COMPOSE_FILE" ]]; then
        cp "$COMPOSE_FILE" "$version_dir/"
        log_debug "已备份 docker-compose.yml"
    fi

    # 备份.env文件
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        cp "$PROJECT_DIR/.env" "$version_dir/"
        log_debug "已备份 .env"
    fi

    # 备份nginx配置
    if [[ -f "$PROJECT_DIR/nginx/nginx.conf" ]]; then
        mkdir -p "$version_dir/nginx"
        cp "$PROJECT_DIR/nginx/nginx.conf" "$version_dir/nginx/"
        log_debug "已备份 nginx配置"
    fi

    # 创建版本信息文件
    cat > "$version_dir/.info" << EOF
version=$version
created_at=$(date -Iseconds)
git_branch=$(git -C "$PROJECT_DIR" branch --show-current 2>/dev/null || echo "unknown")
git_commit=$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
docker_images=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "(zhineng|postgres|redis)" | tr '\n' ',')
EOF

    log_info "版本快照创建完成: $version"
    echo "$version"
}

# ==============================================================================
# Docker容器回滚
# ==============================================================================

# 获取容器镜像版本
get_container_image() {
    local container=$1
    docker inspect "$container" --format='{{.Config.Image}}' 2>/dev/null || echo ""
}

# 停止服务
stop_services() {
    log_step "停止服务..."
    cd "$PROJECT_DIR"

    # 优雅关闭
    docker-compose stop --timeout 30 2>&1 | tee -a "$LOG_FILE"
}

# 启动服务
start_services() {
    log_step "启动服务..."
    cd "$PROJECT_DIR"

    docker-compose start 2>&1 | tee -a "$LOG_FILE"
}

# 重启服务
restart_services() {
    log_step "重启服务..."
    cd "$PROJECT_DIR"

    docker-compose restart 2>&1 | tee -a "$LOG_FILE"
}

# 容器回滚
rollback_containers() {
    local version=$1
    local version_dir="$VERSION_DIR/$version"

    log_step "回滚容器配置..."

    if [[ ! -d "$version_dir" ]]; then
        log_error "版本目录不存在: $version"
        return 1
    fi

    # 恢复docker-compose配置
    if [[ -f "$version_dir/docker-compose.yml" ]]; then
        cp "$version_dir/docker-compose.yml" "$COMPOSE_FILE"
        log_info "已恢复 docker-compose.yml"
    fi

    # 恢复.env配置
    if [[ -f "$version_dir/.env" ]]; then
        cp "$version_dir/.env" "$PROJECT_DIR/.env"
        log_info "已恢复 .env"
    fi

    # 恢复nginx配置
    if [[ -f "$version_dir/nginx/nginx.conf" ]]; then
        cp "$version_dir/nginx/nginx.conf" "$PROJECT_DIR/nginx/nginx.conf"
        log_info "已恢复 nginx配置"
    fi

    # 重启服务
    restart_services

    log_info "容器配置回滚完成"
}

# 快速容器恢复
quick_container_rollback() {
    log_step "快速容器恢复..."

    cd "$PROJECT_DIR"

    # 重启所有容器
    docker-compose restart 2>&1 | tee -a "$LOG_FILE"

    # 等待服务就绪
    sleep 10

    # 验证服务状态
    verify_services

    log_info "快速容器恢复完成"
}

# ==============================================================================
# 数据库回滚
# ==============================================================================

# 数据库回滚
rollback_database() {
    local version=${1:-""}

    log_step "回滚数据库..."

    if [[ -z "$version" ]]; then
        # 列出可用的数据库备份
        log_info "可用的数据库备份:"
        find "$BACKUP_DIR" -name "db_full_*.sql.gz" -o -name "db_*.sql.gz" | \
            sort -r | head -10 | while read -r file; do
            local size=$(ls -lh "$file" | awk '{print $5}')
            local date=$(stat -c %y "$file" | cut -d'.' -f1)
            echo "  $(basename "$file") (${size}) - $date"
        done

        echo ""
        read -p "请输入要回滚的备份文件名或日期 (YYYYMMDD): " backup_input

        if [[ -n "$backup_input" ]]; then
            # 查找匹配的备份
            local backup_file=$(find "$BACKUP_DIR" -name "*${backup_input}*.sql.gz" | sort -r | head -1)
            if [[ -n "$backup_file" ]]; then
                restore_database "$backup_file"
            else
                log_error "未找到匹配的备份"
                return 1
            fi
        fi
    else
        # 使用指定版本的数据库备份
        local backup_file="$VERSION_DIR/$version/database.sql.gz"
        if [[ -f "$backup_file" ]]; then
            restore_database "$backup_file"
        else
            log_error "未找到版本 $version 的数据库备份"
            return 1
        fi
    fi
}

# 恢复数据库
restore_database() {
    local backup_file=$1

    log_info "恢复数据库: $(basename "$backup_file")"

    # 确认操作
    if ! confirm "确认恢复数据库? 这将覆盖当前数据!" n; then
        log_info "取消操作"
        return 0
    fi

    cd "$PROJECT_DIR"

    # 停止API服务
    docker-compose stop api 2>/dev/null || true

    # 清空现有数据库
    log_step "清空现有数据库..."
    docker-compose exec -T postgres psql -U "$DB_USER" "$DB_NAME" \
        -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" \
        --quiet 2>/dev/null || {
        log_warn "清空数据库失败，继续恢复..."
    }

    # 恢复数据
    log_step "恢复数据..."
    local start_time=$(date +%s)

    if [[ "$backup_file" == *.gz ]]; then
        if ! gunzip -c "$backup_file" | docker-compose exec -T postgres psql -U "$DB_USER" "$DB_NAME" --quiet 2>&1 | tee -a "$LOG_FILE"; then
            log_error "数据库恢复失败"
            return 1
        fi
    else
        if ! docker-compose exec -T postgres psql -U "$DB_USER" "$DB_NAME" < "$backup_file" 2>&1 | tee -a "$LOG_FILE"; then
            log_error "数据库恢复失败"
            return 1
        fi
    fi

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # 重启服务
    log_step "启动API服务..."
    docker-compose start api 2>/dev/null || true
    sleep 3

    # 验证恢复
    log_step "验证数据库..."
    local table_count=$(docker-compose exec -T postgres psql -U "$DB_USER" "$DB_NAME" -t -c "
        SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';
    " 2>/dev/null | tr -d ' ' || echo "0")

    log_info "数据库恢复完成!"
    log_info "  恢复时间: ${duration} 秒"
    log_info "  数据表数量: ${table_count}"
}

# ==============================================================================
# 验证函数
# ==============================================================================

# 验证服务状态
verify_services() {
    log_step "验证服务状态..."

    local failed=0

    # 检查容器状态
    cd "$PROJECT_DIR"
    local containers=$(docker-compose ps -q)

    if [[ -z "$containers" ]]; then
        log_error "没有运行的容器"
        return 1
    fi

    # 检查每个容器
    echo "$containers" | while read -r container_id; do
        local name=$(docker inspect "$container_id" --format='{{.Name}}' | sed 's/\///')
        local status=$(docker inspect "$container_id" --format='{{.State.Status}}')

        if [[ "$status" == "running" ]]; then
            log_info "✓ $name: 运行中"
        else
            log_error "✗ $name: $status"
            ((failed++))
        fi
    done

    # 健康检查
    log_step "执行健康检查..."
    health_check

    return $failed
}

# 健康检查
health_check() {
    local api_url="http://localhost:8001/health"
    local frontend_url="http://localhost:8008"

    # 检查API
    if command -v curl &> /dev/null; then
        if curl -f -s "$api_url" > /dev/null 2>&1; then
            log_info "✓ API健康检查通过"
        else
            log_warn "✗ API健康检查失败"
        fi
    fi

    # 检查前端
    if command -v curl &> /dev/null; then
        if curl -f -s "$frontend_url" > /dev/null 2>&1; then
            log_info "✓ 前端健康检查通过"
        else
            log_warn "✗ 前端健康检查失败"
        fi
    fi

    # 检查数据库连接
    if docker-compose exec -T postgres pg_isready -U "$DB_USER" "$DB_NAME" > /dev/null 2>&1; then
        log_info "✓ 数据库连接正常"
    else
        log_warn "✗ 数据库连接失败"
    fi

    # 检查Redis连接
    if docker-compose exec -T redis redis-cli -a redis123 ping > /dev/null 2>&1; then
        log_info "✓ Redis连接正常"
    else
        log_warn "✗ Redis连接失败"
    fi
}

# 验证当前版本
verify_current_version() {
    log_step "验证当前版本..."

    local current_version=$(get_current_version)
    log_info "当前版本: $current_version"

    if [[ "$current_version" != "unknown" ]]; then
        get_version_info "$current_version"
    fi

    echo ""
    verify_services
}

# ==============================================================================
# 列出和状态
# ==============================================================================

# 列出可用版本
list_versions() {
    echo ""
    echo -e "${CYAN}=== 可用版本列表 ===${NC}"
    echo ""

    local current=$(get_current_version)
    local versions=$(get_version_list)

    if [[ -z "$versions" ]]; then
        echo "无可用版本"
        echo ""
        echo "提示: 使用 '$0 create' 创建版本快照"
        return
    fi

    echo "$versions" | while read -r version; do
        local marker=""
        if [[ "$version" == "$current" ]]; then
            marker="${GREEN}*${NC} 当前版本"
        fi

        local info=$(get_version_info "$version" | grep -E "created_at|git_commit" | head -2)

        echo -e "${CYAN}$version${NC} $marker"
        echo "$info" | sed 's/^/  /'
        echo ""
    done

    # 显示备份信息
    echo -e "${BLUE}--- 数据库备份 ---${NC}"
    find "$BACKUP_DIR" -name "db_*.sql.gz" 2>/dev/null | sort -r | head -5 | while read -r file; do
        local size=$(ls -lh "$file" | awk '{print $5}')
        local date=$(stat -c %y "$file" | cut -d'.' -f1)
        printf "  %-40s %10s  %s\n" "$(basename "$file")" "$size" "$date"
    done
    echo ""
}

# 显示状态
show_status() {
    echo ""
    echo -e "${CYAN}=== 系统状态 ===${NC}"
    echo ""

    # 当前版本
    local current=$(get_current_version)
    echo "当前版本: ${current}"

    # 容器状态
    echo ""
    echo -e "${BLUE}--- 容器状态 ---${NC}"
    cd "$PROJECT_DIR"
    docker-compose ps 2>/dev/null || echo "无法获取容器状态"

    # 最近备份
    echo ""
    echo -e "${BLUE}--- 最近备份 ---${NC}"
    find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime -1 2>/dev/null | while read -r file; do
        local size=$(ls -lh "$file" | awk '{print $5}')
        local date=$(stat -c %y "$file" | cut -d'.' -f1)
        printf "  %-40s %10s  %s\n" "$(basename "$file")" "$size" "$date"
    done

    # 磁盘使用
    echo ""
    echo -e "${BLUE}--- 磁盘使用 ---${NC}"
    df -h "$PROJECT_DIR" | tail -1 | awk '{printf "  项目目录: %s / %s (%s 使用)\n", $3, $2, $5}'
    df -h "$BACKUP_DIR" | tail -1 | awk '{printf "  备份目录: %s / %s (%s 使用)\n", $3, $2, $5}'

    echo ""
}

# ==============================================================================
# 完整回滚
# ==============================================================================

# 完整回滚到指定版本
rollback_to_version() {
    local version=$1

    log_info "========================================="
    log_info "开始回滚到版本: $version"
    log_info "========================================="

    local version_dir="$VERSION_DIR/$version"

    if [[ ! -d "$version_dir" ]]; then
        log_error "版本不存在: $version"
        return 1
    fi

    # 显示版本信息
    echo ""
    get_version_info "$version"
    echo ""

    # 确认回滚
    if ! confirm "确认回滚到此版本? " n; then
        log_info "取消回滚"
        return 0
    fi

    # 创建当前版本快照（用于回滚的回滚）
    log_step "创建当前版本快照..."
    local current_snapshot=$(create_version "before_rollback_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || echo "")
    if [[ -n "$current_snapshot" ]]; then
        log_info "已保存当前状态到: $current_snapshot"
    fi

    # 回滚容器
    log_step "回滚容器配置..."
    rollback_containers "$version"

    # 回滚数据库
    if [[ -f "$version_dir/database.sql.gz" ]]; then
        log_step "回滚数据库..."
        restore_database "$version_dir/database.sql.gz"
    elif confirm "是否回滚数据库?" y; then
        rollback_database ""
    fi

    # 验证回滚
    log_step "验证回滚结果..."
    verify_services

    # 更新当前版本
    set_current_version "$version"

    log_info "========================================="
    log_info "回滚完成!"
    log_info "========================================="
}

# 回滚到上一版本
rollback_to_previous() {
    local current=$(get_current_version)
    local versions=$(get_version_list)

    # 获取上一版本
    local previous=$(echo "$versions" | grep -v "^${current}$" | head -1)

    if [[ -z "$previous" ]]; then
        log_error "没有可回滚的版本"
        return 1
    fi

    rollback_to_version "$previous"
}

# ==============================================================================
# 快速恢复
# ==============================================================================

# 快速恢复（使用最近备份）
quick_restore() {
    log_info "========================================="
    log_info "快速恢复模式"
    log_info "========================================="

    # 查找最近备份
    local latest_backup=$(find "$BACKUP_DIR" -name "db_full_*.sql.gz" -o -name "db_*.sql.gz" | sort -r | head -1)

    if [[ -z "$latest_backup" ]]; then
        log_error "未找到备份文件"
        return 1
    fi

    echo ""
    echo "找到最近备份: $(basename "$latest_backup")"

    if ! confirm "确认使用此备份恢复?" n; then
        log_info "取消操作"
        return 0
    fi

    # 恢复数据库
    restore_database "$latest_backup"

    # 重启容器
    quick_container_rollback

    log_info "快速恢复完成"
}

# ==============================================================================
# 帮助
# ==============================================================================

show_help() {
    cat << EOF
智能知识系统 - 部署回滚脚本

用法: $0 [命令] [参数]

命令:
    list                         列出可用版本和备份
    status                       显示当前系统状态
    create [version]             创建版本快照
    rollback <version>           回滚到指定版本
    rollback-last                回滚到上一版本
    container-rollback [version] 仅回滚容器配置
    db-rollback [version|file]   仅回滚数据库
    quick-restore                快速恢复（使用最近备份）
    quick-container              快速容器恢复
    verify                       验证当前版本
    health-check                 执行健康检查

参数:
    version      版本号 (如: v_20240325_120000)
    file         备份文件路径

环境变量:
    VERSION_DIR         版本存储目录 (默认: ./versions)
    BACKUP_DIR          备份目录 (默认: ./backups)
    FORCE_ROLLBACK      强制回滚，跳过确认 (默认: false)
    DEBUG               启用调试输出 (默认: false)

示例:
    $0 list                                  # 列出可用版本
    $0 create                                # 创建当前版本快照
    $0 rollback v_20240325_120000            # 回滚到指定版本
    $0 rollback-last                         # 回滚到上一版本
    $0 db-rollback 20240325                  # 回滚数据库到指定日期
    $0 quick-restore                         # 快速恢复

注意事项:
    1. 回滚操作会覆盖当前数据和配置
    2. 回滚前会自动创建当前版本快照
    3. 建议在回滚前先执行备份操作

EOF
}

# ==============================================================================
# 主函数
# ==============================================================================

main() {
    init

    local command=${1:-""}

    case "$command" in
        list|ls)
            list_versions
            ;;
        status|st)
            show_status
            ;;
        create|snapshot)
            create_version "$2"
            ;;
        rollback)
            if [[ -z "${2:-}" ]]; then
                log_error "请指定版本号"
                list_versions
                exit 1
            fi
            rollback_to_version "$2"
            ;;
        rollback-last|prev)
            rollback_to_previous
            ;;
        container-rollback)
            if [[ -z "${2:-}" ]]; then
                log_error "请指定版本号"
                list_versions
                exit 1
            fi
            rollback_containers "$2"
            ;;
        db-rollback)
            rollback_database "${2:-}"
            ;;
        quick-restore|qr)
            quick_restore
            ;;
        quick-container|qc)
            quick_container_rollback
            ;;
        verify|check)
            verify_current_version
            ;;
        health-check|hc)
            health_check
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
