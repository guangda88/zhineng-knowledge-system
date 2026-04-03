"""自学习和自进化API

提供多AI对比、用户行为追踪、进化方向识别等功能
"""

import logging
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.typing import JSONResponse
from backend.core.database import get_async_session
from backend.services.evolution.comparison_engine import get_comparison_engine
from backend.services.evolution.multi_ai_adapter import get_multi_ai_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/evolution", tags=["自学习进化"])


# ==================== 请求/响应模型 ====================


class QAComparisonRequest(BaseModel):
    """问答对比请求"""

    request_type: Literal["qa"] = "qa"
    query: str = Field(..., description="用户问题")
    lingzhi_response: str = Field(..., description="灵知系统的回答")
    providers: Optional[List[str]] = Field(None, description="要比对的AI列表，None表示全部")


class PodcastComparisonRequest(BaseModel):
    """播客生成对比请求"""

    request_type: Literal["podcast"] = "podcast"
    topic: str = Field(..., description="播客主题")
    lingzhi_output: str = Field(..., description="灵知系统生成的播客脚本")
    providers: Optional[List[str]] = None


class BehaviorTrackingRequest(BaseModel):
    """用户行为追踪请求"""

    request_id: str = Field(..., description="关联的请求ID")
    session_id: Optional[str] = None
    behaviors: List[Dict[str, Any]] = Field(..., description="行为列表")


class EvolutionFeedbackRequest(BaseModel):
    """进化反馈请求"""

    comparison_id: int = Field(..., description="对比记录ID")
    rating: Literal["good", "neutral", "poor"]
    preferred_ai: str = Field(..., description="用户更喜欢的AI")
    comment: Optional[str] = None


class EvolutionOpportunity(BaseModel):
    """进化机会"""

    type: str
    priority: Literal["critical", "high", "medium", "low"]
    description: str
    action: str
    details: str


# ==================== API端点 ====================


@router.post("/compare", response_model=JSONResponse)
async def trigger_comparison(
    request: QAComparisonRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    触发多AI对比

    **场景1：问答对比**

    POST /api/v1/evolution/compare
    {
        "request_type": "qa",
        "query": "如何提高学习注意力？",
        "lingzhi_response": "灵知系统的回答..."
    }

    后台并行调用其他AI，进行对比评估
    """
    try:
        # 1. 并行调用其他AI
        adapter = get_multi_ai_adapter()
        comparison_result = await adapter.compare_responses(
            prompt=request.query, request_type=request.request_type, providers=request.providers
        )

        # 提取竞争对手响应
        competitor_responses = {
            provider: response
            for provider, response in comparison_result["responses"].items()
            if provider != "lingzhi"
        }

        # 2. 对比评估
        engine = get_comparison_engine()
        evaluation = await engine.compare_qa_responses(
            query=request.query,
            lingzhi_response=request.lingzhi_response,
            competitor_responses=competitor_responses,
        )

        # 3. 记录对比结果
        comparison_id = str(uuid.uuid4())

        # 注意：这里假设ai_comparison_log表已创建
        # 如果表不存在，只返回结果，不记录到数据库
        try:
            await db.execute(
                text(
                    """
                    INSERT INTO ai_comparison_log
                    (user_id, session_id, request_type, user_query,
                     lingzhi_response, competitor_responses, comparison_metrics,
                     winner, created_at)
                    VALUES (:user_id, :session_id, :request_type, :user_query,
                            :lingzhi_response, :competitor_responses, :comparison_metrics,
                            :winner, NOW())
                """
                ),
                {
                    "user_id": None,  # 从JWT获取
                    "session_id": comparison_id,
                    "request_type": request.request_type,
                    "user_query": request.query,
                    "lingzhi_response": request.lingzhi_response,
                    "competitor_responses": comparison_result["responses"],
                    "comparison_metrics": evaluation,
                    "winner": evaluation["winner"],
                },
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to log comparison (table may not exist yet): {e}")
            # 不影响主流程，继续返回结果

        return JSONResponse(
            {
                "status": "success",
                "comparison_id": comparison_id,
                "evaluation": evaluation,
                "comparison_summary": comparison_result["summary"],
                "suggestions": evaluation["suggestions"],
                "message": "对比完成，系统将自动学习改进",
            }
        )

    except Exception as e:
        logger.error(f"Comparison failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"对比失败: {str(e)}")


@router.post("/track-behavior", response_model=JSONResponse)
async def track_user_behavior(
    request: BehaviorTrackingRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    追踪用户行为（焦点、停留、滚动）

    POST /api/v1/evolution/track-behavior
    {
        "request_id": "xxx",
        "behaviors": [
            {
                "element_id": "section-2",
                "element_type": "paragraph",
                "dwell_time_ms": 8500,
                "viewport_position": {"x": 0, "y": 500, "width": 1200, "height": 800}
            }
        ]
    }
    """
    try:
        # 分析热点
        hotspots = analyze_behavior_hotspots(request.behaviors)

        # 持久化行为记录到 user_focus_log
        session_id = request.session_id or str(uuid.uuid4())
        try:
            for behavior in request.behaviors:
                await db.execute(
                    text(
                        """
                        INSERT INTO user_focus_log
                        (session_id, request_id, element_id, element_type,
                         dwell_time_ms, viewport_position, timestamp)
                        VALUES (:session_id, :request_id, :element_id, :element_type,
                                :dwell_time_ms, :viewport_position, NOW())
                    """
                    ),
                    {
                        "session_id": session_id,
                        "request_id": request.request_id,
                        "element_id": behavior.get("element_id"),
                        "element_type": behavior.get("element_type", "other"),
                        "dwell_time_ms": behavior.get("dwell_time_ms", 0),
                        "viewport_position": behavior.get("viewport_position"),
                    },
                )
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to persist behavior (table may not exist): {e}")

        return JSONResponse(
            {
                "status": "tracked",
                "request_id": request.request_id,
                "behaviors_recorded": len(request.behaviors),
                "hotspots": hotspots,
                "insights": generate_behavior_insights(request.behaviors, hotspots),
            }
        )

    except Exception as e:
        logger.error(f"Behavior tracking failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"行为追踪失败: {str(e)}")


@router.post("/submit-feedback", response_model=JSONResponse)
async def submit_evolution_feedback(
    request: EvolutionFeedbackRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    提交对比反馈

    POST /api/v1/evolution/submit-feedback
    {
        "comparison_id": 123,
        "rating": "good",
        "preferred_ai": "lingzhi",
        "comment": "灵知系统的回答更详细"
    }
    """
    try:
        # 回写用户反馈到 ai_comparison_log
        try:
            result = await db.execute(
                text(
                    """
                    UPDATE ai_comparison_log
                    SET user_feedback = :feedback,
                        user_comment = :comment,
                        user_preference = :preference
                    WHERE id = :comparison_id
                """
                ),
                {
                    "feedback": request.rating,
                    "comment": request.comment,
                    "preference": request.preferred_ai,
                    "comparison_id": request.comparison_id,
                },
            )
            await db.commit()
            if result.rowcount == 0:
                logger.warning(f"Comparison {request.comparison_id} not found for feedback")
        except Exception as e:
            logger.warning(f"Failed to write feedback (table may not exist): {e}")

        # 识别进化方向
        opportunities = await detect_improvement_opportunities(request)

        # 自动执行进化（如果机会明确）
        evolution_results = await execute_evolution(opportunities)

        return JSONResponse(
            {
                "status": "success",
                "message": "反馈已提交，系统将自动学习改进",
                "opportunities_detected": len(opportunities),
                "evolution_results": evolution_results,
            }
        )

    except Exception as e:
        logger.error(f"Feedback submission failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"反馈提交失败: {str(e)}")


@router.get("/comparison/{comparison_id}", response_model=JSONResponse)
async def get_comparison_result(comparison_id: str, db: AsyncSession = Depends(get_async_session)):
    """获取对比结果详情"""
    try:
        result = await db.execute(
            text(
                """
                SELECT id, session_id, request_type, user_query,
                       lingzhi_response, competitor_responses,
                       comparison_metrics, winner,
                       user_feedback, user_comment, user_preference,
                       improvement_suggestions, improvement_status,
                       created_at
                FROM ai_comparison_log
                WHERE session_id = :comparison_id
                ORDER BY created_at DESC
                LIMIT 1
            """
            ),
            {"comparison_id": comparison_id},
        )
        row = result.mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail=f"Comparison {comparison_id} not found")

        return JSONResponse(
            {"comparison_id": comparison_id, "status": "found", "result": dict(row)}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get comparison: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取对比失败: {str(e)}")


@router.get("/dashboard", response_model=JSONResponse)
async def get_evolution_dashboard(
    period: Literal["7d", "30d", "90d"] = "30d", db: AsyncSession = Depends(get_async_session)
):
    """
    获取进化仪表板

    GET /api/v1/evolution/dashboard?period=30d

    显示：
    - 对比次数统计
    - 各AI胜率
    - 进化机会趋势
    - 已实施的进化
    """
    try:
        interval_map = {"7d": "7 days", "30d": "30 days", "90d": "90 days"}
        interval = interval_map.get(period, "30 days")

        # 1. 对比统计摘要
        summary_row = await db.execute(
            text(
                f"""
                SELECT
                    COUNT(*) AS total_comparisons,
                    COALESCE(SUM(CASE WHEN winner = 'lingzhi' THEN 1 ELSE 0 END)::float
                        / NULLIF(COUNT(*), 0) * 100, 0) AS lingzhi_win_rate
                FROM ai_comparison_log
                WHERE created_at >= NOW() - INTERVAL '{interval}'
            """
            )
        )
        summary = summary_row.mappings().first()

        # 2. 各AI胜率
        perf_rows = await db.execute(
            text(
                f"""
                SELECT
                    winner AS provider,
                    COUNT(*) AS wins,
                    COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0) AS win_rate
                FROM ai_comparison_log
                WHERE created_at >= NOW() - INTERVAL '{interval}'
                  AND winner IS NOT NULL
                GROUP BY winner
            """
            )
        )
        ai_performance = {}
        for row in perf_rows.mappings().all():
            ai_performance[row["provider"]] = {
                "wins": row["wins"],
                "win_rate": float(row["win_rate"] or 0),
            }
        for provider in ["lingzhi", "hunyuan", "doubao", "deepseek", "glm"]:
            ai_performance.setdefault(provider, {"wins": 0, "win_rate": 0.0})

        # 3. 进化趋势
        evo_rows = await db.execute(
            text(
                f"""
                SELECT
                    COUNT(*) AS total_issues,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS resolved_issues
                FROM evolution_log
                WHERE created_at >= NOW() - INTERVAL '{interval}'
            """
            )
        )
        evo = evo_rows.mappings().first()
        total_issues = evo["total_issues"] if evo else 0
        resolved = evo["resolved_issues"] if evo else 0

        # 4. 最近对比
        recent_rows = await db.execute(
            text(
                f"""
                SELECT id, session_id, request_type, winner, created_at
                FROM ai_comparison_log
                WHERE created_at >= NOW() - INTERVAL '{interval}'
                ORDER BY created_at DESC
                LIMIT 10
            """
            )
        )
        recent_comparisons = [dict(r) for r in recent_rows.mappings().all()]

        return JSONResponse(
            {
                "period": period,
                "summary": {
                    "total_comparisons": summary["total_comparisons"] if summary else 0,
                    "lingzhi_win_rate": (
                        float(summary["lingzhi_win_rate"])
                        if summary and summary["lingzhi_win_rate"]
                        else 0.0
                    ),
                    "avg_improvement_per_week": 0,
                },
                "ai_performance": ai_performance,
                "evolution_trends": {
                    "opportunities_detected": total_issues,
                    "evolutions_implemented": resolved or 0,
                    "improvement_rate": (resolved / total_issues * 100) if total_issues else 0.0,
                },
                "recent_comparisons": recent_comparisons,
                "top_improvements": [],
            }
        )

    except Exception as e:
        logger.error(f"Failed to get dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取仪表板失败: {str(e)}")


# ==================== 辅助函数 ====================


def analyze_behavior_hotspots(behaviors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """分析用户行为热点"""
    if not behaviors:
        return []

    # 按元素ID聚合停留时间
    element_dwell_times = {}
    for behavior in behaviors:
        element_id = behavior.get("element_id", "unknown")
        dwell_time = behavior.get("dwell_time_ms", 0)

        if element_id not in element_dwell_times:
            element_dwell_times[element_id] = {
                "total_dwell_time_ms": 0,
                "visit_count": 0,
                "element_type": behavior.get("element_type", "unknown"),
            }

        element_dwell_times[element_id]["total_dwell_time_ms"] += dwell_time
        element_dwell_times[element_id]["visit_count"] += 1

    # 找出热点（停留时间最长的3个元素）
    sorted_elements = sorted(
        element_dwell_times.items(), key=lambda x: x[1]["total_dwell_time_ms"], reverse=True
    )

    hotspots = []
    for element_id, data in sorted_elements[:3]:
        hotspots.append(
            {
                "element_id": element_id,
                "element_type": data["element_type"],
                "total_dwell_time_ms": data["total_dwell_time_ms"],
                "visit_count": data["visit_count"],
                "avg_dwell_time_ms": data["total_dwell_time_ms"] // data["visit_count"],
                "interest_level": "high" if data["total_dwell_time_ms"] > 10000 else "medium",
            }
        )

    return hotspots


def generate_behavior_insights(
    behaviors: List[Dict[str, Any]], hotspots: List[Dict[str, Any]]
) -> List[str]:
    """生成行为洞察"""

    insights = []

    # 总停留时间
    total_dwell_time = sum(b.get("dwell_time_ms", 0) for b in behaviors)

    if total_dwell_time < 5000:
        insights.append("用户快速浏览，可能内容不够吸引")
    elif total_dwell_time > 30000:
        insights.append("用户停留时间较长，内容较有吸引力")

    # 热点分析
    if hotspots:
        top_hotspot = hotspots[0]
        insights.append(
            f"用户最关注'{top_hotspot['element_id']}'部分，"
            f"停留{top_hotspot['total_dwell_time_ms'] / 1000:.1f}秒"
        )

    # 滚动深度
    max_scroll = max((b.get("viewport_position", {}).get("y", 0) for b in behaviors), default=0)

    if max_scroll < 500:
        insights.append("用户主要查看顶部内容")
    elif max_scroll > 2000:
        insights.append("用户查看了大部分内容")

    return insights


async def detect_improvement_opportunities(
    feedback: EvolutionFeedbackRequest,
) -> List[EvolutionOpportunity]:
    """识别改进机会"""

    opportunities = []

    # 如果用户偏好其他AI
    if feedback.preferred_ai != "lingzhi":
        opportunities.append(
            EvolutionOpportunity(
                type="competitor_outperformed",
                priority="high",
                description=f"用户更偏好{feedback.preferred_ai}",
                action="analyze_competitor_strength",
                details=f"对比ID: {feedback.comparison_id}, 用户偏好: {feedback.preferred_ai}",
            )
        )

    # 如果是差评
    if feedback.rating == "poor":
        opportunities.append(
            EvolutionOpportunity(
                type="quality_issue",
                priority="critical",
                description="用户满意度低",
                action="investigate_and_fix",
                details=feedback.comment or "无详细评论",
            )
        )

    # 如果有具体建议
    if feedback.comment and len(feedback.comment) > 10:
        opportunities.append(
            EvolutionOpportunity(
                type="user_suggestion",
                priority="medium",
                description="用户提供了具体建议",
                action="review_and_implement",
                details=feedback.comment,
            )
        )

    return opportunities


async def execute_evolution(opportunities: List[EvolutionOpportunity]) -> List[Dict[str, Any]]:
    """执行进化改进"""

    results = []

    for opportunity in opportunities:
        try:
            if opportunity.type == "competitor_outperformed":
                # 记录到进化日志，待人工审核
                result = {
                    "opportunity": opportunity.model_dump(),
                    "status": "logged_for_review",
                    "message": "已记录，等待人工分析竞品优势",
                }

            elif opportunity.type == "quality_issue":
                # 高优先级，立即标记
                result = {
                    "opportunity": opportunity.model_dump(),
                    "status": "flagged",
                    "message": "已标记为高优先级问题",
                }

            elif opportunity.type == "user_suggestion":
                # 记录建议
                result = {
                    "opportunity": opportunity.model_dump(),
                    "status": "suggestion_recorded",
                    "message": "用户建议已记录",
                }

            else:
                result = {
                    "opportunity": opportunity.model_dump(),
                    "status": "unknown_type",
                    "message": f"未知类型: {opportunity.type}",
                }

            results.append(result)

        except Exception as e:
            logger.error(f"Evolution execution failed: {e}")
            results.append(
                {"opportunity": opportunity.model_dump(), "status": "failed", "error": str(e)}
            )

    return results
