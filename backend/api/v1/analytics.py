"""用户价值追踪与分析API

提供用户行为追踪、满意度反馈、价值验证等功能
"""

import hashlib
import json
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.common.typing import JSONResponse
from backend.core.dependency_injection import get_db_pool, require_admin_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["用户价值分析"])


# ==================== 请求/响应模型 ====================


class TrackActivityRequest(BaseModel):
    """活动追踪请求"""

    action_type: Literal["search", "ask", "audio_play", "book_read", "other"]
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FeedbackRequest(BaseModel):
    """反馈请求（即时）"""

    rating: Literal["good", "neutral", "poor"]
    comment: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ExtendedFeedbackRequest(BaseModel):
    """深度反馈请求（周度/月度）"""

    feedback_type: Literal["weekly", "monthly"]
    rating: Literal["good", "neutral", "poor"]
    comment: str = Field(..., min_length=1, description="意见和建议")
    additional_context: Optional[Dict[str, Any]] = None


class DeletionRequest(BaseModel):
    """数据删除请求"""

    contact_email: Optional[str] = None
    reason: Optional[str] = None


class UserProfile(BaseModel):
    """用户状态"""

    user_id: Optional[str] = None
    session_id: str
    level: str
    display_name: Optional[str] = None
    total_sessions: int
    current_streak: int
    last_feedback_date: Optional[date] = None
    preferences: Dict[str, Any]


class DashboardStats(BaseModel):
    """仪表板统计"""

    period: str
    total_users: int
    active_users: int
    total_activities: int
    total_feedbacks: int
    avg_rating: float
    rating_distribution: Dict[str, int]
    top_features: List[str]
    nps_score: Optional[int] = None
    retention_7d: float
    retention_30d: float


# ==================== 辅助函数 ====================


def get_or_create_session_id(request: Request) -> str:
    """获取或创建session_id

    优先级：
    1. 请求头中的X-Session-ID
    2. Cookie中的session_id
    3. 生成新的UUID
    """
    # 检查请求头
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        return session_id

    # 检查cookie
    session_id = request.cookies.get("session_id")
    if session_id:
        return session_id

    # 生成新的
    return str(uuid.uuid4())


def get_user_id(request: Request) -> Optional[str]:
    """从JWT token中获取user_id"""
    # 从request.state.user获取（由JWT中间件设置）
    user = getattr(request.state, "user", None)
    if user:
        return user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    return None


def anonymize_content(content: str) -> str:
    """匿名化内容（SHA-256）"""
    return hashlib.sha256(content.encode()).hexdigest()


async def get_or_create_user_profile(
    conn, user_id: Optional[str], session_id: str
) -> Dict[str, Any]:
    """获取或创建用户状态"""
    if user_id:
        row = await conn.fetchrow(
            """
            SELECT user_id, session_id, display_name, level, first_seen_at,
                   last_active_at, total_sessions, current_streak,
                   last_feedback_date, preferences
            FROM user_profile
            WHERE user_id = $1
        """,
            user_id,
        )

        if row:
            await conn.execute(
                """
                UPDATE user_profile
                SET last_active_at = NOW()
                WHERE user_id = $1
            """,
                user_id,
            )
            return dict(row)
        else:
            await conn.execute(
                """
                    INSERT INTO user_profile (user_id, session_id, level, preferences)
                    VALUES ($1, $2, 'beginner', $3)
                """,
                user_id,
                session_id,
                json.dumps({}),
            )
            return {
                "user_id": user_id,
                "session_id": session_id,
                "level": "beginner",
                "total_sessions": 1,
                "current_streak": 0,
                "preferences": {},
            }
    else:
        row = await conn.fetchrow(
            """
            SELECT user_id, session_id, display_name, level, first_seen_at,
                   last_active_at, total_sessions, current_streak,
                   last_feedback_date, preferences
            FROM user_profile
            WHERE session_id = $1
        """,
            session_id,
        )

        if row:
            await conn.execute(
                """
                UPDATE user_profile
                SET last_active_at = NOW()
                WHERE session_id = $1
            """,
                session_id,
            )
            return dict(row)
        else:
            await conn.execute(
                """
                    INSERT INTO user_profile (session_id, level, preferences)
                    VALUES ($1, 'guest', $2)
                """,
                session_id,
                json.dumps({}),
            )
            return {
                "user_id": None,
                "session_id": session_id,
                "level": "guest",
                "total_sessions": 1,
                "current_streak": 0,
                "preferences": {},
            }


# ==================== API端点 ====================


@router.post("/track", response_model=JSONResponse)
async def track_activity(
    request: TrackActivityRequest,
    http_request: Request,
):
    """记录用户活动

    追踪用户的搜索、问答、音频播放、书籍阅读等行为
    """
    try:
        pool = get_db_pool()
        session_id = get_or_create_session_id(http_request)
        user_id = get_user_id(http_request)

        async with pool.acquire() as conn:
            # 获取用户隐私设置
            profile = await get_or_create_user_profile(conn, user_id, session_id)
            privacy_mode = profile.get("preferences", {}).get("privacy_mode", "standard")

            # 根据隐私设置决定是否记录具体内容
            content_anonymous = None
            content_to_store = request.content

            if privacy_mode == "anonymous":
                if request.content:
                    content_anonymous = anonymize_content(request.content)
                content_to_store = None
            elif privacy_mode == "standard":
                content_to_store = request.content
                if request.content:
                    content_anonymous = anonymize_content(request.content)
            else:  # full
                content_to_store = request.content

            await conn.execute(
                """
                INSERT INTO user_activity_log
                (user_id, session_id, action_type, content, content_anonymous,
                 metadata, ip_address, user_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                user_id,
                session_id,
                request.action_type,
                content_to_store,
                content_anonymous,
                json.dumps(request.metadata or {}),
                http_request.client.host if http_request.client else None,
                http_request.headers.get("user-agent"),
            )

        logger.info(f"Activity tracked: {request.action_type} for user {user_id or session_id}")

        return JSONResponse(
            {"status": "success", "session_id": session_id, "privacy_mode": privacy_mode}
        )

    except Exception as e:
        logger.error(f"Failed to track activity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to track activity: {str(e)}")


@router.post("/feedback/instant", response_model=JSONResponse)
async def submit_instant_feedback(
    request: FeedbackRequest, http_request: Request
):
    """提交即时反馈

    用户在使用某个功能后立即评价（好/中/差）
    """
    try:
        pool = get_db_pool()
        session_id = get_or_create_session_id(http_request)
        user_id = get_user_id(http_request)

        # 差评时建议填写评论
        if request.rating == "poor" and not request.comment:
            logger.warning(f"Poor feedback without comment from {user_id or session_id}")

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_feedback
                (user_id, session_id, feedback_type, rating, comment, context)
                VALUES ($1, $2, 'instant', $3, $4, $5)
                """,
                user_id,
                session_id,
                request.rating,
                request.comment,
                json.dumps(request.context or {}),
            )

            await conn.execute(
                """
                UPDATE user_profile
                SET last_feedback_date = CURRENT_DATE
                WHERE user_id = $1 OR (user_id IS NULL AND session_id = $2)
                """,
                user_id,
                session_id,
            )

        logger.info(f"Instant feedback submitted: {request.rating} from {user_id or session_id}")

        return JSONResponse({"status": "success", "message": "感谢您的反馈！"})

    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


@router.post("/feedback/extended", response_model=JSONResponse)
async def submit_extended_feedback(
    request: ExtendedFeedbackRequest,
    http_request: Request,
):
    """提交深度反馈

    周度或月度满意度调查，要求填写文字意见
    """
    try:
        pool = get_db_pool()
        session_id = get_or_create_session_id(http_request)
        user_id = get_user_id(http_request)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_feedback
                (user_id, session_id, feedback_type, rating, comment, context)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                user_id,
                session_id,
                request.feedback_type,
                request.rating,
                request.comment,
                json.dumps(request.additional_context or {}),
            )

            await conn.execute(
                """
                UPDATE user_profile
                SET last_feedback_date = CURRENT_DATE
                WHERE user_id = $1 OR (user_id IS NULL AND session_id = $2)
                """,
                user_id,
                session_id,
            )

        logger.info(
            f"Extended feedback submitted: {request.feedback_type} - {request.rating} from {user_id or session_id}"
        )

        return JSONResponse(
            {"status": "success", "message": "感谢您的详细反馈！这将帮助我们改进系统。"}
        )

    except Exception as e:
        logger.error(f"Failed to submit extended feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to submit extended feedback: {str(e)}")


@router.get("/me", response_model=UserProfile)
async def get_my_profile(http_request: Request):
    """获取当前用户状态"""
    try:
        pool = get_db_pool()
        session_id = get_or_create_session_id(http_request)
        user_id = get_user_id(http_request)

        async with pool.acquire() as conn:
            profile = await get_or_create_user_profile(conn, user_id, session_id)

        return UserProfile(
            user_id=profile.get("user_id"),
            session_id=profile.get("session_id") or session_id,
            level=profile.get("level", "guest"),
            display_name=profile.get("display_name"),
            total_sessions=profile.get("total_sessions", 0),
            current_streak=profile.get("current_streak", 0),
            last_feedback_date=profile.get("last_feedback_date"),
            preferences=profile.get("preferences", {}),
        )

    except Exception as e:
        logger.error(f"Failed to get user profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {str(e)}")


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(
    period: Literal["7d", "30d", "90d"] = Query("7d", description="统计周期"),
    _admin: bool = Depends(require_admin_api_key),
):
    """获取管理员仪表板数据

    仅限管理员访问
    """

    try:
        pool = get_db_pool()
        # 计算日期范围
        days_map = {"7d": 7, "30d": 30, "90d": 90}
        days = days_map[period]
        start_date = datetime.now() - timedelta(days=days)

        async with pool.acquire() as conn:
            # 总用户数（去重session_id）
            row = await conn.fetchrow(
                """
                SELECT COUNT(DISTINCT session_id) as total_users,
                       COUNT(DISTINCT user_id) as total_logged_in_users
                FROM user_activity_log
                WHERE created_at >= $1
                """,
                start_date,
            )
            total_users = row["total_users"] if row else 0

            # 活跃用户数（最近7天有活动）
            row = await conn.fetchrow(
                """
                SELECT COUNT(DISTINCT session_id) as active_users
                FROM user_activity_log
                WHERE created_at >= $1
                """,
                datetime.now() - timedelta(days=7),
            )
            active_users = row["active_users"] if row else 0

            # 总活动数
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) as total_activities
                FROM user_activity_log
                WHERE created_at >= $1
                """,
                start_date,
            )
            total_activities = row["total_activities"] if row else 0

            # 总反馈数
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) as total_feedbacks
                FROM user_feedback
                WHERE created_at >= $1
                """,
                start_date,
            )
            total_feedbacks = row["total_feedbacks"] if row else 0

            # 平均评分（good=5, neutral=3, poor=1）
            row = await conn.fetchrow(
                """
                SELECT
                    AVG(CASE WHEN rating = 'good' THEN 5
                             WHEN rating = 'neutral' THEN 3
                             WHEN rating = 'poor' THEN 1
                             END) as avg_rating
                FROM user_feedback
                WHERE created_at >= $1
                """,
                start_date,
            )
            avg_rating = float(row["avg_rating"]) if row and row["avg_rating"] else 0.0

            # 评分分布
            rows = await conn.fetch(
                """
                SELECT rating, COUNT(*) as count
                FROM user_feedback
                WHERE created_at >= $1
                GROUP BY rating
                """,
                start_date,
            )
            rating_distribution = {r["rating"]: r["count"] for r in rows}

            # Top功能
            rows = await conn.fetch(
                """
                SELECT action_type, COUNT(*) as count
                FROM user_activity_log
                WHERE created_at >= $1
                GROUP BY action_type
                ORDER BY count DESC
                LIMIT 5
                """,
                start_date,
            )
            top_features = [r["action_type"] for r in rows]

            # 留存率（简化计算）
            row = await conn.fetchrow(
                """
                WITH users_7d_ago AS (
                    SELECT DISTINCT session_id
                    FROM user_activity_log
                    WHERE created_at BETWEEN $1 AND $2
                ),
                users_today AS (
                    SELECT DISTINCT session_id
                    FROM user_activity_log
                    WHERE created_at >= $3
                )
                SELECT
                    COUNT(DISTINCT u.session_id) * 1.0 / NULLIF(COUNT(DISTINCT t.session_id), 0) as retention_rate
                FROM users_7d_ago t
                LEFT JOIN users_today u ON t.session_id = u.session_id
                """,
                datetime.now() - timedelta(days=14),
                datetime.now() - timedelta(days=7),
                datetime.now() - timedelta(days=1),
            )
            retention_7d = float(row["retention_rate"]) if row and row["retention_rate"] else 0.0

        # 30日留存（简化）
        retention_30d = max(0.0, retention_7d - 0.2)  # 粗略估算

        # NPS计算（简化版：good推荐者，poor贬损者）
        nps_score = None
        if total_feedbacks > 0:
            good_count = rating_distribution.get("good", 0)
            poor_count = rating_distribution.get("poor", 0)
            nps_score = int(((good_count - poor_count) * 100) / total_feedbacks)

        return DashboardStats(
            period=period,
            total_users=total_users,
            active_users=active_users,
            total_activities=total_activities,
            total_feedbacks=total_feedbacks,
            avg_rating=round(avg_rating, 2),
            rating_distribution=rating_distribution,
            top_features=top_features,
            nps_score=nps_score,
            retention_7d=round(retention_7d, 2),
            retention_30d=round(retention_30d, 2),
        )

    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard: {str(e)}")


@router.post("/request-deletion", response_model=JSONResponse)
async def request_data_deletion(
    request: DeletionRequest, http_request: Request
):
    """请求数据删除

    用户可以请求删除所有追踪数据（GDPR合规）
    """
    try:
        pool = get_db_pool()
        session_id = get_or_create_session_id(http_request)
        user_id = get_user_id(http_request)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO data_deletion_requests
                (user_id, session_id, contact_email, status)
                VALUES ($1, $2, $3, 'pending')
                """,
                user_id,
                session_id,
                request.contact_email,
            )

        logger.info(f"Data deletion requested from {user_id or session_id}")

        return JSONResponse(
            {
                "status": "success",
                "message": "您的数据删除请求已记录。我们将在7个工作日内处理。",
                "request_id": session_id,
            }
        )

    except Exception as e:
        logger.error(f"Failed to request deletion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to request deletion: {str(e)}")


@router.get("/privacy-policy")
async def get_privacy_policy() -> dict:
    """获取隐私政策"""
    return {
        "policy_version": "1.0.0",
        "last_updated": "2026-04-01",
        "data_collection": {
            "what_we_collect": [
                "使用行为：搜索、问答、音频播放、书籍阅读",
                "满意度反馈：好/中/差评价，文字意见",
                "技术信息：IP地址（防滥用）、设备类型",
            ],
            "what_we_dont_collect": [
                "个人身份信息（除非您主动提供）",
                "敏感个人信息（健康、政治、宗教等）",
            ],
        },
        "data_usage": {
            "purposes": ["改进系统功能和准确性", "验证用户价值", "统计分析（匿名化）"],
            "never_sold": "我们从不出售、出租或交易您的个人数据",
        },
        "data_retention": {
            "anonymous_users": "90天",
            "logged_in_users": "永久（直到您要求删除）",
            "feedback": "永久（用于改进）",
        },
        "your_rights": {
            "access": "您可以查看我们收集的关于您的数据",
            "delete": "您可以要求删除所有数据",
            "opt_out": "您可以设置隐私模式为'匿名'",
        },
        "contact": {"email": "privacy@example.com", "response_time": "7个工作日内"},
    }
