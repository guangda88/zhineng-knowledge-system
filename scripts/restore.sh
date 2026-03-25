#!/bin/bash
# ==============================================================================
# 智能知识系统 - 数据恢复脚本
# ==============================================================================
# 功能：
#   - 数据库恢复
#   - 上传文件恢复
#   - 配置文件恢复
#   - 全量恢复
#   - 备份验证
#   - 回滚机制
#   - 自动备份当前状态
#
# 用法:
#   ./restore.sh list                    # 列出所有备份
#   ./restore.sh restore-db <file>       # 恢复数据库
#   ./restore.sh restore-uploads <file>  # 恢复上传文件
#   ./restore.sh restore-config <file>   # 恢复配置文件
#   ./restore.sh restore-full <date>     # 恢复指定日期的全量备份
#   ./restore.sh rollback                # 回滚到上一个备份
#   ./restore.sh verify <file>           # 验证备份文件
#   ./restore.sh info <file>             # 显示备份详细信息
#
# 环境变量:
#   BACKUP_DIR          - 备份存储目录 (默认: ./backups)
#   AUTO_BACKUP         - 恢复前自动备份 (默认: true)
#   LOG_FILE            - 日志文件路径
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
readonly PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
readonly LOG_DIR="${LOG_DIR:-$PROJECT_DIR/logs}"

# 数据库配置
DB_CONTAINER="${DB_CONTAINER:-zhineng-postgres}"
DB_NAME="${DB_NAME:-zhineng_kb}"
DB_USER="${DB_USER:-zhineng}"

# 恢复配置
AUTO_BACKUP=${AUTO_BACKUP:-true}
ROLLBACK_DIR="$BACKUP_DIR/rollback"

# 日志文件
LOG_FILE="${LOG_FILE:-$LOG_DIR/restore_$(date +%Y%m%d).log}"

# ==============================================================================
# 日志函数
# ==============================================================================

# 初始化日志目录
init_logging() {
    mkdir -p "$LOG_DIR" "$ROLLBACK_DIR"
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

log_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $*" | tee -a "$LOG_FILE"
    fi
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $*" | tee -a "$LOG_FILE"
}

# ==============================================================================
# 错误处理
# ==============================================================================

# 错误处理器
error_handler() {
    local line_number=$1
    local error_code=$2
    log_error "脚本在第 ${line_number} 行退出，错误码: ${error_code}"
    log_error "恢复过程中发生错误，请检查日志: $LOG_FILE"
    exit "$error_code"
}

# 设置错误陷阱
trap 'error_handler ${LINENO} $?' ERR

# ==============================================================================
# 确认函数
# ==============================================================================

# 用户确认
confirm() {
    local prompt=$1
    local default=${2:-n}

    if [[ "$FORCE_CONFIRM" == "true" ]]; then
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
# 备份验证
# ==============================================================================

# 验证备份文件
verify_backup_file() {
    local backup_file=$1

    if [[ ! -f "$backup_file" ]]; then
        log_error "备份文件不存在: $backup_file"
        return 1
    fi

    log_step "验证备份文件: $(basename "$backup_file")"

    # 检查文件大小
    local size=$(stat -c%s "$backup_file" 2>/dev/null || stat -f%z "$backup_file")
    if [[ "$size" -lt 100 ]]; then
        log_error "备份文件过小 (${size} bytes)，可能损坏"
        return 1
    fi

    # 检查文件类型
    local mime=$(file -b --mime-type "$backup_file" 2>/dev/null)
    log_debug "文件类型: $mime, 大小: $size bytes"

    # 如果是gzip文件，测试解压
    if [[ "$backup_file" == *.gz ]]; then
        if ! gzip -t "$backup_file" 2>/dev/null; then
            log_error "gzip 文件损坏"
            return 1
        fi
        log_info "✓ gzip 文件完整性验证通过"
    fi

    # 如果是tar文件，测试解压
    if [[ "$backup_file" == *.tar.gz ]]; then
        if ! tar -tzf "$backup_file" > /dev/null 2>&1; then
            log_error "tar 文件损坏"
            return 1
        fi
        log_info "✓ tar 文件完整性验证通过"
    fi

    # 读取备份信息
    if [[ -f "${backup_file}.info" ]]; then
        log_debug "备份信息:"
        while IFS= read -r line; do
            log_debug "  $line"
        done < "${backup_file}.info"
    fi

    return 0
}

# 显示备份详细信息
show_backup_info() {
    local backup_file=$1

    if [[ ! -f "$backup_file" ]]; then
        log_error "备份文件不存在: $backup_file"
        return 1
    fi

    echo ""
    echo -e "${CYAN}=== 备份文件信息 ===${NC}"
    echo "文件名: $(basename "$backup_file")"
    echo "完整路径: $backup_file"
    echo "文件大小: $(ls -lh "$backup_file" | awk '{print $5}')"
    echo "修改时间: $(stat -c %y "$backup_file" 2>/dev/null | cut -d'.' -f1)"
    echo "文件类型: $(file -b "$backup_file")"
    echo "MD5 校验: $(md5sum "$backup_file" 2>/dev/null | awk '{print $1}')"

    # 如果有info文件，显示更多信息
    if [[ -f "${backup_file}.info" ]]; then
        echo -e "\n备份元数据:"
        cat "${backup_file}.info" | sed 's/^/  /'
    fi

    # 如果是SQL文件，显示前几行
    if [[ "$backup_file" == *.sql.gz ]]; then
        echo -e "\nSQL 预览:"
        gunzip -c "$backup_file" 2>/dev/null | head -20 | sed 's/^/  /'
    fi

    echo ""
}

# ==============================================================================
# 回滚管理
# ==============================================================================

# 保存当前状态用于回滚
save_rollback_state() {
    local component=$1

    if [[ "$AUTO_BACKUP" != "true" ]]; then
        return 0
    fi

    log_step "保存当前状态用于回滚..."

    local rollback_file="$ROLLBACK_DIR/${component}_rollback_$(date +%Y%m%d_%H%M%S)"

    case "$component" in
        database)
            # 备份当前数据库
            docker-compose exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" \
                --no-owner --no-acl 2>/dev/null | gzip > "$rollback_file.sql.gz" || {
                log_warn "无法保存数据库回滚状态"
                return 1
            }
            ;;
        uploads)
            # 备份当前上传文件
            local uploads_dir="${UPLOADS_DIR:-$PROJECT_DIR/data/uploads}"
            if [[ -d "$uploads_dir" ]]; then
                tar -czf "$rollback_file.tar.gz" -C "$uploads_dir" . 2>/dev/null || {
                    log_warn "无法保存上传文件回滚状态"
                    return 1
                }
            fi
            ;;
        config)
            # 备份当前配置
            tar -czf "$rollback_file.tar.gz" -C "$PROJECT_DIR" \
                docker-compose.yml .env backend/config.py 2>/dev/null || {
                log_warn "无法保存配置回滚状态"
                return 1
            }
            ;;
    esac

    # 保存回滚信息
    echo "$rollback_file" > "$ROLLBACK_DIR/.last_rollback"
    log_info "回滚状态已保存: $rollback_file"
}

# 执行回滚
perform_rollback() {
    if [[ ! -f "$ROLLBACK_DIR/.last_rollback" ]]; then
        log_error "没有找到回滚状态"
        return 1
    fi

    local rollback_file=$(cat "$ROLLBACK_DIR/.last_rollback")

    if [[ ! -f "$rollback_file" ]]; then
        log_error "回滚文件不存在: $rollback_file"
        return 1
    fi

    log_warn "警告: 这将回滚到恢复前的状态"
    confirm "确认回滚?" n || return 0

    # 根据文件类型恢复
    if [[ "$rollback_file" == *.sql.gz ]]; then
        restore_database_from_file "$rollback_file"
    elif [[ "$rollback_file" == uploads_*.tar.gz ]]; then
        restore_uploads_from_file "$rollback_file"
    elif [[ "$rollback_file" == config_*.tar.gz ]]; then
        restore_config_from_file "$rollback_file"
    fi

    log_info "回滚完成"
}

# ==============================================================================
# 数据库恢复
# ==============================================================================

# 从文件恢复数据库
restore_database_from_file() {
    local backup_file=$1
    local skip_confirm=${2:-false}

    log_step "准备恢复数据库..."

    # 验证备份
    if ! verify_backup_file "$backup_file"; then
        return 1
    fi

    # 确认操作
    if [[ "$skip_confirm" != "true" ]]; then
        log_warn "警告: 这将覆盖当前数据库!"
        if ! confirm "确认继续恢复数据库?" n; then
            log_info "取消操作"
            return 0
        fi
    fi

    # 保存回滚状态
    save_rollback_state "database"

    log_info "开始恢复数据库..."

    cd "$PROJECT_DIR"

    # 停止API服务
    log_step "停止API服务..."
    docker-compose stop api 2>/dev/null || true

    # 清空现有数据库（可选）
    if confirm "是否清空现有数据库? (推荐)" y; then
        log_step "清空现有数据库..."
        docker-compose exec -T postgres psql -U "$DB_USER" "$DB_NAME" \
            -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" \
            --quiet 2>/dev/null || {
            log_warn "清空数据库失败，继续恢复..."
        }
    fi

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

    return 0
}

# 恢复数据库（命令入口）
restore_database() {
    local backup_file=$1

    if [[ -z "$backup_file" ]]; then
        log_error "请指定备份文件"
        echo ""
        echo "可用的数据库备份:"
        ls -lht "$BACKUP_DIR"/db_*.sql.gz 2>/dev/null | head -10 || echo "无"
        return 1
    fi

    # 支持日期格式
    if [[ ! -f "$backup_file" ]]; then
        local matched=$(find "$BACKUP_DIR" -name "db_${backup_file}*.sql.gz" | sort -r | head -1)
        if [[ -n "$matched" ]]; then
            backup_file="$matched"
            log_info "找到匹配的备份: $(basename "$backup_file")"
        else
            log_error "未找到匹配的备份: $backup_file"
            return 1
        fi
    fi

    restore_database_from_file "$backup_file"
}

# ==============================================================================
# 上传文件恢复
# ==============================================================================

# 从文件恢复上传文件
restore_uploads_from_file() {
    local backup_file=$1
    local skip_confirm=${2:-false}

    log_step "准备恢复上传文件..."

    # 验证备份
    if ! verify_backup_file "$backup_file"; then
        return 1
    fi

    # 确认操作
    if [[ "$skip_confirm" != "true" ]]; then
        log_warn "警告: 这将覆盖当前上传文件!"
        if ! confirm "确认继续恢复上传文件?" n; then
            log_info "取消操作"
            return 0
        fi
    fi

    # 保存回滚状态
    save_rollback_state "uploads"

    log_info "开始恢复上传文件..."

    local upload_dir="${UPLOADS_DIR:-$PROJECT_DIR/data/uploads}"
    mkdir -p "$upload_dir"

    # 备份现有文件
    if [[ "$(ls -A "$upload_dir" 2>/dev/null)" ]]; then
        local temp_backup="$upload_dir/../uploads_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
        log_step "备份现有文件到: $temp_backup"
        tar -czf "$temp_backup" -C "$upload_dir" . 2>/dev/null || true
    fi

    # 清空现有文件
    log_step "清空现有文件..."
    rm -rf "$upload_dir"/* 2>/dev/null || true

    # 解压备份
    log_step "解压备份文件..."
    if ! tar -xzf "$backup_file" -C "$upload_dir" 2>&1 | tee -a "$LOG_FILE"; then
        log_error "上传文件恢复失败"
        return 1
    fi

    # 统计恢复的文件
    local file_count=$(find "$upload_dir" -type f | wc -l)
    local total_size=$(du -sh "$upload_dir" 2>/dev/null | awk '{print $1}')

    log_info "上传文件恢复完成!"
    log_info "  文件数量: ${file_count}"
    log_info "  总大小: ${total_size}"

    return 0
}

# 恢复上传文件（命令入口）
restore_uploads() {
    local backup_file=$1

    if [[ -z "$backup_file" ]]; then
        log_error "请指定备份文件"
        echo ""
        echo "可用的上传文件备份:"
        ls -lht "$BACKUP_DIR"/uploads_*.tar.gz 2>/dev/null | head -10 || echo "无"
        return 1
    fi

    # 支持日期格式
    if [[ ! -f "$backup_file" ]]; then
        local matched=$(find "$BACKUP_DIR" -name "uploads_${backup_file}*.tar.gz" | sort -r | head -1)
        if [[ -n "$matched" ]]; then
            backup_file="$matched"
            log_info "找到匹配的备份: $(basename "$backup_file")"
        else
            log_error "未找到匹配的备份: $backup_file"
            return 1
        fi
    fi

    restore_uploads_from_file "$backup_file"
}

# ==============================================================================
# 配置文件恢复
# ==============================================================================

# 从文件恢复配置
restore_config_from_file() {
    local backup_file=$1
    local skip_confirm=${2:-false}

    log_step "准备恢复配置文件..."

    # 验证备份
    if ! verify_backup_file "$backup_file"; then
        return 1
    fi

    # 确认操作
    if [[ "$skip_confirm" != "true" ]]; then
        log_warn "警告: 这将覆盖当前配置文件!"
        if ! confirm "确认继续恢复配置文件?" n; then
            log_info "取消操作"
            return 0
        fi
    fi

    # 保存回滚状态
    save_rollback_state "config"

    log_info "开始恢复配置文件..."

    # 显示将要恢复的文件
    log_step "备份包含的文件:"
    tar -tzf "$backup_file" | sed 's/^/  /'

    # 恢复文件
    cd "$PROJECT_DIR"
    if ! tar -xzf "$backup_file" 2>&1 | tee -a "$LOG_FILE"; then
        log_error "配置文件恢复失败"
        return 1
    fi

    log_info "配置文件恢复完成!"
    log_warn "请重启服务以应用新配置:"
    echo "  docker-compose restart"
}

# 恢复配置文件（命令入口）
restore_config() {
    local backup_file=$1

    if [[ -z "$backup_file" ]]; then
        log_error "请指定备份文件"
        echo ""
        echo "可用的配置文件备份:"
        ls -lht "$BACKUP_DIR"/config_*.tar.gz 2>/dev/null | head -10 || echo "无"
        return 1
    fi

    # 支持日期格式
    if [[ ! -f "$backup_file" ]]; then
        local matched=$(find "$BACKUP_DIR" -name "config_${backup_file}*.tar.gz" | sort -r | head -1)
        if [[ -n "$matched" ]]; then
            backup_file="$matched"
            log_info "找到匹配的备份: $(basename "$backup_file")"
        else
            log_error "未找到匹配的备份: $backup_file"
            return 1
        fi
    fi

    restore_config_from_file "$backup_file"
}

# ==============================================================================
# 全量恢复
# ==============================================================================

restore_full() {
    local date_str=$1

    if [[ -z "$date_str" ]]; then
        log_error "请指定日期 (格式: YYYYMMDD)"
        echo ""
        echo "可用的备份日期:"
        find "$BACKUP_DIR" -name "db_*.sql.gz" -o -name "uploads_*.tar.gz" | \
            grep -oP '\d{8}' | sort -u | tail -10 || echo "无"
        return 1
    fi

    log_info "========================================="
    log_info "开始全量恢复: $date_str"
    log_info "========================================="

    # 查找该日期的备份
    local db_backup=$(find "$BACKUP_DIR" -name "db_${date_str}*.sql.gz" | sort -r | head -1)
    local uploads_backup=$(find "$BACKUP_DIR" -name "uploads_${date_str}*.tar.gz" | sort -r | head -1)
    local config_backup=$(find "$BACKUP_DIR" -name "config_${date_str}*.tar.gz" | sort -r | head -1)

    if [[ -z "$db_backup" ]]; then
        log_error "未找到该日期的数据库备份"
        return 1
    fi

    # 显示将要恢复的备份
    echo ""
    echo -e "${CYAN}=== 将要恢复的备份 ===${NC}"
    echo "数据库: $(basename "$db_backup")"
    [[ -n "$uploads_backup" ]] && echo "上传文件: $(basename "$uploads_backup")"
    [[ -n "$config_backup" ]] && echo "配置文件: $(basename "$config_backup")"
    echo ""

    # 确认
    if ! confirm "确认执行全量恢复?" n; then
        log_info "取消操作"
        return 0
    fi

    cd "$PROJECT_DIR"

    # 停止所有服务
    log_step "停止所有服务..."
    docker-compose stop 2>/dev/null || true

    # 恢复数据库
    log_info "恢复数据库..."
    if ! restore_database_from_file "$db_backup" true; then
        log_error "数据库恢复失败"
        docker-compose start
        return 1
    fi

    # 恢复上传文件
    if [[ -n "$uploads_backup" ]]; then
        log_info "恢复上传文件..."
        if ! restore_uploads_from_file "$uploads_backup" true; then
            log_warn "上传文件恢复失败，继续..."
        fi
    fi

    # 恢复配置文件
    if [[ -n "$config_backup" ]]; then
        log_info "恢复配置文件..."
        if ! restore_config_from_file "$config_backup" true; then
            log_warn "配置文件恢复失败，继续..."
        fi
    fi

    # 启动所有服务
    log_step "启动所有服务..."
    docker-compose start 2>/dev/null || true

    log_info "========================================="
    log_info "全量恢复完成!"
    log_info "========================================="
}

# ==============================================================================
# 列出备份
# ==============================================================================

list_backups() {
    echo ""
    echo -e "${CYAN}=== 智能知识系统 - 备份列表 ===${NC}"
    echo ""

    # 数据库备份
    echo -e "${BLUE}--- 数据库备份 ---${NC}"
    local db_files=$(find "$BACKUP_DIR" -name "db_*.sql.gz" 2>/dev/null | sort -r)
    if [[ -n "$db_files" ]]; then
        echo "$db_files" | while read -r file; do
            local size=$(ls -lh "$file" | awk '{print $5}')
            local date=$(stat -c %y "$file" 2>/dev/null | cut -d'.' -f1)
            local type="未知"
            [[ -f "${file}.info" ]] && type=$(grep "backup_type=" "${file}.info" | cut -d= -f2)
            printf "  %-40s %10s  %s  [%s]\n" "$(basename "$file")" "$size" "$date" "$type"
        done
    else
        echo "  无"
    fi

    # 上传文件备份
    echo -e "\n${BLUE}--- 上传文件备份 ---${NC}"
    local upload_files=$(find "$BACKUP_DIR" -name "uploads_*.tar.gz" 2>/dev/null | sort -r | head -10)
    if [[ -n "$upload_files" ]]; then
        echo "$upload_files" | while read -r file; do
            local size=$(ls -lh "$file" | awk '{print $5}')
            local date=$(stat -c %y "$file" 2>/dev/null | cut -d'.' -f1)
            printf "  %-40s %10s  %s\n" "$(basename "$file")" "$size" "$date"
        done
    else
        echo "  无"
    fi

    # 配置文件备份
    echo -e "\n${BLUE}--- 配置文件备份 ---${NC}"
    local config_files=$(find "$BACKUP_DIR" -name "config_*.tar.gz" 2>/dev/null | sort -r | head -10)
    if [[ -n "$config_files" ]]; then
        echo "$config_files" | while read -r file; do
            local size=$(ls -lh "$file" | awk '{print $5}')
            local date=$(stat -c %y "$file" 2>/dev/null | cut -d'.' -f1)
            printf "  %-40s %10s  %s\n" "$(basename "$file")" "$size" "$date"
        done
    else
        echo "  无"
    fi

    # 备份统计
    echo -e "\n${BLUE}--- 备份统计 ---${NC}"
    local db_count=$(find "$BACKUP_DIR" -name "db_*.sql.gz" 2>/dev/null | wc -l)
    local upload_count=$(find "$BACKUP_DIR" -name "uploads_*.tar.gz" 2>/dev/null | wc -l)
    local config_count=$(find "$BACKUP_DIR" -name "config_*.tar.gz" 2>/dev/null | wc -l)
    local total_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | awk '{print $1}')

    echo "  数据库备份: ${db_count} 个"
    echo "  上传文件备份: ${upload_count} 个"
    echo "  配置文件备份: ${config_count} 个"
    echo "  总大小: ${total_size}"

    # 回滚状态
    if [[ -f "$ROLLBACK_DIR/.last_rollback" ]]; then
        local last_rollback=$(cat "$ROLLBACK_DIR/.last_rollback")
        echo -e "\n${YELLOW}可用回滚: $(basename "$last_rollback")${NC}"
    fi

    echo ""
}

# ==============================================================================
# 显示帮助
# ==============================================================================

show_help() {
    cat << EOF
智能知识系统 - 数据恢复脚本

用法: $0 [命令] [参数]

命令:
    list                         列出所有备份
    restore-db <file>            恢复数据库
    restore-uploads <file>       恢复上传文件
    restore-config <file>        恢复配置文件
    restore-full <date>          恢复指定日期的全量备份
    rollback                     回滚到恢复前的状态
    verify <file>                验证备份文件
    info <file>                  显示备份详细信息

参数:
    <file>   备份文件路径或日期 (YYYYMMDD)
    <date>   备份日期 (YYYYMMDD)

环境变量:
    BACKUP_DIR          备份存储目录 (默认: ./backups)
    AUTO_BACKUP         恢复前自动备份 (默认: true)
    FORCE_CONFIRM       强制确认，跳过提示 (默认: false)
    DEBUG               启用调试输出 (默认: false)

示例:
    $0 list
    $0 restore-db 20240325
    $0 restore-db backups/db_full_20240325_120000.sql.gz
    $0 restore-full 20240325
    $0 verify backups/db_full_20240325.sql.gz
    $0 info backups/db_full_20240325.sql.gz

注意事项:
    1. 恢复操作会覆盖现有数据，请谨慎操作
    2. 恢复前会自动备份当前状态用于回滚
    3. 恢复后需要重启服务才能生效

EOF
}

# ==============================================================================
# 主函数
# ==============================================================================

main() {
    init_logging

    local command=${1:-""}

    case "$command" in
        list|ls)
            list_backups
            ;;
        restore-db)
            restore_database "$2"
            ;;
        restore-uploads)
            restore_uploads "$2"
            ;;
        restore-config)
            restore_config "$2"
            ;;
        restore-full)
            restore_full "$2"
            ;;
        rollback)
            perform_rollback
            ;;
        verify)
            verify_backup_file "$2"
            ;;
        info)
            show_backup_info "$2"
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
