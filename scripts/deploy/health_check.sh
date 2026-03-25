#!/bin/bash
# ==============================================================================
# 智能知识系统 - 部署健康检查脚本
# ==============================================================================
# 功能：
#   - 服务状态检查
#   - 容器健康检查
#   - 数据库连接检查
#   - API端点检查
#   - 资源使用检查
#   - 日志分析
#
# 用法:
#   ./health_check.sh                    # 执行完整健康检查
#   ./health_check.sh quick              # 快速检查
#   ./health_check.sh containers         # 检查容器状态
#   ./health_check.sh database           # 检查数据库
#   ./health_check.sh api                # 检查API服务
#   ./health_check.sh resources          # 检查资源使用
#   ./health_check.sh logs               # 检查日志错误
#   ./health_check.sh watch              # 持续监控模式
#
# 环境变量:
#   API_URL              - API地址 (默认: http://localhost:8001)
#   FRONTEND_URL         - 前端地址 (默认: http://localhost:8008)
#   CHECK_TIMEOUT        - 请求超时时间 (默认: 5秒)
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

# 服务配置
API_URL="${API_URL:-http://localhost:8001}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:8008}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"

# 数据库配置
DB_CONTAINER="${DB_CONTAINER:-zhineng-postgres}"
DB_NAME="${DB_NAME:-zhineng_kb}"
DB_USER="${DB_USER:-zhineng}"

# Redis配置
REDIS_CONTAINER="${REDIS_CONTAINER:-zhineng-redis}"
REDIS_PASSWORD="${REDIS_PASSWORD:-redis123}"

# 检查配置
CHECK_TIMEOUT=${CHECK_TIMEOUT:-5}
WATCH_INTERVAL=${WATCH_INTERVAL:-30}

# 状态变量
EXIT_CODE=0
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

# ==============================================================================
# 输出函数
# ==============================================================================

# 输出标题
print_header() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  智能知识系统 - 健康检查${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo -e "检查时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
}

# 输出通过
print_pass() {
    echo -e "${GREEN}✓ PASS${NC} - $*"
    ((CHECKS_PASSED++))
}

# 输出失败
print_fail() {
    echo -e "${RED}✗ FAIL${NC} - $*"
    ((CHECKS_FAILED++))
    EXIT_CODE=1
}

# 输出警告
print_warn() {
    echo -e "${YELLOW}⚠ WARN${NC} - $*"
    ((CHECKS_WARNING++))
}

# 输出信息
print_info() {
    echo -e "${BLUE}ℹ INFO${NC} - $*"
}

# 输出部分标题
print_section() {
    echo ""
    echo -e "${CYAN}--- $* ---${NC}"
}

# ==============================================================================
# 容器检查
# ==============================================================================

check_containers() {
    print_section "容器状态检查"

    cd "$PROJECT_DIR"

    # 获取所有容器
    local containers=$(docker-compose ps -q 2>/dev/null)

    if [[ -z "$containers" ]]; then
        print_fail "没有运行的容器"
        return 1
    fi

    # 检查每个容器
    echo "$containers" | while read -r container_id; do
        local name=$(docker inspect "$container_id" --format='{{.Name}}' | sed 's/\///')
        local status=$(docker inspect "$container_id" --format='{{.State.Status}}')
        local health=$(docker inspect "$container_id" --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")
        local restarts=$(docker inspect "$container_id" --format='{{.RestartCount}}')

        if [[ "$status" == "running" ]]; then
            if [[ "$health" == "healthy" ]] || [[ "$health" == "none" ]]; then
                print_pass "$name - 运行中 (重启次数: $restarts)"
            else
                print_warn "$name - 运行中但健康检查: $health"
            fi
        else
            print_fail "$name - 状态: $status"
        fi

        # 检查重启次数
        if [[ "$restarts" -gt 5 ]]; then
            print_warn "$name - 重启次数过多: $restarts"
        fi
    done
}

# ==============================================================================
# 数据库检查
# ==============================================================================

check_database() {
    print_section "数据库检查"

    # 检查容器运行
    if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
        print_fail "数据库容器未运行"
        return 1
    fi

    # 检查数据库连接
    if docker-compose exec -T postgres pg_isready -U "$DB_USER" "$DB_NAME" > /dev/null 2>&1; then
        print_pass "数据库连接正常"
    else
        print_fail "数据库连接失败"
        return 1
    fi

    # 检查数据库大小
    local db_size=$(docker-compose exec -T postgres psql -U "$DB_USER" "$DB_NAME" -t -c "
        SELECT pg_size_pretty(pg_database_size('$DB_NAME'));
    " 2>/dev/null | tr -d ' ')

    if [[ -n "$db_size" ]]; then
        print_info "数据库大小: $db_size"
    fi

    # 检查表数量
    local table_count=$(docker-compose exec -T postgres psql -U "$DB_USER" "$DB_NAME" -t -c "
        SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';
    " 2>/dev/null | tr -d ' ')

    if [[ -n "$table_count" ]]; then
        print_info "数据表数量: $table_count"
    fi

    # 检查活跃连接数
    local connections=$(docker-compose exec -T postgres psql -U "$DB_USER" "$DB_NAME" -t -c "
        SELECT count(*) FROM pg_stat_activity WHERE state = 'active';
    " 2>/dev/null | tr -d ' ')

    if [[ -n "$connections" ]]; then
        if [[ "$connections" -lt 50 ]]; then
            print_pass "活跃连接数: $connections"
        else
            print_warn "活跃连接数较高: $connections"
        fi
    fi

    # 检查慢查询
    local slow_queries=$(docker-compose exec -T postgres psql -U "$DB_USER" "$DB_NAME" -t -c "
        SELECT COUNT(*) FROM pg_stat_statements WHERE mean_exec_time > 1000;
    " 2>/dev/null | tr -d ' ' || echo "0")

    if [[ "$slow_queries" -gt 0 ]]; then
        print_warn "检测到 $slow_queries 个慢查询"
    fi
}

# ==============================================================================
# Redis检查
# ==============================================================================

check_redis() {
    print_section "Redis检查"

    # 检查容器运行
    if ! docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
        print_fail "Redis容器未运行"
        return 1
    fi

    # 检查Redis连接
    if docker-compose exec -T redis redis-cli -a "$REDIS_PASSWORD" ping > /dev/null 2>&1; then
        print_pass "Redis连接正常"
    else
        print_fail "Redis连接失败"
        return 1
    fi

    # 获取Redis信息
    local redis_info=$(docker-compose exec -T redis redis-cli -a "$REDIS_PASSWORD" INFO 2>/dev/null)

    # 检查内存使用
    local used_memory=$(echo "$redis_info" | grep "^used_memory_human:" | cut -d: -f2 | tr -d '\r')
    print_info "Redis内存使用: $used_memory"

    # 检查连接数
    local connected_clients=$(echo "$redis_info" | grep "^connected_clients:" | cut -d: -f2 | tr -d '\r')
    print_info "Redis连接数: $connected_clients"

    # 检查命中率
    local keyspace_hits=$(echo "$redis_info" | grep "^keyspace_hits:" | cut -d: -f2 | tr -d '\r')
    local keyspace_misses=$(echo "$redis_info" | grep "^keyspace_misses:" | cut -d: -f2 | tr -d '\r')

    if [[ -n "$keyspace_hits" ]] && [[ "$keyspace_hits" -gt 0 ]]; then
        local hit_rate=$(echo "scale=2; $keyspace_hits / ($keyspace_hits + $keyspace_misses) * 100" | bc 2>/dev/null || echo "N/A")
        print_info "Redis命中率: ${hit_rate}%"
    fi
}

# ==============================================================================
# API检查
# ==============================================================================

check_api() {
    print_section "API服务检查"

    if ! command -v curl &> /dev/null; then
        print_warn "curl未安装，跳过API检查"
        return 0
    fi

    # 健康检查端点
    local health_url="${API_URL}/health"
    local response=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$CHECK_TIMEOUT" "$health_url" 2>/dev/null || echo "000")

    if [[ "$response" == "200" ]]; then
        print_pass "API健康检查端点正常"
    else
        print_fail "API健康检查端点返回: $response"
    fi

    # 检查响应时间
    local response_time=$(curl -o /dev/null -s -w "%{time_total}" --max-time "$CHECK_TIMEOUT" "$health_url" 2>/dev/null || echo "0")

    if [[ -n "$response_time" ]]; then
        local time_ms=$(echo "$response_time * 1000" | bc 2>/dev/null || echo "$response_time")
        if [[ "$(echo "$response_time < 1" | bc 2>/dev/null)" == "1" ]]; then
            print_pass "API响应时间: ${time_ms}ms"
        else
            print_warn "API响应时间较慢: ${time_ms}ms"
        fi
    fi

    # 检查主要端点
    local endpoints=(
        "${API_URL}/api/v1/categories"
        "${API_URL}/api/v1/domains"
    )

    for endpoint in "${endpoints[@]}"; do
        local ep_response=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$CHECK_TIMEOUT" "$endpoint" 2>/dev/null || echo "000")
        local ep_name=$(echo "$endpoint" | sed 's|.*api/v1/||')

        if [[ "$ep_response" == "200" ]] || [[ "$ep_response" == "404" ]]; then
            print_pass "API端点 /$ep_name 可访问"
        else
            print_warn "API端点 /$ep_name 返回: $ep_response"
        fi
    done
}

# ==============================================================================
# 前端检查
# ==============================================================================

check_frontend() {
    print_section "前端服务检查"

    if ! command -v curl &> /dev/null; then
        print_warn "curl未安装，跳过前端检查"
        return 0
    fi

    local response=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$CHECK_TIMEOUT" "$FRONTEND_URL" 2>/dev/null || echo "000")

    if [[ "$response" == "200" ]]; then
        print_pass "前端服务正常"
    else
        print_fail "前端服务返回: $response"
    fi
}

# ==============================================================================
# 监控服务检查
# ==============================================================================

check_monitoring() {
    print_section "监控服务检查"

    if ! command -v curl &> /dev/null; then
        print_warn "curl未安装，跳过监控检查"
        return 0
    fi

    # Prometheus
    local prometheus_response=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$CHECK_TIMEOUT" "$PROMETHEUS_URL" 2>/dev/null || echo "000")
    if [[ "$prometheus_response" == "200" ]]; then
        print_pass "Prometheus服务正常"
    else
        print_warn "Prometheus服务返回: $prometheus_response"
    fi

    # Grafana
    local grafana_response=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$CHECK_TIMEOUT" "$GRAFANA_URL" 2>/dev/null || echo "000")
    if [[ "$grafana_response" == "200" ]]; then
        print_pass "Grafana服务正常"
    else
        print_warn "Grafana服务返回: $grafana_response"
    fi
}

# ==============================================================================
# 资源检查
# ==============================================================================

check_resources() {
    print_section "资源使用检查"

    # Docker资源使用
    print_info "容器资源使用:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null || print_warn "无法获取容器统计信息"

    # 磁盘使用
    echo ""
    print_info "磁盘使用情况:"
    df -h "$PROJECT_DIR" | tail -1 | while read -r line; do
        local usage=$(echo "$line" | awk '{print $5}' | sed 's/%//')
        if [[ "$usage" -lt 70 ]]; then
            print_pass "项目目录: $line"
        elif [[ "$usage" -lt 85 ]]; then
            print_warn "项目目录: $line (使用率较高)"
        else
            print_fail "项目目录: $line (使用率过高)"
        fi
    done

    # 内存使用
    local mem_total=$(free -h | awk '/^Mem:/ {print $2}')
    local mem_used=$(free -h | awk '/^Mem:/ {print $3}')
    local mem_percent=$(free | awk '/^Mem:/ {printf "%.0f", $3/$2 * 100}')

    print_info "系统内存: $mem_used / $mem_total (${mem_percent}%)"

    if [[ "$mem_percent" -lt 70 ]]; then
        print_pass "内存使用正常"
    elif [[ "$mem_percent" -lt 85 ]]; then
        print_warn "内存使用率较高"
    else
        print_fail "内存使用率过高"
    fi

    # CPU负载
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    local cpu_count=$(nproc)
    local load_ratio=$(echo "$load_avg / $cpu_count" | bc -l 2>/dev/null || echo "1")

    print_info "CPU负载: $load_avg (核心数: $cpu_count)"

    if [[ "$(echo "$load_ratio < 1" | bc 2>/dev/null)" == "1" ]]; then
        print_pass "CPU负载正常"
    elif [[ "$(echo "$load_ratio < 2" | bc 2>/dev/null)" == "1" ]]; then
        print_warn "CPU负载较高"
    else
        print_fail "CPU负载过高"
    fi
}

# ==============================================================================
# 日志检查
# ==============================================================================

check_logs() {
    print_section "日志错误检查"

    cd "$PROJECT_DIR"

    # 检查最近5分钟的日志
    local since_time="5m"

    # 检查错误日志
    local error_count=$(docker-compose logs --since "$since_time" 2>&1 | grep -i "error\|exception\|failed" | wc -l)

    if [[ "$error_count" -eq 0 ]]; then
        print_pass "未检测到错误日志"
    elif [[ "$error_count" -lt 10 ]]; then
        print_warn "检测到 $error_count 条错误日志"
    else
        print_fail "检测到 $error_count 条错误日志"
    fi

    # 显示最近的错误
    if [[ "$error_count" -gt 0 ]]; then
        print_info "最近的错误:"
        docker-compose logs --since "$since_time" 2>&1 | grep -i "error\|exception\|failed" | tail -5 | sed 's/^/  /'
    fi
}

# ==============================================================================
# 网络检查
# ==============================================================================

check_network() {
    print_section "网络检查"

    # 检查Docker网络
    local network_exists=$(docker network ls --format '{{.Name}}' | grep -c "zhineng-network" || echo "0")

    if [[ "$network_exists" -gt 0 ]]; then
        print_pass "Docker网络存在"
    else
        print_warn "Docker网络不存在"
    fi

    # 检查端口监听
    local ports=(8001 8008 5436 6381 9090 3000)
    local listening=0

    for port in "${ports[@]}"; do
        if ss -tuln | grep -q ":$port "; then
            ((listening++))
        fi
    done

    print_info "端口监听: $listening / ${#ports[@]}"

    if [[ "$listening" -eq "${#ports[@]}" ]]; then
        print_pass "所有服务端口正常监听"
    else
        print_warn "部分服务端口未监听"
    fi
}

# ==============================================================================
# 完整检查
# ==============================================================================

full_check() {
    print_header

    check_containers
    check_database
    check_redis
    check_api
    check_frontend
    check_monitoring
    check_resources
    check_network

    # 输出总结
    print_summary
}

# 快速检查
quick_check() {
    print_header

    check_containers
    check_database
    check_api

    print_summary
}

# 持续监控
watch_mode() {
    print_info "持续监控模式 (每 ${WATCH_INTERVAL} 秒检查一次)"
    print_info "按 Ctrl+C 退出"

    local iteration=0
    while true; do
        clear
        print_header
        echo -e "第 $((iteration + 1)) 次检查\n"

        check_containers
        check_database
        check_api

        print_summary

        ((iteration++))
        sleep "$WATCH_INTERVAL"
    done
}

# 输出总结
print_summary() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  检查总结${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo -e "${GREEN}通过: $CHECKS_PASSED${NC}"
    echo -e "${YELLOW}警告: $CHECKS_WARNING${NC}"
    echo -e "${RED}失败: $CHECKS_FAILED${NC}"
    echo ""

    if [[ $EXIT_CODE -eq 0 ]]; then
        echo -e "${GREEN}✓ 系统健康状态良好${NC}"
    else
        echo -e "${RED}✗ 系统存在问题，请检查失败的项${NC}"
    fi

    echo ""
}

# ==============================================================================
# 帮助
# ==============================================================================

show_help() {
    cat << EOF
智能知识系统 - 部署健康检查脚本

用法: $0 [命令]

命令:
    (无参数)               执行完整健康检查（默认）
    quick                  快速检查
    containers             检查容器状态
    database               检查数据库
    redis                  检查Redis
    api                    检查API服务
    frontend               检查前端服务
    monitoring             检查监控服务
    resources              检查资源使用
    logs                   检查日志错误
    network                检查网络状态
    watch                  持续监控模式
    help                   显示此帮助信息

环境变量:
    API_URL              API地址 (默认: http://localhost:8001)
    FRONTEND_URL         前端地址 (默认: http://localhost:8008)
    CHECK_TIMEOUT        请求超时时间 (默认: 5秒)
    WATCH_INTERVAL       监控间隔秒数 (默认: 30秒)

示例:
    $0              # 完整健康检查
    $0 quick        # 快速检查
    $0 api          # 仅检查API服务
    $0 watch        # 持续监控模式

退出码:
    0 - 所有检查通过
    1 - 有检查失败

EOF
}

# ==============================================================================
# 主函数
# ==============================================================================

main() {
    local command=${1:-full}

    case "$command" in
        full|all|"")
            full_check
            ;;
        quick|q)
            quick_check
            ;;
        containers|ct)
            print_header
            check_containers
            print_summary
            ;;
        database|db)
            print_header
            check_database
            print_summary
            ;;
        redis)
            print_header
            check_redis
            print_summary
            ;;
        api)
            print_header
            check_api
            print_summary
            ;;
        frontend|fe)
            print_header
            check_frontend
            print_summary
            ;;
        monitoring|mon)
            print_header
            check_monitoring
            print_summary
            ;;
        resources|res)
            print_header
            check_resources
            print_summary
            ;;
        logs)
            print_header
            check_logs
            print_summary
            ;;
        network|net)
            print_header
            check_network
            print_summary
            ;;
        watch)
            watch_mode
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo "未知命令: $command"
            show_help
            exit 1
            ;;
    esac

    exit $EXIT_CODE
}

# 执行主函数
main "$@"
