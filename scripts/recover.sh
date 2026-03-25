#!/bin/bash
# 智能知识系统 - 灾难恢复脚本
# P6阶段: 高级特性

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 配置
BACKUP_DIR="${BACKUP_DIR:-./backups}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 显示帮助
show_help() {
    cat << EOF
智能知识系统 - 灾难恢复脚本

用法: $0 [命令] [选项]

命令:
    list                    列出所有备份
    restore-db <file>        恢复数据库
    restore-uploads <file>   恢复上传文件
    restore-config <file>    恢复配置文件
    restore-full <date>      恢复指定日期的全量备份
    verify <file>            验证备份文件完整性

示例:
    $0 list
    $0 restore-db backups/db_20260325_120000.sql.gz
    $0 restore-full 20260325

EOF
}

# 列出备份
list_backups() {
    log_info "可用备份列表:"

    echo -e "\n数据库备份:"
    if ls "$BACKUP_DIR"/db_*.sql.gz 2>/dev/null; then
        ls -lht "$BACKUP_DIR"/db_*.sql.gz | head -10
    else
        echo "无"
    fi

    echo -e "\n上传文件备份:"
    if ls "$BACKUP_DIR"/uploads_*.tar.gz 2>/dev/null; then
        ls -lht "$BACKUP_DIR"/uploads_*.tar.gz | head -5
    else
        echo "无"
    fi

    echo -e "\n配置文件备份:"
    if ls "$BACKUP_DIR"/config_*.tar.gz 2>/dev/null; then
        ls -lht "$BACKUP_DIR"/config_*.tar.gz | head -5
    else
        echo "无"
    fi
}

# 验证备份文件
verify_backup() {
    local backup_file=$1

    if [ ! -f "$backup_file" ]; then
        log_error "备份文件不存在: $backup_file"
        return 1
    fi

    log_info "验证备份: $backup_file"

    # 检查文件大小
    local size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file")
    if [ "$size" -lt 100 ]; then
        log_error "备份文件过小，可能损坏"
        return 1
    fi

    # 检查文件类型
    local mime=$(file -b --mime-type "$backup_file" 2>/dev/null)
    log_info "文件类型: $mime, 大小: $size bytes"

    # 如果是gzip文件，测试解压
    if [[ "$backup_file" == *.gz ]]; then
        if gzip -t "$backup_file" 2>/dev/null; then
            log_info "✓ gzip 文件完整性验证通过"
        else
            log_error "✗ gzip 文件损坏"
            return 1
        fi
    fi

    # 如果是tar文件，测试解压
    if [[ "$backup_file" == *.tar.gz ]]; then
        if tar -tzf "$backup_file" > /dev/null 2>&1; then
            log_info "✓ tar 文件完整性验证通过"
            echo -e "\n备份内容:"
            tar -tzf "$backup_file" | head -20
        else
            log_error "✗ tar 文件损坏"
            return 1
        fi
    fi

    return 0
}

# 恢复数据库
restore_database() {
    local backup_file=$1

    if [ -z "$backup_file" ]; then
        log_error "请指定备份文件"
        return 1
    fi

    # 验证备份
    if ! verify_backup "$backup_file"; then
        return 1
    fi

    log_warn "警告: 这将覆盖当前数据库!"
    read -p "确认继续? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "取消操作"
        return 0
    fi

    log_info "开始恢复数据库..."

    # 停止服务
    cd "$PROJECT_DIR"
    docker-compose stop api

    # 删除旧数据库（可选）
    # docker-compose exec -T postgres dropdb -U zhineng zhineng_kb
    # docker-compose exec -T postgres createdb -U zhineng zhineng_kb

    # 恢复数据
    if [[ "$backup_file" == *.gz ]]; then
        gunzip -c "$backup_file" | docker-compose exec -T postgres psql -U zhineng zhineng_kb
    else
        docker-compose exec -T postgres psql -U zhineng zhineng_kb < "$backup_file"
    fi

    # 重启服务
    docker-compose start api

    log_info "数据库恢复完成"
}

# 恢复上传文件
restore_uploads() {
    local backup_file=$1

    if [ -z "$backup_file" ]; then
        log_error "请指定备份文件"
        return 1
    fi

    if ! verify_backup "$backup_file"; then
        return 1
    fi

    log_info "恢复上传文件..."

    local upload_dir="./data/uploads"
    mkdir -p "$upload_dir"

    # 清空现有文件（可选）
    # rm -rf "$upload_dir"/*

    # 解压备份
    tar -xzf "$backup_file" -C "$upload_dir"

    log_info "上传文件恢复完成"
}

# 恢复配置文件
restore_config() {
    local backup_file=$1

    if [ -z "$backup_file" ]; then
        log_error "请指定备份文件"
        return 1
    fi

    if ! verify_backup "$backup_file"; then
        return 1
    fi

    log_info "恢复配置文件..."

    cd "$PROJECT_DIR"

    # 解压到项目根目录
    tar -xzf "$backup_file"

    log_info "配置文件恢复完成"
    log_warn "请重启服务以应用新配置"
}

# 全量恢复
restore_full() {
    local date_str=$1

    if [ -z "$date_str" ]; then
        log_error "请指定日期 (格式: YYYYMMDD)"
        return 1
    fi

    log_info "开始全量恢复: $date_str"

    # 查找该日期的备份
    local db_backup=$(find "$BACKUP_DIR" -name "db_${date_str}*.sql.gz" | sort -r | head -1)
    local uploads_backup=$(find "$BACKUP_DIR" -name "uploads_${date_str}*.tar.gz" | sort -r | head -1)
    local config_backup=$(find "$BACKUP_DIR" -name "config_${date_str}*.tar.gz" | sort -r | head -1)

    if [ -z "$db_backup" ]; then
        log_error "未找到该日期的数据库备份"
        return 1
    fi

    log_info "将恢复以下备份:"
    echo "  数据库: $db_backup"
    [ -n "$uploads_backup" ] && echo "  上传文件: $uploads_backup"
    [ -n "$config_backup" ] && echo "  配置文件: $config_backup"

    read -p "确认继续? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "取消操作"
        return 0
    fi

    # 停止服务
    cd "$PROJECT_DIR"
    docker-compose stop

    # 恢复
    restore_database "$db_backup"

    if [ -n "$uploads_backup" ]; then
        restore_uploads "$uploads_backup"
    fi

    if [ -n "$config_backup" ]; then
        restore_config "$config_backup"
    fi

    # 启动服务
    docker-compose start

    log_info "全量恢复完成"
}

# 主函数
main() {
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
        verify)
            verify_backup "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
