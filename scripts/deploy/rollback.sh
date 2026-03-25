#!/bin/bash
# ==============================================================================
# 智能知识系统 - 部署回滚脚本
# ==============================================================================
# 功能：
#   - 版本回滚管理
#   - Docker容器回滚
#   - 数据库回滚
#   - 配置文件回滚
#   - 快速恢复模式
#
# 用法:
#   ./rollback.sh list                    # 列出可用版本
#   ./rollback.sh rollback <version>      # 回滚到指定版本
#   ./rollback.sh quick                   # 快速回滚（使用最近备份）
#   ./rollback.sh db-only <backup>        # 仅回滚数据库
#   ./rollback.sh config-only <version>   # 仅回滚配置
#   ./rollback.sh verify                  # 验证当前状态
#   ./rollback.sh pre-rollback            # 部署前创建快照
# ==============================================================================

set -euo pipefail

# ==============================================================================
# 配置部分
# ==============================================================================

# 颜色输出
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

# 目录配置
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly PROJECT_DIR="$(cd "$SCRIPT_DIR" && pwd)"
readonly VERSION_DIR="${VERSION_DIR:-$PROJECT_DIR/versions}"
readonly BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
readonly LOG_DIR="${LOG_DIR:-$PROJECT_DIR/logs}"

# Docker配置
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
DB_CONTAINER="${DB_CONTAINER:-zhineng-postgres}"
DB_NAME="${DB_NAME:-zhineng_kb}"
DB_USER="${DB_USER:-zhineng}"

# 日志文件
LOG_FILE="${LOG_FILE:-$LOG_DIR/rollback_$(date +%Y%m%d_%H%M%S).log}"
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
    echo "$(date -Iseconds)|$version" >> "$VERSION_HISTORY_FILE"
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
# 版本创建（部署前快照）
# ==============================================================================

# 创建版本快照
create_version_snapshot() {
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
        log_info "已备份 docker-compose.yml"
    fi

    # 备份.env文件
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        cp "$PROJECT_DIR/.env" "$version_dir/"
        log_info "已备份 .env"
    fi

    # 备份nginx配置
    if [[ -f "$PROJECT_DIR/nginx/nginx.conf" ]]; then
        mkdir -p "$version_dir/nginx"
        cp "$PROJECT_DIR/nginx/nginx.conf" "$version_dir/nginx/"
        log_info "已备份 nginx配置"
    fi

    # 备份后端配置
    if [[ -f "$PROJECT_DIR/backend/config.py" ]]; then
        mkdir -p "$version_dir/backend"
        cp "$PROJECT_DIR/backend/config.py" "$version_dir/backend/"
        log_info "已备份后端配置"
    fi

    # 创建版本信息文件
    cat > "$version_dir/.info" << EOF
version=$version
created_at=$(date -Iseconds)
git_branch=$(git -C "$PROJECT_DIR" branch --show-current 2>/dev/null || echo "unknown")
git_commit=$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
git_commit_full=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || echo "unknown")
docker_images=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "(zhineng|postgres|redis)" | tr '\n' ',' | sed 's/,$//')
EOF

    log_info "版本快照创建完成: $version"
    echo "$version"
}

# ==============================================================================
# Docker容器回滚
# ==============================================================================

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

    # 恢复后端配置
    if [[ -f "$version_dir/backend/config.py" ]]; then
        cp "$version_dir/backend/config.py" "$PROJECT_DIR/backend/config.py"
        log_info "已恢复后端配置"
    fi

    # 重启服务
    restart_services

    log_info "容器配置回滚完成"
}

# 快速容器恢复
quick_container_rollback() {
    log_step "快速容器恢复..."

    cd "$PROJECT_DIR"
    docker-compose restart 2>&1 | tee -a "$LOG_FILE"
    sleep 10
    verify_services

    log_info "快速容器恢复完成"
}

# ==============================================================================
# 数据库回滚
# ==============================================================================

# 数据库回滚
rollback_database() {
    local backup_file=$1

    if [[ -z "$backup_file" ]]; then
        # 列出可用的数据库备份
        log_info "可用的数据库备份:"
        find "$BACKUP_DIR" -name "db_full_*.sql.gz" -o -name "db_*.sql.gz" 2>/dev/null | \
            sort -r | head -10 | while read -r file; do
            local size=$(ls -lh "$file" | awk '{print $5}')
            local date=$(stat -c %y "$file" | cut -d'.' -f1)
            echo "  $(basename "$file") (${size}) - $date"
        done

        echo ""
        read -p "请输入要回滚的备份文件名或日期 (YYYYMMDD): " backup_input

        if [[ -n "$backup_input" ]]; then
            # 查找匹配的备份
            local found_backup=$(find "$BACKUP_DIR" -name "*${backup_input}*.sql.gz" 2>/dev/null | sort -r | head -1)
            if [[ -n "$found_backup" ]]; then
                restore_database "$found_backup"
            else
                log_error "未找到匹配的备份"
                return 1
            fi
        fi
    else
        # 使用指定的备份文件
        if [[ -f "$backup_file" ]]; then
            restore_database "$backup_file"
        else
            log_error "备份文件不存在: $backup_file"
            return 1
        fi
    fi
}

# 恢复数据库
restore_database() {
    local backup_file=$1

    log_info "恢复数据库: $(basename "$backup_file")"

    echo "确认恢复数据库? 这将覆盖当前数据! [y/N]: "
    read -r confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "取消操作"
        return 0
    fi

    cd "$PROJECT_DIR"

    # 停止API服务
    docker-compose stop api nginx 2>/dev/null || true

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
    log_step "启动服务..."
    docker-compose start api nginx 2>/dev/null || true
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
        fi
    done

    # 健康检查
    health_check
}

# 健康检查
health_check() {
    local api_url="http://localhost:8001/health"
    local frontend_url="http://localhost:8008"

    # 检查API
    if command -v curl &> /dev/null; then
        if curl -f -s --max-time 5 "$api_url" > /dev/null 2>&1; then
            log_info "✓ API健康检查通过"
        else
            log_warn "✗ API健康检查失败"
        fi
    fi

    # 检查前端
    if command -v curl &> /dev/null; then
        if curl -f -s --max-time 5 "$frontend_url" > /dev/null 2>&1; then
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
    echo "=== 可用版本列表 ==="
    echo ""

    local current=$(get_current_version)
    local versions=$(get_version_list)

    if [[ -z "$versions" ]]; then
        echo "无可用版本"
        echo ""
        echo "提示: 使用 '$0 pre-rollback' 创建版本快照"
        return
    fi

    echo "$versions" | while read -r version; do
        local marker=""
        if [[ "$version" == "$current" ]]; then
            marker="* 当前版本"
        fi

        local info=$(get_version_info "$version" | grep -E "created_at|git_commit" | head -2)

        echo "$version $marker"
        echo "$info" | sed 's/^/  /'
        echo ""
    done

    # 显示备份信息
    echo "--- 数据库备份 ---"
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
    echo "=== 系统状态 ==="
    echo ""

    # 当前版本
    local current=$(get_current_version)
    echo "当前版本: ${current}"

    # 容器状态
    echo ""
    echo "--- 容器状态 ---"
    cd "$PROJECT_DIR"
    docker-compose ps 2>/dev/null || echo "无法获取容器状态"

    # 最近备份
    echo ""
    echo "--- 最近备份 ---"
    find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime -1 2>/dev/null | while read -r file; do
        local size=$(ls -lh "$file" | awk '{print $5}')
        local date=$(stat -c %y "$file" | cut -d'.' -f1)
        printf "  %-40s %10s  %s\n" "$(basename "$file")" "$size" "$date"
    done

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
    echo "确认回滚到此版本? [y/N]: "
    read -r confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "取消回滚"
        return 0
    fi

    # 创建当前版本快照（用于回滚的回滚）
    log_step "创建当前版本快照..."
    local current_snapshot=$(create_version_snapshot "before_rollback_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || echo "")
    if [[ -n "$current_snapshot" ]]; then
        log_info "已保存当前状态到: $current_snapshot"
    fi

    # 回滚容器
    log_step "回滚容器配置..."
    rollback_containers "$version"

    # 回滚数据库（如果存在备份）
    if [[ -f "$version_dir/database.sql.gz" ]]; then
        echo "是否回滚数据库? [Y/n]: "
        read -r db_confirm
        if [[ "$db_confirm" =~ ^[Yy]$ ]] || [[ -z "$db_confirm" ]]; then
            log_step "回滚数据库..."
            restore_database "$version_dir/database.sql.gz"
        fi
    elif [[ -f "$version_dir/db_full_"*".sql.gz" ]]; then
        echo "是否回滚数据库? [Y/n]: "
        read -r db_confirm
        if [[ "$db_confirm" =~ ^[Yy]$ ]] || [[ -z "$db_confirm" ]]; then
            local db_backup=$(ls "$version_dir"/db_full_*.sql.gz 2>/dev/null | head -1)
            [[ -n "$db_backup" ]] && restore_database "$db_backup"
        fi
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

# 快速回滚
quick_rollback() {
    log_info "========================================="
    log_info "快速回滚模式"
    log_info "========================================="

    # 查找最近备份
    local latest_backup=$(find "$BACKUP_DIR" -name "db_full_*.sql.gz" -o -name "db_*.sql.gz" 2>/dev/null | sort -r | head -1)

    if [[ -z "$latest_backup" ]]; then
        log_error "未找到备份文件"
        return 1
    fi

    echo ""
    echo "找到最近备份: $(basename "$latest_backup")"

    echo "确认使用此备份恢复? [y/N]: "
    read -r confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "取消操作"
        return 0
    fi

    # 恢复数据库
    restore_database "$latest_backup"

    # 重启容器
    quick_container_rollback

    log_info "快速回滚完成"
}

# ==============================================================================
# 帮助
# ==============================================================================

show_help() {
    cat << EOF
智能知识系统 - 部署回滚脚本

用法: $0 [命令] [参数]

命令:
    list                    列出可用版本和备份
    status                  显示当前系统状态
    pre-rollback            部署前创建版本快照
    rollback <version>      回滚到指定版本
    quick                   快速回滚（使用最近备份）
    db-only <backup>        仅回滚数据库
    config-only <version>   仅回滚配置文件
    verify                  验证当前版本
    help                    显示此帮助信息

示例:
    $0 list                    # 列出可用版本
    $0 pre-rollback            # 创建当前版本快照
    $0 rollback v_20240325     # 回滚到指定版本
    $0 quick                   # 快速回滚

注意事项:
    1. 回滚操作会覆盖当前数据和配置
    2. 回滚前会自动创建当前版本快照
    3. 建议在部署前执行 pre-rollback 创建快照

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
        pre-rollback|snapshot)
            create_version_snapshot "${2:-}"
            ;;
        rollback)
            if [[ -z "${2:-}" ]]; then
                log_error "请指定版本号"
                list_versions
                exit 1
            fi
            rollback_to_version "$2"
            ;;
        quick|qr)
            quick_rollback
            ;;
        db-only)
            rollback_database "${2:-}"
            ;;
        config-only)
            if [[ -z "${2:-}" ]]; then
                log_error "请指定版本号"
                list_versions
                exit 1
            fi
            rollback_containers "$2"
            ;;
        quick-container|qc)
            quick_container_rollback
            ;;
        verify|check)
            verify_current_version
            ;;
        help|--help|-h|"")
            show_help
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
