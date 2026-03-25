#!/bin/bash
# 智能知识系统 - 部署脚本
# P5阶段: 系统集成

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

log_info "智能知识系统部署脚本 (P5阶段)"
log_info "项目目录: $PROJECT_DIR"

# 环境检查
check_env() {
    log_info "检查环境..."

    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi
    log_info "✓ Docker: $(docker --version)"

    # 检查 Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi
    log_info "✓ Docker Compose 已安装"

    # 检查端口占用
    check_port 5436 "PostgreSQL"
    check_port 6381 "Redis"
    check_port 8001 "API"
    check_port 8008 "Web"

    log_info "环境检查完成"
}

check_port() {
    local port=$1
    local service=$2

    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_warn "$service 端口 $port 已被占用"
        read -p "是否继续? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 构建镜像
build_images() {
    log_info "构建 Docker 镜像..."

    docker-compose build

    log_info "镜像构建完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."

    docker-compose up -d

    log_info "等待服务启动..."
    sleep 5

    # 检查服务状态
    docker-compose ps

    log_info "服务启动完成"
}

# 停止服务
stop_services() {
    log_info "停止服务..."

    docker-compose down

    log_info "服务已停止"
}

# 重启服务
restart_services() {
    log_info "重启服务..."

    docker-compose restart

    log_info "服务已重启"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."

    # 检查 API
    if curl -s http://localhost:8001/health | grep -q "ok"; then
        log_info "✓ API 服务正常"
    else
        log_error "✗ API 服务异常"
        return 1
    fi

    # 检查领域系统
    if curl -s http://localhost:8001/api/v1/domains | grep -q "qigong"; then
        log_info "✓ 领域系统正常"
    else
        log_warn "✗ 领域系统可能异常"
    fi

    # 检查监控
    if curl -s http://localhost:8001/api/v1/health | grep -q "healthy"; then
        log_info "✓ 监控系统正常"
    else
        log_warn "✗ 监控系统可能异常"
    fi

    log_info "健康检查完成"
}

# 查看日志
view_logs() {
    local service=${1:-""}

    if [ -n "$service" ]; then
        docker-compose logs -f "$service"
    else
        docker-compose logs -f
    fi
}

# 数据库备份
backup_database() {
    log_info "备份数据库..."

    local backup_dir="$PROJECT_DIR/backups"
    mkdir -p "$backup_dir"

    local backup_file="$backup_dir/db_backup_$(date +%Y%m%d_%H%M%S).sql"

    docker-compose exec -T postgres pg_dump -U zhineng zhineng_kb > "$backup_file"

    log_info "数据库已备份到: $backup_file"
}

# 数据库恢复
restore_database() {
    local backup_file=$1

    if [ -z "$backup_file" ]; then
        log_error "请指定备份文件"
        exit 1
    fi

    if [ ! -f "$backup_file" ]; then
        log_error "备份文件不存在: $backup_file"
        exit 1
    fi

    log_warn "这将覆盖当前数据库，确认继续? (y/n)"
    read -r -n 1
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "恢复数据库..."

        docker-compose exec -T postgres psql -U zhineng zhineng_kb < "$backup_file"

        log_info "数据库已恢复"
    fi
}

# 清理资源
cleanup() {
    log_info "清理未使用的资源..."

    docker-compose down -v --remove-orphans

    log_info "清理完成"
}

# 显示帮助
show_help() {
    cat << EOF
智能知识系统部署脚本

用法: $0 [命令] [选项]

命令:
    check       检查环境
    build       构建 Docker 镜像
    start       启动服务
    stop        停止服务
    restart     重启服务
    status      查看服务状态
    health      执行健康检查
    logs [服务] 查看日志 (指定服务名或全部)
    backup      备份数据库
    restore     恢复数据库
    cleanup     清理资源
    help        显示此帮助

示例:
    $0 check
    $0 start
    $0 logs api
    $0 backup
EOF
}

# 主函数
main() {
    local command=${1:-""}

    case "$command" in
        check)
            check_env
            ;;
        build)
            check_env
            build_images
            ;;
        start)
            check_env
            start_services
            health_check
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            health_check
            ;;
        status)
            docker-compose ps
            ;;
        health)
            health_check
            ;;
        logs)
            view_logs "$2"
            ;;
        backup)
            backup_database
            ;;
        restore)
            restore_database "$2"
            ;;
        cleanup)
            cleanup
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

# 执行主函数
main "$@"
