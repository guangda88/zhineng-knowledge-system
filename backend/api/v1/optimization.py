"""自优化API路由

LingMinOpt自优化框架的API接口
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from services.optimization import (
    LingMinOptOptimizer,
    FeedbackCollector,
    ErrorAnalyzer,
    SystemAuditor
)
from services.optimization.lingminopt import (
    OptimizationOpportunity,
    OptimizationPriority
)

router = APIRouter(prefix="/optimization", tags=["自优化系统"])


# ==================== 请求/响应模型 ====================

class FeedbackSubmissionRequest(BaseModel):
    """用户反馈提交"""
    user_id: str
    feedback_type: str  # bug, feature, improvement, complaint
    content: str
    rating: Optional[int] = None  # 1-5
    metadata: Optional[dict] = None


class ErrorLogRequest(BaseModel):
    """错误日志提交"""
    error_type: str
    error_message: str
    stack_trace: str
    context: Optional[dict] = None
    severity: str = "error"  # error, warning, critical


class OptimizationExecuteRequest(BaseModel):
    """优化执行请求"""
    opportunity_id: str
    auto_approve: bool = False


# ==================== API端点 ====================

@router.get("/opportunities")
async def list_optimization_opportunities(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 20
) -> dict:
    """
    列出优化机会

    参数：
    - **status**: 状态筛选（identified, planned, in_progress, completed）
    - **priority**: 优先级筛选（critical, high, medium, low）
    - **limit**: 返回数量限制

    返回：优化机会列表
    """
    try:
        optimizer = LingMinOptOptimizer()

        # 识别新的机会
        opportunities = await optimizer.identify_opportunities()

        # 应用过滤
        if status:
            opportunities = [o for o in opportunities if o.status.value == status]
        if priority:
            opportunities = [o for o in opportunities if o.priority.value == priority]

        return {
            "success": True,
            "total": len(opportunities),
            "opportunities": [
                {
                    "id": o.id,
                    "title": o.title,
                    "description": o.description,
                    "source": o.source.value,
                    "priority": o.priority.value,
                    "category": o.category,
                    "status": o.status.value,
                    "impact_estimate": o.impact_estimate,
                    "effort_estimate": o.effort_estimate,
                    "created_at": o.created_at.isoformat()
                }
                for o in opportunities[:limit]
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/opportunities/{opportunity_id}/analyze")
async def analyze_opportunity(
    opportunity_id: str
) -> dict:
    """
    分析优化机会

    深入分析优化机会，制定详细计划
    """
    try:
        optimizer = LingMinOptOptimizer()

        # 查找机会
        opportunity = None
        for opp in optimizer.opportunities:
            if opp.id == opportunity_id:
                opportunity = opp
                break

        if not opportunity:
            raise HTTPException(status_code=404, detail="优化机会不存在")

        # 执行分析
        analyzed = await optimizer.analyze_opportunity(opportunity)

        # 生成计划
        plan = await optimizer.plan_optimization(analyzed)

        return {
            "success": True,
            "opportunity": {
                "id": analyzed.id,
                "title": analyzed.title,
                "status": analyzed.status.value,
                "solution": analyzed.solution,
                "impact_estimate": analyzed.impact_estimate,
                "effort_estimate": analyzed.effort_estimate
            },
            "plan": plan
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/opportunities/{opportunity_id}/execute")
async def execute_optimization(
    opportunity_id: str,
    request: OptimizationExecuteRequest,
    background_tasks: BackgroundTasks
) -> dict:
    """
    执行优化

    按照计划执行优化操作

    参数：
    - **opportunity_id**: 优化机会ID
    - **auto_approve**: 是否自动批准（跳过人工确认）
    """
    try:
        optimizer = LingMinOptOptimizer()

        # 查找机会
        opportunity = None
        for opp in optimizer.opportunities:
            if opp.id == opportunity_id:
                opportunity = opp
                break

        if not opportunity:
            raise HTTPException(status_code=404, detail="优化机会不存在")

        # 检查是否需要人工确认
        if not request.auto_approve and opportunity.priority == OptimizationPriority.CRITICAL:
            return {
                "success": False,
                "message": "关键优化需要人工确认",
                "requires_approval": True
            }

        # 在后台执行优化
        async def run_optimization():
            return await optimizer.execute_optimization(
                opportunity,
                auto_approve=request.auto_approve
            )

        background_tasks.add_task(run_optimization)

        return {
            "success": True,
            "message": f"优化任务已启动: {opportunity.title}",
            "opportunity_id": opportunity_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackSubmissionRequest
) -> dict:
    """
    提交用户反馈

    参数：
    - **user_id**: 用户ID
    - **feedback_type**: 反馈类型（bug, feature, improvement, complaint）
    - **content**: 反馈内容
    - **rating**: 评分（1-5）
    - **metadata**: 额外元数据
    """
    try:
        collector = FeedbackCollector()

        feedback_id = await collector.collect_feedback(
            user_id=request.user_id,
            feedback_type=request.feedback_type,
            content=request.content,
            rating=request.rating,
            metadata=request.metadata
        )

        return {
            "success": True,
            "feedback_id": feedback_id,
            "message": "反馈已提交，感谢您的反馈！"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback/analysis")
async def get_feedback_analysis() -> dict:
    """
    获取反馈分析

    返回用户反馈的统计分析
    """
    try:
        collector = FeedbackCollector()

        analysis = await collector.analyze_feedback()

        return {
            "success": True,
            "analysis": analysis
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/errors/log")
async def log_system_error(
    request: ErrorLogRequest
) -> dict:
    """
    记录系统错误

    参数：
    - **error_type**: 错误类型
    - **error_message**: 错误消息
    - **stack_trace**: 堆栈跟踪
    - **context**: 上下文信息
    - **severity**: 严重程度
    """
    try:
        analyzer = ErrorAnalyzer()

        error_id = await analyzer.log_error(
            error_type=request.error_type,
            error_message=request.error_message,
            stack_trace=request.stack_trace,
            context=request.context,
            severity=request.severity
        )

        return {
            "success": True,
            "error_id": error_id,
            "message": "错误已记录"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/errors/analysis")
async def get_error_analysis() -> dict:
    """
    获取错误分析

    返回系统错误的统计分析
    """
    try:
        analyzer = ErrorAnalyzer()

        analysis = await analyzer.analyze_errors()

        return {
            "success": True,
            "analysis": analysis
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audit/perform")
async def perform_audit(
    audit_type: str = "comprehensive",
    background_tasks: BackgroundTasks
) -> dict:
    """
    执行系统审计

    参数：
    - **audit_type**: 审计类型（comprehensive, security, performance, code_quality）
    """
    try:
        auditor = SystemAuditor()

        # 在后台执行审计
        async def run_audit():
            return await auditor.perform_audit(audit_type)

        background_tasks.add_task(run_audit)

        return {
            "success": True,
            "message": f"审计任务已启动: {audit_type}",
            "audit_type": audit_type
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/history")
async def get_audit_history(
    limit: int = 10
) -> dict:
    """
    获取审计历史

    返回最近的审计记录
    """
    try:
        auditor = SystemAuditor()

        history = auditor.audit_history[-limit:]

        return {
            "success": True,
            "total": len(history),
            "audits": history
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_optimization_stats() -> dict:
    """
    获取自优化系统统计

    返回整体统计信息
    """
    try:
        optimizer = LingMinOptOptimizer()
        collector = FeedbackCollector()
        analyzer = ErrorAnalyzer()
        auditor = SystemAuditor()

        # 并行收集统计
        import asyncio
        feedback_analysis, error_analysis = await asyncio.gather(
            collector.analyze_feedback(),
            analyzer.analyze_errors()
        )

        return {
            "success": True,
            "statistics": {
                "total_opportunities": len(optimizer.opportunities),
                "completed_optimizations": len(optimizer.optimization_history),
                "feedback": feedback_analysis,
                "errors": error_analysis,
                "audits": len(auditor.audit_history)
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
async def get_optimization_dashboard() -> dict:
    """
    获取自优化仪表盘

    返回可视化的优化状态和趋势
    """
    try:
        optimizer = LingMinOptOptimizer()

        # 获取优化机会分布
        all_opportunities = await optimizer.identify_opportunities()

        by_priority = {}
        by_category = {}
        by_status = {}

        for opp in all_opportunities:
            # 按优先级
            p = opp.priority.value
            by_priority[p] = by_priority.get(p, 0) + 1

            # 按类别
            c = opp.category
            by_category[c] = by_category.get(c, 0) + 1

            # 按状态
            s = opp.status.value
            by_status[s] = by_status.get(s, 0) + 1

        return {
            "success": True,
            "dashboard": {
                "total_opportunities": len(all_opportunities),
                "by_priority": by_priority,
                "by_category": by_category,
                "by_status": by_status,
                "recent_optimizations": optimizer.optimization_history[-5:],
                "active_optimizations": len(optimizer.active_optimizations)
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
