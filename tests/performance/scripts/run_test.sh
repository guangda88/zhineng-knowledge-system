#!/bin/bash
#
# 性能测试运行脚本
#
# 用法:
#   ./scripts/run_test.sh                    # 默认配置测试
#   ./scripts/run_test.sh --quick            # 快速测试
#   ./scripts/run_test.sh --full             # 完整测试
#   ./scripts/run_test.sh --endpoint search  # 单端点测试
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
PROJECT_ROOT="/home/ai/zhineng-knowledge-system"
LOCUSTFILE="$PROJECT_ROOT/tests/performance/locustfile.py"
REPORT_DIR="$PROJECT_ROOT/tests/performance/reports"
HOST="${TARGET_HOST:-http://localhost:8000}"

# 创建报告目录
mkdir -p "$REPORT_DIR"

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

# 检查服务是否可用
check_service() {
    log_info "检查服务可用性: $HOST"

    if curl -s -f "$HOST/health" > /dev/null 2>&1; then
        log_info "服务运行正常"
        return 0
    else
        log_error "服务不可用，请先启动服务"
        log_info "启动命令: cd backend && python main.py"
        return 1
    fi
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."

    if ! command -v locust &> /dev/null; then
        log_error "locust 未安装"
        log_info "安装命令: pip install -r $PROJECT_ROOT/tests/performance/requirements.txt"
        return 1
    fi

    log_info "依赖检查完成"
}

# 快速测试
run_quick_test() {
    log_info "开始快速测试..."

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    REPORT_PREFIX="$REPORT_DIR/quick_$TIMESTAMP"

    locust -f "$LOCUSTFILE" \
        --headless \
        --host="$HOST" \
        --users=10 \
        --spawn-rate=2 \
        --run-time=30s \
        --html="$REPORT_PREFIX.html" \
        --csv="$REPORT_PREFIX"

    log_info "快速测试完成，报告: $REPORT_PREFIX.html"
}

# 标准测试
run_standard_test() {
    log_info "开始标准测试..."

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    REPORT_PREFIX="$REPORT_DIR/standard_$TIMESTAMP"

    locust -f "$LOCUSTFILE" \
        --headless \
        --host="$HOST" \
        --users=50 \
        --spawn-rate=5 \
        --run-time=1m \
        --html="$REPORT_PREFIX.html" \
        --csv="$REPORT_PREFIX"

    log_info "标准测试完成，报告: $REPORT_PREFIX.html"
}

# 峰值测试
run_peak_test() {
    log_info "开始峰值测试..."

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    REPORT_PREFIX="$REPORT_DIR/peak_$TIMESTAMP"

    locust -f "$LOCUSTFILE" \
        --headless \
        --host="$HOST" \
        --users=100 \
        --spawn-rate=10 \
        --run-time=2m \
        --html="$REPORT_PREFIX.html" \
        --csv="$REPORT_PREFIX"

    log_info "峰值测试完成，报告: $REPORT_PREFIX.html"
}

# 压力测试
run_stress_test() {
    log_info "开始压力测试..."

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    REPORT_PREFIX="$REPORT_DIR/stress_$TIMESTAMP"

    locust -f "$LOCUSTFILE" \
        --headless \
        --host="$HOST" \
        --users=200 \
        --spawn-rate=20 \
        --run-time=5m \
        --html="$REPORT_PREFIX.html" \
        --csv="$REPORT_PREFIX"

    log_info "压力测试完成，报告: $REPORT_PREFIX.html"
}

# 耐久测试
run_endurance_test() {
    log_info "开始耐久测试 (30分钟)..."

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    REPORT_PREFIX="$REPORT_DIR/endurance_$TIMESTAMP"

    locust -f "$LOCUSTFILE" \
        --headless \
        --host="$HOST" \
        --users=50 \
        --spawn-rate=5 \
        --run-time=30m \
        --html="$REPORT_PREFIX.html" \
        --csv="$REPORT_PREFIX"

    log_info "耐久测试完成，报告: $REPORT_PREFIX.html"
}

# 单端点测试
run_endpoint_test() {
    local endpoint=$1

    log_info "开始端点测试: $endpoint"

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    REPORT_PREFIX="$REPORT_DIR/${endpoint}_$TIMESTAMP"

    case "$endpoint" in
        search)
            USER_CLASS="SearchEndpointTest"
            ;;
        ask)
            USER_CLASS="AskEndpointTest"
            ;;
        hybrid)
            USER_CLASS="HybridSearchEndpointTest"
            ;;
        documents)
            USER_CLASS="DocumentsEndpointTest"
            ;;
        *)
            log_error "未知端点: $endpoint"
            log_info "支持的端点: search, ask, hybrid, documents"
            return 1
            ;;
    esac

    locust -f "$LOCUSTFILE" \
        --headless \
        --user-class="$USER_CLASS" \
        --host="$HOST" \
        --users=100 \
        --spawn-rate=10 \
        --run-time=1m \
        --html="$REPORT_PREFIX.html" \
        --csv="$REPORT_PREFIX"

    log_info "$endpoint 端点测试完成，报告: $REPORT_PREFIX.html"
}

# 完整测试套件
run_full_test_suite() {
    log_info "开始完整测试套件..."

    log_info "=========================================="
    log_info "完整测试套件包含以下测试:"
    log_info "1. 快速测试 (验证服务可用性)"
    log_info "2. 标准测试 (常规负载)"
    log_info "3. 峰值测试 (目标负载)"
    log_info "4. 端点专项测试 (所有端点)"
    log_info "=========================================="

    # 快速测试
    run_quick_test

    # 等待服务恢复
    sleep 5

    # 标准测试
    run_standard_test

    # 等待服务恢复
    sleep 5

    # 峰值测试
    run_peak_test

    # 等待服务恢复
    sleep 5

    # 各端点专项测试
    for endpoint in search ask hybrid documents; do
        run_endpoint_test "$endpoint"
        sleep 5
    done

    log_info "完整测试套件完成！"
    log_info "报告目录: $REPORT_DIR"
}

# 解析参数
TEST_TYPE="standard"

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            TEST_TYPE="quick"
            shift
            ;;
        --standard)
            TEST_TYPE="standard"
            shift
            ;;
        --peak)
            TEST_TYPE="peak"
            shift
            ;;
        --stress)
            TEST_TYPE="stress"
            shift
            ;;
        --endurance)
            TEST_TYPE="endurance"
            shift
            ;;
        --full)
            TEST_TYPE="full"
            shift
            ;;
        --endpoint)
            TEST_TYPE="endpoint"
            ENDPOINT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --web)
            TEST_TYPE="web"
            shift
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --quick       快速测试 (10用户, 30秒)"
            echo "  --standard    标准测试 (50用户, 1分钟) [默认]"
            echo "  --peak        峰值测试 (100用户, 2分钟)"
            echo "  --stress      压力测试 (200用户, 5分钟)"
            echo "  --endurance   耐久测试 (50用户, 30分钟)"
            echo "  --full        完整测试套件"
            echo "  --endpoint E  单端点测试 (E: search|ask|hybrid|documents)"
            echo "  --host H      指定目标主机 (默认: $HOST)"
            echo "  --web         启动 Web UI 模式"
            echo "  -h, --help    显示帮助"
            exit 0
            ;;
        *)
            log_error "未知选项: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 主流程
main() {
    log_info "=========================================="
    log_info "智能知识系统 - 性能测试"
    log_info "=========================================="
    log_info "目标主机: $HOST"
    log_info "测试类型: $TEST_TYPE"
    log_info "报告目录: $REPORT_DIR"
    log_info "=========================================="

    # 检查依赖
    check_dependencies || exit 1

    # 检查服务
    check_service || exit 1

    # 运行测试
    case "$TEST_TYPE" in
        quick)
            run_quick_test
            ;;
        standard)
            run_standard_test
            ;;
        peak)
            run_peak_test
            ;;
        stress)
            run_stress_test
            ;;
        endurance)
            run_endurance_test
            ;;
        full)
            run_full_test_suite
            ;;
        endpoint)
            if [ -z "$ENDPOINT" ]; then
                log_error "--endpoint 需要指定端点名称"
                exit 1
            fi
            run_endpoint_test "$ENDPOINT"
            ;;
        web)
            log_info "启动 Web UI 模式..."
            locust -f "$LOCUSTFILE" --host="$HOST"
            ;;
    esac

    log_info "=========================================="
    log_info "测试完成！"
    log_info "=========================================="
}

main
