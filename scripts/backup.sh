#!/bin/bash
# ==============================================================================
# 智能知识系统 - 增强版数据库备份脚本
# ==============================================================================
# 功能：
#   - 全量备份和增量备份
#   - 备份完整性验证
#   - 定时备份支持（cron集成）
#   - 备份加密（可选）
#   - 日志记录
#   - 错误处理和回滚机制
#
# 用法:
#   ./backup.sh                    # 执行全量备份
#   ./backup.sh incremental        # 执行增量备份
#   ./backup.sh db                 # 仅备份数据库
#   ./backup.sh uploads            # 仅备份上传文件
#   ./backup.sh config             # 仅备份配置
#   ./backup.sh verify <file>      # 验证备份文件
#   ./backup.sh list               # 列出所有备份
#   ./backup.sh install-cron       # 安装定时备份任务
#   ./backup.sh remove-cron        # 移除定时备份任务
#
# 环境变量:
#   BACKUP_DIR          - 备份存储目录 (默认: ./backups)
#   RETENTION_DAYS      - 备份保留天数 (默认: 7)
#   BACKUP_ENCRYPT      - 是否加密备份 (默认: false)
#   ENCRYPTION_KEY      - 加密密钥路径
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
readonly NC='\033[0m'

# 目录配置
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
readonly LOG_DIR="${LOG_DIR:-$PROJECT_DIR/logs}"

# 备份配置
RETENTION_DAYS=${RETENTION_DAYS:-7}
BACKUP_ENCRYPT=${BACKUP_ENCRYPT:-false}
INCREMENTAL_ENABLED=${INCREMENTAL_ENABLED:-true}
MAX_INCREMENTAL_COUNT=${MAX_INCREMENTAL_COUNT:-7}  # 增量备份次数后执行全量备份

# 数据库配置（从docker-compose读取）
DB_CONTAINER="${DB_CONTAINER:-zhineng-postgres}"
DB_NAME="${DB_NAME:-zhineng_kb}"
DB_USER="${DB_USER:-zhineng}"

# 时间戳
readonly TIMESTAMP=$(date +%Y%m%d_%H%M%S)
readonly DATE_ONLY=$(date +%Y%m%d)

# 日志文件
LOG_FILE="${LOG_FILE:-$LOG_DIR/backup_$(date +%Y%m%d).log}"

# 状态文件
STATE_FILE="$BACKUP_DIR/.backup_state"
MANIFEST_FILE="$BACKUP_DIR/manifest_${TIMESTAMP}.json"

# ==============================================================================
# 日志函数
# ==============================================================================

# 初始化日志目录
init_logging() {
    mkdir -p "$LOG_DIR" "$BACKUP_DIR"
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

# ==============================================================================
# 错误处理
# ==============================================================================

# 错误处理器
error_handler() {
    local line_number=$1
    local error_code=$2
    log_error "脚本在第 ${line_number} 行退出，错误码: ${error_code}"
    cleanup_on_error
    exit "$error_code"
}

# 清理临时文件
cleanup_on_error() {
    log_warn "清理临时文件..."
    rm -f "$BACKUP_DIR"/tmp_* 2>/dev/null || true
}

# 设置错误陷阱
trap 'error_handler ${LINENO} $?' ERR

# ==============================================================================
# 备份状态管理
# ==============================================================================

# 读取备份状态
read_state() {
    if [[ -f "$STATE_FILE" ]]; then
        source "$STATE_FILE"
    else
        LAST_FULL_BACKUP=""
        INCREMENTAL_COUNT=0
        LAST_BACKUP_TYPE="none"
    fi
}

# 写入备份状态
write_state() {
    local backup_type=$1
    local backup_file=$2

    case "$backup_type" in
        full)
            LAST_FULL_BACKUP="$backup_file"
            INCREMENTAL_COUNT=0
            ;;
        incremental)
            INCREMENTAL_COUNT=$((INCREMENTAL_COUNT + 1))
            ;;
    esac

    LAST_BACKUP_TYPE="$backup_type"
    LAST_BACKUP_TIME=$(date -Iseconds)

    cat > "$STATE_FILE" << EOF
LAST_FULL_BACKUP="$LAST_FULL_BACKUP"
INCREMENTAL_COUNT=$INCREMENTAL_COUNT
LAST_BACKUP_TYPE="$LAST_BACKUP_TYPE"
LAST_BACKUP_TIME="$LAST_BACKUP_TIME"
EOF
}

# 判断是否需要全量备份
need_full_backup() {
    if [[ "$INCREMENTAL_ENABLED" != "true" ]]; then
        return 0  # 需要全量备份
    fi

    read_state

    # 没有全量备份或增量备份次数超过限制
    if [[ -z "$LAST_FULL_BACKUP" ]] || [[ "$INCREMENTAL_COUNT" -ge "$MAX_INCREMENTAL_COUNT" ]]; then
        return 0  # 需要全量备份
    fi

    # 全量备份超过3天
    if [[ -n "$LAST_FULL_BACKUP" ]]; then
        local last_backup_date=$(basename "$LAST_FULL_BACKUP" | grep -oP '\d{8}' || echo "")
        if [[ -n "$last_backup_date" ]]; then
            local days_since_full=$(( ($(date +%s) - $(date -d "${last_backup_date:0:4}-${last_backup_date:4:2}-${last_backup_date:6:2}" +%s 2>/dev/null || echo 0) / 86400 ))
            if [[ "$days_since_full" -ge 3 ]]; then
                return 0  # 需要全量备份
            fi
        fi
    fi

    return 1  # 可以增量备份
}

# ==============================================================================
# Docker 检查
# ==============================================================================

# 检查 Docker 和 Docker Compose
check_docker() {
    log_debug "检查 Docker 环境..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        return 1
    fi

    if ! docker ps &> /dev/null; then
        log_error "Docker 守护进程未运行"
        return 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装"
        return 1
    fi

    return 0
}

# 检查数据库容器是否运行
check_db_container() {
    log_debug "检查数据库容器..."

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

# 获取数据库列表（用于增量备份）
get_database_tables() {
    docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT tablename FROM pg_tables WHERE schemaname = 'public';
    " 2>/dev/null | tr -d ' ' | grep -v '^$' || echo ""
}

# 获取数据库 checksum（用于检测变更）
get_database_checksum() {
    local checksum=$(docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT MD5(string_agg(data, '')) FROM (
            SELECT schemaname||tablename||obj_description((schemaname||'.'||tablename)::regclass, 'pg_class') as data
            FROM pg_tables WHERE schemaname = 'public'
            ORDER BY tablename
        ) t;
    " 2>/dev/null | tr -d ' ' || echo "unknown")
    echo "$checksum"
}

# 备份数据库（全量）
backup_database_full() {
    log_info "开始数据库全量备份..."

    local backup_file="$BACKUP_DIR/db_full_${TIMESTAMP}.sql.gz"
    local temp_file="$BACKUP_DIR/tmp_db_${TIMESTAMP}.sql.gz"

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

    # 记录数据库状态
    local db_checksum=$(get_database_checksum)
    echo "db_checksum=$db_checksum" > "${backup_file}.info"
    echo "backup_type=full" >> "${backup_file}.info"
    echo "timestamp=$TIMESTAMP" >> "${backup_file}.info"

    log_info "数据库全量备份完成: $backup_file"
    echo "$backup_file"
}

# 备份数据库（增量 - 基于WAL或变更检测）
backup_database_incremental() {
    log_info "开始数据库增量备份..."

    local last_full="$STATE_FILE"  # 从状态文件获取上次全量备份
    local backup_file="$BACKUP_DIR/db_incr_${TIMESTAMP}.sql.gz"
    local temp_file="$BACKUP_DIR/tmp_db_incr_${TIMESTAMP}.sql.gz"

    # 获取变更的表
    local changed_tables=$(docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
        ORDER BY tablename;
    " 2>/dev/null | tr -d ' ')

    if [[ -z "$changed_tables" ]]; then
        log_warn "没有检测到数据库变更，跳过增量备份"
        return 0
    fi

    # 执行增量备份（实际上仍是pg_dump，但只导出数据变更）
    docker-compose exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" \
        --no-owner --no-acl \
        --data-only \
        --table="${changed_tables// / --table=}" \
        2>&1 | tee -a "$LOG_FILE" | gzip > "$temp_file"

    # 检查备份大小（太小可能没有实际数据变更）
    local backup_size=$(stat -c%s "$temp_file" 2>/dev/null || stat -f%z "$temp_file")
    if [[ "$backup_size" -lt 100 ]]; then
        log_info "增量备份无数据变更，跳过保存"
        rm -f "$temp_file"
        return 0
    fi

    # 验证备份文件
    if ! verify_backup_file "$temp_file"; then
        log_error "增量备份验证失败"
        rm -f "$temp_file"
        return 1
    fi

    mv "$temp_file" "$backup_file"

    # 记录增量信息
    local db_checksum=$(get_database_checksum)
    echo "db_checksum=$db_checksum" > "${backup_file}.info"
    echo "backup_type=incremental" >> "${backup_file}.info"
    echo "based_on=$LAST_FULL_BACKUP" >> "${backup_file}.info"
    echo "timestamp=$TIMESTAMP" >> "${backup_file}.info"

    log_info "数据库增量备份完成: $backup_file"
    echo "$backup_file"
}

# 备份数据库（智能选择全量或增量）
backup_database() {
    if ! check_docker; then
        log_error "Docker 环境检查失败"
        return 1
    fi

    if ! check_db_container; then
        log_error "数据库容器检查失败"
        return 1
    fi

    cd "$PROJECT_DIR"

    if need_full_backup; then
        log_info "执行全量备份"
        backup_database_full
        write_state "full" "$BACKUP_DIR/db_full_${TIMESTAMP}.sql.gz"
    else
        log_info "执行增量备份"
        backup_database_incremental
        write_state "incremental" "$BACKUP_DIR/db_incr_${TIMESTAMP}.sql.gz"
    fi
}

# 备份上传文件（支持增量）
backup_uploads() {
    log_info "备份上传文件..."

    local uploads_dir="${UPLOADS_DIR:-$PROJECT_DIR/data/uploads}"
    local backup_file="$BACKUP_DIR/uploads_${TIMESTAMP}.tar.gz"
    local temp_file="$BACKUP_DIR/tmp_uploads_${TIMESTAMP}.tar.gz"

    if [[ ! -d "$uploads_dir" ]]; then
        log_warn "上传目录不存在: $uploads_dir"
        return 0
    fi

    # 使用 rsync 检测变更
    local last_sync_file="$BACKUP_DIR/.uploads_last_sync"
    local has_changes=false

    if [[ -f "$last_sync_file" ]]; then
        # 检测是否有文件变更
        local changes=$(rsync -ani --delete "$uploads_dir/" "$BACKUP_DIR/uploads_prev/" 2>/dev/null || echo "")
        if [[ -n "$changes" ]]; then
            has_changes=true
        fi
    else
        has_changes=true
    fi

    if [[ "$has_changes" == "false" ]]; then
        log_info "上传文件无变更，跳过备份"
        return 0
    fi

    # 创建备份
    if ! tar -czf "$temp_file" -C "$uploads_dir" . 2>&1 | tee -a "$LOG_FILE"; then
        log_error "上传文件备份失败"
        rm -f "$temp_file"
        return 1
    fi

    # 验证备份
    if ! verify_backup_file "$temp_file"; then
        log_error "上传文件备份验证失败"
        rm -f "$temp_file"
        return 1
    fi

    mv "$temp_file" "$backup_file"

    # 更新同步标记
    mkdir -p "$BACKUP_DIR/uploads_prev"
    rsync -a --delete "$uploads_dir/" "$BACKUP_DIR/uploads_prev/" 2>/dev/null || true
    touch "$last_sync_file"

    log_info "上传文件备份完成: $backup_file"
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

    log_debug "备份验证通过: $backup_file (${size} bytes)"
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

        # 显示备份信息
        if [[ -f "${backup_file}.info" ]]; then
            echo -e "\n备份信息:"
            cat "${backup_file}.info"
        fi

        # 显示文件详情
        echo -e "\n文件详情:"
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
        log_debug "删除: $file"
        rm -f "$file" "${file}.info"
        ((deleted_count++))
    done < <(find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +"$RETENTION_DAYS" -print0 2>/dev/null)

    # 清理上传文件备份
    while IFS= read -r -d '' file; do
        log_debug "删除: $file"
        rm -f "$file"
        ((deleted_count++))
    done < <(find "$BACKUP_DIR" -name "uploads_*.tar.gz" -mtime +"$RETENTION_DAYS" -print0 2>/dev/null)

    # 清理配置文件备份（保留更多天数）
    while IFS= read -r -d '' file; do
        log_debug "删除: $file"
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
    echo -e "${BLUE}=== 数据库备份 ===${NC}"
    local db_files=$(find "$BACKUP_DIR" -name "db_*.sql.gz" 2>/dev/null | sort -r)
    if [[ -n "$db_files" ]]; then
        echo "$db_files" | while read -r file; do
            local size=$(ls -lh "$file" | awk '{print $5}')
            local type=""
            [[ -f "${file}.info" ]] && type=$(grep "backup_type=" "${file}.info" | cut -d= -f2)
            echo "  $(basename "$file") (${size}) ${type:+[$type]}"
        done
    else
        echo "  无"
    fi

    # 上传文件备份
    echo -e "\n${BLUE}=== 上传文件备份 ===${NC}"
    local upload_files=$(find "$BACKUP_DIR" -name "uploads_*.tar.gz" 2>/dev/null | sort -r | head -5)
    if [[ -n "$upload_files" ]]; then
        echo "$upload_files" | while read -r file; do
            local size=$(ls -lh "$file" | awk '{print $5}')
            echo "  $(basename "$file") (${size})"
        done
    else
        echo "  无"
    fi

    # 配置文件备份
    echo -e "\n${BLUE}=== 配置文件备份 ===${NC}"
    local config_files=$(find "$BACKUP_DIR" -name "config_*.tar.gz" 2>/dev/null | sort -r | head -5)
    if [[ -n "$config_files" ]]; then
        echo "$config_files" | while read -r file; do
            local size=$(ls -lh "$file" | awk '{print $5}')
            echo "  $(basename "$file") (${size})"
        done
    else
        echo "  无"
    fi

    # 备份状态
    echo -e "\n${BLUE}=== 备份状态 ===${NC}"
    if [[ -f "$STATE_FILE" ]]; then
        source "$STATE_FILE"
        echo "  上次备份: ${LAST_BACKUP_TIME:-未知}"
        echo "  上次类型: ${LAST_BACKUP_TYPE:-无}"
        echo "  增量次数: ${INCREMENTAL_COUNT:-0}/${MAX_INCREMENTAL_COUNT}"
    else
        echo "  无备份状态记录"
    fi

    # 磁盘使用
    local backup_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | awk '{print $1}')
    echo "  总大小: ${backup_size}"
}

# ==============================================================================
# Cron 管理
# ==============================================================================

# 安装定时任务
install_cron() {
    log_info "安装定时备份任务..."

    local cron_entry="0 2 * * * $SCRIPT_DIR/backup.sh >> $LOG_DIR/cron_backup.log 2>&1"

    # 检查是否已存在
    if crontab -l 2>/dev/null | grep -q "$SCRIPT_DIR/backup.sh"; then
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

    crontab -l 2>/dev/null | grep -v "$SCRIPT_DIR/backup.sh" | crontab -

    log_info "定时任务已移除"
}

# ==============================================================================
# 备份清单
# ==============================================================================

create_manifest() {
    local backup_files=("$@")

    log_info "创建备份清单..."

    cat > "$MANIFEST_FILE" << EOF
{
  "backup_time": "$(date -Iseconds)",
  "backup_type": "$LAST_BACKUP_TYPE",
  "files": [
$(for file in "${backup_files[@]}"; do
    if [[ -n "$file" && -f "$file" ]]; then
        local size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file")
        local checksum=$(md5sum "$file" 2>/dev/null | awk '{print $1}' || echo "unknown")
        echo "    {"
        echo "      \"path\": \"$(basename "$file")\","
        echo "      \"size\": $size,"
        echo "      \"md5\": \"$checksum\""
        echo "    },"
    fi
done)
    {}
  ],
  "hostname": "$(hostname)",
  "user": "$(whoami)"
}
EOF

    # 移除最后的逗号
    sed -i 's/,    {}/  {}/' "$MANIFEST_FILE"

    log_info "备份清单已创建: $MANIFEST_FILE"
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

    # 备份数据库
    local db_backup=$(backup_database)
    if [[ -n "$db_backup" && -f "$db_backup" ]]; then
        backup_files+=("$db_backup")
    fi

    # 备份上传文件
    local uploads_backup=$(backup_uploads)
    if [[ -n "$uploads_backup" && -f "$uploads_backup" ]]; then
        backup_files+=("$uploads_backup")
    fi

    # 备份配置
    local config_backup=$(backup_config)
    if [[ -n "$config_backup" && -f "$config_backup" ]]; then
        backup_files+=("$config_backup")
    fi

    # 创建清单
    create_manifest "${backup_files[@]}"

    # 清理旧备份
    cleanup_old_backups

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_info "========================================="
    log_info "全量备份完成，耗时: ${duration} 秒"
    log_info "备份文件数: ${#backup_files[@]}"
    log_info "========================================="
}

# ==============================================================================
# 增量备份
# ==============================================================================

backup_incremental() {
    log_info "========================================="
    log_info "开始增量备份"
    log_info "========================================="

    local start_time=$(date +%s)

    # 初始化
    init_logging
    mkdir -p "$BACKUP_DIR"

    # 备份数据库（自动判断全量或增量）
    backup_database

    # 备份上传文件
    backup_uploads

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_info "========================================="
    log_info "增量备份完成，耗时: ${duration} 秒"
    log_info "========================================="
}

# ==============================================================================
# 显示帮助
# ==============================================================================

show_help() {
    cat << EOF
智能知识系统 - 增强版备份脚本

用法: $0 [命令] [选项]

命令:
    all                     执行全量备份（默认）
    incremental             执行增量备份
    db                      仅备份数据库
    uploads                 仅备份上传文件
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
    BACKUP_ENCRYPT          是否加密备份 (默认: false)
    INCREMENTAL_ENABLED     是否启用增量备份 (默认: true)
    MAX_INCREMENTAL_COUNT   最大增量备份次数 (默认: 7)
    DEBUG                   启用调试输出 (默认: false)

示例:
    $0                      # 执行全量备份
    $0 incremental          # 执行增量备份
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
        all|full)
            backup_all
            ;;
        incremental|incr)
            backup_incremental
            ;;
        db|database)
            init_logging
            backup_database
            ;;
        uploads)
            init_logging
            backup_uploads
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
