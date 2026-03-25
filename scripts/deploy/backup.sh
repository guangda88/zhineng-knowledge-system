#!/bin/bash
# ==============================================================================
# 智能知识系统 - 部署备份脚本
# ==============================================================================
# 功能：
#   - 全量备份和增量备份
#   - 备份完整性验证
#   - 定时备份支持（cron集成）
#   - 日志记录
#   - 错误处理
#
# 用法:
#   ./backup.sh                    # 执行全量备份
#   ./backup.sh quick              # 快速备份（仅数据库）
#   ./backup.sh db                 # 仅备份数据库
#   ./backup.sh config             # 仅备份配置
#   ./backup.sh verify <file>      # 验证备份文件
#   ./backup.sh list               # 列出所有备份
#   ./backup.sh install-cron       # 安装定时备份任务
#   ./backup.sh remove-cron        # 移除定时备份任务
#
# 环境变量:
#   BACKUP_DIR          - 备份存储目录 (默认: ./backups)
#   RETENTION_DAYS      - 备份保留天数 (默认: 7)
# ==============================================================================

set -euo pipefail

# ==============================================================================
# 配置部分
# ==============================================================================

# 颜色输出
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly NC='\033[0m'

# 目录配置
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly PROJECT_DIR="$(cd "$SCRIPT_DIR" && pwd)"
readonly BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
readonly LOG_DIR="${LOG_DIR:-$PROJECT_DIR/logs}"

# 备份配置
RETENTION_DAYS=${RETENTION_DAYS:-7}

# 数据库配置
DB_CONTAINER="${DB_CONTAINER:-zhineng-postgres}"
DB_NAME="${DB_NAME:-zhineng_kb}"
DB_USER="${DB_USER:-zhineng}"

# 时间戳
readonly TIMESTAMP=$(date +%Y%m%d_%H%M%S)
readonly DATE_ONLY=$(date +%Y%m%d)

# 日志文件
LOG_FILE="${LOG_FILE:-$LOG_DIR/backup_$(date +%Y%m%d).log}"

# ==============================================================================
# 日志函数
# ==============================================================================

# 初始化日志目录
init_logging() {
    mkdir -p "$LOG_DIR" "$BACKUP_DIR"
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

# ==============================================================================
# Docker 检查
# ==============================================================================

# 检查 Docker 和 Docker Compose
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        return 1
    fi

    if ! docker ps &> /dev/null; then
        log_error "Docker 守护进程未运行"
        return 1
    fi

    return 0
}

# 检查数据库容器是否运行
check_db_container() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
        log_warn "数据库容器 ${DB_CONTAINER} 未运行，尝试启动..."
        cd "$PROJECT_DIR"
        docker-compose start postgres || {
            log_error "无法启动数据库容器"
            return 1
        }
        sleep 5
    fi

    return 0
}

# ==============================================================================
# 备份函数
# ==============================================================================

# 备份数据库（全量）
backup_database() {
    log_info "开始数据库备份..."

    local backup_file="$BACKUP_DIR/db_full_${TIMESTAMP}.sql.gz"
    local temp_file="$BACKUP_DIR/tmp_db_${TIMESTAMP}.sql.gz"

    cd "$PROJECT_DIR"

    # 创建备份
    if ! docker-compose exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" \
        --no-owner --no-acl \
        --verbose 2>&1 | tee -a "$LOG_FILE" | gzip > "$temp_file"; then
        log_error "数据库备份失败"
        rm -f "$temp_file"
        return 1
    fi

    # 验证备份文件
    if ! verify_backup_file "$temp_file"; then
        log_error "备份文件验证失败"
        rm -f "$temp_file"
        return 1
    fi

    # 重命名为正式文件
    mv "$temp_file" "$backup_file"

    log_info "数据库备份完成: $backup_file"
    echo "$backup_file"
}

# 备份配置文件
backup_config() {
    log_info "备份配置文件..."

    local backup_file="$BACKUP_DIR/config_${TIMESTAMP}.tar.gz"
    local temp_file="$BACKUP_DIR/tmp_config_${TIMESTAMP}.tar.gz"

    # 收集配置文件列表
    local config_files=(
        "$PROJECT_DIR/docker-compose.yml"
        "$PROJECT_DIR/.env"
        "$PROJECT_DIR/backend/config.py"
        "$PROJECT_DIR/nginx/nginx.conf"
    )

    # 检查文件是否存在
    local existing_files=()
    for file in "${config_files[@]}"; do
        [[ -f "$file" ]] && existing_files+=("$file")
    done

    if [[ ${#existing_files[@]} -eq 0 ]]; then
        log_warn "没有找到配置文件"
        return 0
    fi

    # 创建备份
    if ! tar -czf "$temp_file" -C "$PROJECT_DIR" \
        docker-compose.yml \
        .env \
        backend/config.py \
        nginx/nginx.conf 2>/dev/null; then
        log_error "配置文件备份失败"
        rm -f "$temp_file"
        return 1
    fi

    # 验证备份
    if ! verify_backup_file "$temp_file"; then
        log_error "配置文件备份验证失败"
        rm -f "$temp_file"
        return 1
    fi

    mv "$temp_file" "$backup_file"

    log_info "配置文件备份完成: $backup_file"
    echo "$backup_file"
}

# ==============================================================================
# 验证函数
# ==============================================================================

# 验证备份文件
verify_backup_file() {
    local backup_file=$1

    if [[ ! -f "$backup_file" ]]; then
        log_error "备份文件不存在: $backup_file"
        return 1
    fi

    # 检查文件大小
    local size=$(stat -c%s "$backup_file" 2>/dev/null || stat -f%z "$backup_file")
    if [[ "$size" -lt 100 ]]; then
        log_error "备份文件过小 (${size} bytes)，可能损坏"
        return 1
    fi

    # 如果是gzip文件，测试完整性
    if [[ "$backup_file" == *.gz ]]; then
        if ! gzip -t "$backup_file" 2>/dev/null; then
            log_error "gzip 文件损坏: $backup_file"
            return 1
        fi
    fi

    # 如果是tar文件，测试完整性
    if [[ "$backup_file" == *.tar.gz ]]; then
        if ! tar -tzf "$backup_file" > /dev/null 2>&1; then
            log_error "tar 文件损坏: $backup_file"
            return 1
        fi
    fi

    log_info "备份验证通过: $backup_file (${size} bytes)"
    return 0
}

# 验证备份（外部调用）
verify_backup() {
    local backup_file=$1

    if [[ -z "$backup_file" ]]; then
        log_error "请指定备份文件"
        return 1
    fi

    log_info "验证备份: $backup_file"

    if verify_backup_file "$backup_file"; then
        log_info "✓ 备份文件验证通过"

        # 显示文件详情
        echo "文件详情:"
        ls -lh "$backup_file"

        return 0
    else
        log_error "✗ 备份文件验证失败"
        return 1
    fi
}

# ==============================================================================
# 清理函数
# ==============================================================================

# 清理旧备份
cleanup_old_backups() {
    log_info "清理 ${RETENTION_DAYS} 天前的备份..."

    local deleted_count=0

    # 清理数据库备份
    while IFS= read -r -d '' file; do
        rm -f "$file"
        ((deleted_count++))
    done < <(find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +"$RETENTION_DAYS" -print0 2>/dev/null)

    # 清理配置文件备份（保留更多天数）
    while IFS= read -r -d '' file; do
        rm -f "$file"
        ((deleted_count++))
    done < <(find "$BACKUP_DIR" -name "config_*.tar.gz" -mtime +$((RETENTION_DAYS * 2)) -print0 2>/dev/null)

    log_info "清理完成，删除了 ${deleted_count} 个旧备份文件"

    # 清理旧日志文件（30天）
    find "$LOG_DIR" -name "backup_*.log" -mtime +30 -delete 2>/dev/null || true
}

# ==============================================================================
# 列出备份
# ==============================================================================

list_backups() {
    log_info "备份列表:"
    echo ""

    # 数据库备份
    echo "=== 数据库备份 ==="
    local db_files=$(find "$BACKUP_DIR" -name "db_*.sql.gz" 2>/dev/null | sort -r)
    if [[ -n "$db_files" ]]; then
        echo "$db_files" | while read -r file; do
            local size=$(ls -lh "$file" | awk '{print $5}')
            echo "  $(basename "$file") (${size})"
        done
    else
        echo "  无"
    fi

    # 配置文件备份
    echo ""
    echo "=== 配置文件备份 ==="
    local config_files=$(find "$BACKUP_DIR" -name "config_*.tar.gz" 2>/dev/null | sort -r | head -5)
    if [[ -n "$config_files" ]]; then
        echo "$config_files" | while read -r file; do
            local size=$(ls -lh "$file" | awk '{print $5}')
            echo "  $(basename "$file") (${size})"
        done
    else
        echo "  无"
    fi

    # 磁盘使用
    local backup_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | awk '{print $1}')
    echo ""
    echo "总大小: ${backup_size}"
}

# ==============================================================================
# Cron 管理
# ==============================================================================

# 安装定时任务
install_cron() {
    log_info "安装定时备份任务..."

    local cron_entry="0 2 * * * $SCRIPT_DIR/scripts/deploy_new/backup.sh >> $LOG_DIR/cron_backup.log 2>&1"

    # 检查是否已存在
    if crontab -l 2>/dev/null | grep -q "scripts/deploy_new/backup.sh"; then
        log_warn "定时任务已存在"
        return 0
    fi

    # 添加定时任务
    (crontab -l 2>/dev/null; echo "$cron_entry") | crontab -

    log_info "定时任务已安装: 每天凌晨 2 点执行备份"
    log_info "日志文件: $LOG_DIR/cron_backup.log"
}

# 移除定时任务
remove_cron() {
    log_info "移除定时备份任务..."

    crontab -l 2>/dev/null | grep -v "scripts/deploy_new/backup.sh" | crontab -

    log_info "定时任务已移除"
}

# ==============================================================================
# 全量备份
# ==============================================================================

backup_all() {
    log_info "========================================="
    log_info "开始全量备份"
    log_info "========================================="

    local start_time=$(date +%s)
    local backup_files=()

    # 初始化
    init_logging
    mkdir -p "$BACKUP_DIR"

    # 检查环境
    if ! check_docker; then
        log_error "Docker 环境检查失败"
        return 1
    fi

    if ! check_db_container; then
        log_error "数据库容器检查失败"
        return 1
    fi

    # 备份数据库
    local db_backup=$(backup_database)
    if [[ -n "$db_backup" && -f "$db_backup" ]]; then
        backup_files+=("$db_backup")
    fi

    # 备份配置
    local config_backup=$(backup_config)
    if [[ -n "$config_backup" && -f "$config_backup" ]]; then
        backup_files+=("$config_backup")
    fi

    # 清理旧备份
    cleanup_old_backups

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_info "========================================="
    log_info "全量备份完成，耗时: ${duration} 秒"
    log_info "备份文件数: ${#backup_files[@]}"
    log_info "========================================="
}

# 快速备份（仅数据库）
backup_quick() {
    log_info "========================================="
    log_info "开始快速备份"
    log_info "========================================="

    local start_time=$(date +%s)

    # 初始化
    init_logging
    mkdir -p "$BACKUP_DIR"

    # 检查环境
    if ! check_docker; then
        log_error "Docker 环境检查失败"
        return 1
    fi

    if ! check_db_container; then
        log_error "数据库容器检查失败"
        return 1
    fi

    # 备份数据库
    backup_database

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_info "========================================="
    log_info "快速备份完成，耗时: ${duration} 秒"
    log_info "========================================="
}

# ==============================================================================
# 显示帮助
# ==============================================================================

show_help() {
    cat << EOF
智能知识系统 - 部署备份脚本

用法: $0 [命令] [选项]

命令:
    all                     执行全量备份（默认）
    quick                   快速备份（仅数据库）
    db                      仅备份数据库
    config                  仅备份配置文件
    verify <file>           验证备份文件
    list                    列出所有备份
    clean                   清理旧备份
    install-cron            安装定时备份任务
    remove-cron             移除定时备份任务
    help                    显示此帮助信息

环境变量:
    BACKUP_DIR              备份存储目录 (默认: ./backups)
    RETENTION_DAYS          备份保留天数 (默认: 7)

示例:
    $0                      # 执行全量备份
    $0 quick                # 快速备份
    $0 verify backups/db_full_20240325.sql.gz
    $0 list                 # 列出所有备份
    $0 install-cron         # 安装每天凌晨2点的定时备份

EOF
}

# ==============================================================================
# 主函数
# ==============================================================================

main() {
    local action=${1:-all}

    case "$action" in
        all|full|"")
            backup_all
            ;;
        quick|q)
            backup_quick
            ;;
        db|database)
            init_logging
            check_docker && check_db_container && backup_database
            ;;
        config)
            init_logging
            backup_config
            ;;
        verify)
            init_logging
            verify_backup "$2"
            ;;
        list|ls)
            list_backups
            ;;
        clean|cleanup)
            init_logging
            cleanup_old_backups
            ;;
        install-cron)
            install_cron
            ;;
        remove-cron)
            remove_cron
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $action"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
