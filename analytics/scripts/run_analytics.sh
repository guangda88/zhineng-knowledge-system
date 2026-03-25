#!/bin/bash
# -*- coding: utf-8 -*-
# 数据分析主控制脚本
# Analytics Main Controller

set -e

# =============================================================================
# 配置
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ANALYTICS_DIR="${PROJECT_DIR}/analytics"
LOG_DIR="${ANALYTICS_DIR}/logs"
REPORTS_DIR="${ANALYTICS_DIR}/reports"

# 创建日志目录
mkdir -p "${LOG_DIR}"

# =============================================================================
# 日志函数
# =============================================================================

log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_DIR}/analytics.log"
}

log_info() {
    log "INFO" "$@"
}

log_error() {
    log "ERROR" "$@"
}

log_success() {
    log "SUCCESS" "$@"
}

# =============================================================================
# 任务执行函数
# =============================================================================

run_data_generation() {
    log_info "Step 1: Data Generation"
    
    cd "${ANALYTICS_DIR}/scripts"
    python3 data_generator.py
    
    if [ $? -eq 0 ]; then
        log_success "Data generation completed"
    else
        log_error "Data generation failed"
        exit 1
    fi
}

run_data_validation() {
    log_info "Step 2: Data Validation"
    
    cd "${ANALYTICS_DIR}/scripts"
    python3 data_validator.py
    
    if [ $? -eq 0 ]; then
        log_success "Data validation completed"
    else
        log_error "Data validation failed"
        exit 1
    fi
}

run_performance_analysis() {
    log_info "Step 3: Performance Analysis"
    
    cd "${ANALYTICS_DIR}/scripts"
    python3 performance_analyzer.py
    
    if [ $? -eq 0 ]; then
        log_success "Performance analysis completed"
    else
        log_error "Performance analysis failed"
        exit 1
    fi
}

generate_summary_report() {
    log_info "Step 4: Summary Report Generation"
    
    local summary_file="${REPORTS_DIR}/summary_report_$(date '+%Y%m%d_%H%M%S').txt"
    
    cat > "${summary_file}" << 'SUMMARYEOF'
================================================================================
                      数据分析摘要报告
                   Analytics Summary Report
================================================================================

报告时间: $(date '+%Y-%m-%d %H:%M:%S')

================================================================================
                           执行步骤
================================================================================

1. 数据生成（Data Generation）
   - 生成了测试用户、文档、标注、搜索历史等数据
   
2. 数据验证（Data Validation）
   - 验证了数据完整性、准确性、一致性、有效性、唯一性
   
3. 性能分析（Performance Analysis）
   - 分析了查询响应时间、系统健康状况、数据库性能

================================================================================
                           生成的报告
================================================================================

SUMMARYEOF

    # 列出所有报告文件
    echo "Generated reports:" >> "${summary_file}"
    ls -lht "${REPORTS_DIR}"/*.json 2>/dev/null | head -10 >> "${summary_file}" || echo "  No JSON reports found" >> "${summary_file}"
    ls -lht "${REPORTS_DIR}"/*.txt 2>/dev/null | head -10 >> "${summary_file}" || echo "  No TXT reports found" >> "${summary_file}"
    
    echo "" >> "${summary_file}"
    echo "================================================================================" >> "${summary_file}"
    echo "报告生成完毕！" >> "${summary_file}"
    echo "================================================================================" >> "${summary_file}"
    
    log_success "Summary report generated: ${summary_file}"
    
    # 打印报告内容
    cat "${summary_file}"
}

check_prerequisites() {
    log_info "Checking Prerequisites"
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    log_success "Python 3: $(python3 --version)"
    
    # 检查数据库连接
    docker exec tcm-postgres pg_isready -U tcmuser &> /dev/null || {
        log_error "PostgreSQL is not ready"
        exit 1
    }
    log_success "PostgreSQL: Ready"
    
    # 检查Docker容器
    if ! docker ps --format '{{.Names}}' | grep -q "tcm-backend"; then
        log_error "Backend container is not running"
        exit 1
    fi
    log_success "Backend container: Running"
    
    log_success "All prerequisites checked"
}

# =============================================================================
# 主函数
# =============================================================================

main() {
    log_info "=========================================="
    log_info "Starting Analytics Pipeline"
    log_info "=========================================="
    
    # 检查前置条件
    check_prerequisites
    
    # 执行数据生成
    if [ "${SKIP_GENERATION:-false}" != "true" ]; then
        run_data_generation
    else
        log_info "Skipping data generation"
    fi
    
    # 执行数据验证
    if [ "${SKIP_VALIDATION:-false}" != "true" ]; then
        run_data_validation
    else
        log_info "Skipping data validation"
    fi
    
    # 执行性能分析
    if [ "${SKIP_PERFORMANCE:-false}" != "true" ]; then
        run_performance_analysis
    else
        log_info "Skipping performance analysis"
    fi
    
    # 生成摘要报告
    generate_summary_report
    
    log_info "=========================================="
    log_info "Analytics Pipeline Complete!"
    log_info "=========================================="
}

# =============================================================================
# 执行入口
# =============================================================================

# 解析命令行参数
SKIP_GENERATION=false
SKIP_VALIDATION=false
SKIP_PERFORMANCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-generation)
            SKIP_GENERATION=true
            shift
            ;;
        --skip-validation)
            SKIP_VALIDATION=true
            shift
            ;;
        --skip-performance)
            SKIP_PERFORMANCE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-generation   Skip data generation"
            echo "  --skip-validation    Skip data validation"
            echo "  --skip-performance  Skip performance analysis"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# 执行主函数
main "$@"
