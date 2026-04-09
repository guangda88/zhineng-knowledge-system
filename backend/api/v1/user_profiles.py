"""用户画像和评估系统API路由

提供用户等级管理、生活状态追踪、练习记录、练习计划等功能
"""

import logging
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.common.db_helpers import (
    require_pool,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["用户画像与评估"])


# ==================== 请求/响应模型 ====================


class UserProfile(BaseModel):
    """用户画像"""

    user_id: str
    current_level: str = Field(default="入门", description="当前等级: 入门, 初级, 中级, 高级")
    level_history: List[dict] = Field(default_factory=list, description="等级历史")
    assessment_score: Optional[float] = Field(default=None, description="评估分数")
    notes: Optional[str] = Field(default=None, description="备注")
    created_at: datetime
    updated_at: datetime


class UserProfileCreate(BaseModel):
    """创建用户画像"""

    user_id: str
    current_level: str = Field(default="入门", pattern="^(入门|初级|中级|高级)$")
    assessment_score: Optional[float] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = None


class UserProfileUpdate(BaseModel):
    """更新用户画像"""

    current_level: Optional[str] = Field(default=None, pattern="^(入门|初级|中级|高级)$")
    assessment_score: Optional[float] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = None


class LifeStateTracking(BaseModel):
    """生活状态追踪"""

    id: int
    user_id: str
    tracked_date: date
    physical_health: Optional[int] = Field(default=None, ge=1, le=10, description="身体健康 (1-10)")
    mental_peace: Optional[int] = Field(default=None, ge=1, le=10, description="内心平静 (1-10)")
    energy_level: Optional[int] = Field(default=None, ge=1, le=10, description="精力水平 (1-10)")
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=10, description="睡眠质量 (1-10)")
    emotional_stability: Optional[int] = Field(
        default=None, ge=1, le=10, description="情绪稳定 (1-10)"
    )
    subjective_notes: Optional[str] = Field(default=None, description="主观记录")
    created_at: datetime


class LifeStateCreate(BaseModel):
    """创建生活状态记录"""

    user_id: str
    tracked_date: Optional[date] = Field(default_factory=date.today)
    physical_health: Optional[int] = Field(default=None, ge=1, le=10)
    mental_peace: Optional[int] = Field(default=None, ge=1, le=10)
    energy_level: Optional[int] = Field(default=None, ge=1, le=10)
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=10)
    emotional_stability: Optional[int] = Field(default=None, ge=1, le=10)
    subjective_notes: Optional[str] = None


class PracticeRecord(BaseModel):
    """练习记录"""

    id: int
    user_id: str
    concept: Optional[str] = Field(default=None, description="练习概念")
    practice_type: Optional[str] = Field(
        default=None, description="练习类型: 站桩, 打坐, 八段锦, 呼吸法, 其他"
    )
    practice_date: datetime
    duration_minutes: Optional[int] = Field(default=None, ge=1, description="练习时长（分钟）")
    subjective_feeling: Optional[str] = Field(default=None, description="主观感受")
    difficulty_level: Optional[int] = Field(default=None, ge=1, le=5, description="难度等级 (1-5)")
    notes: Optional[str] = Field(default=None, description="备注")
    created_at: datetime


class PracticeRecordCreate(BaseModel):
    """创建练习记录"""

    user_id: str
    concept: Optional[str] = None
    practice_type: Optional[str] = None
    practice_date: Optional[datetime] = Field(default_factory=datetime.now)
    duration_minutes: Optional[int] = Field(default=None, ge=1)
    subjective_feeling: Optional[str] = None
    difficulty_level: Optional[int] = Field(default=None, ge=1, le=5)
    notes: Optional[str] = None


class PracticePlan(BaseModel):
    """练习计划"""

    id: int
    user_id: str
    plan_name: str
    goal: Optional[str] = Field(default=None, description="目标")
    plan_type: str = Field(default="manual", description="计划类型: manual, ai_generated, template")
    start_date: date
    end_date: date
    status: str = Field(default="active", description="状态: active, completed, paused")
    created_at: datetime


class PracticePlanCreate(BaseModel):
    """创建练习计划"""

    user_id: str
    plan_name: str
    goal: Optional[str] = None
    plan_type: str = Field(default="manual", pattern="^(manual|ai_generated|template)$")
    start_date: date
    end_date: date


class PracticePlanUpdate(BaseModel):
    """更新练习计划"""

    plan_name: Optional[str] = None
    goal: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(active|completed|paused)$")
    end_date: Optional[date] = None


class UserAssessmentResponse(BaseModel):
    """用户评估响应"""

    user_id: str
    current_level: str
    assessment_score: Optional[float]
    practice_count_last_30_days: int
    total_practice_minutes_last_30_days: int
    life_state_avg_last_30_days: dict
    recommendations: List[str]


# ==================== 用户画像 API ====================


@router.get("/profiles/{user_id}", response_model=UserProfile)
async def get_user_profile(user_id: str):
    """获取用户画像"""
    pool = require_pool()
    row = await pool.fetchrow("SELECT * FROM user_levels WHERE user_id = $1", user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserProfile(**dict(row))


@router.post("/profiles", response_model=UserProfile)
async def create_user_profile(profile: UserProfileCreate):
    """创建用户画像"""
    pool = require_pool()
    try:
        row = await pool.fetchrow(
            """INSERT INTO user_levels (user_id, current_level, assessment_score, notes)
            VALUES ($1, $2, $3, $4)
            RETURNING *""",
            profile.user_id,
            profile.current_level,
            profile.assessment_score,
            profile.notes,
        )
        return UserProfile(**dict(row))
    except Exception as e:
        if "user_levels_pkey" in str(e):
            raise HTTPException(status_code=400, detail="用户已存在")
        raise


@router.put("/profiles/{user_id}", response_model=UserProfile)
async def update_user_profile(user_id: str, profile: UserProfileUpdate):
    """更新用户画像"""
    pool = require_pool()
    updates = []
    values = []
    param_count = 1

    if profile.current_level is not None:
        updates.append(f"current_level = ${param_count}")
        values.append(profile.current_level)
        param_count += 1

    if profile.assessment_score is not None:
        updates.append(f"assessment_score = ${param_count}")
        values.append(profile.assessment_score)
        param_count += 1

    if profile.notes is not None:
        updates.append(f"notes = ${param_count}")
        values.append(profile.notes)
        param_count += 1

    if not updates:
        raise HTTPException(status_code=400, detail="没有提供更新内容")

    values.append(user_id)
    query = f"""
        UPDATE user_levels
        SET {', '.join(updates)}
        WHERE user_id = ${param_count}
        RETURNING *
    """

    row = await pool.fetchrow(query, *values)
    if row is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserProfile(**dict(row))


# ==================== 生活状态追踪 API ====================


@router.post("/life-state", response_model=LifeStateTracking)
async def create_life_state_tracking(state: LifeStateCreate):
    """记录生活状态"""
    pool = require_pool()
    try:
        row = await pool.fetchrow(
            """INSERT INTO life_state_tracking
            (user_id, tracked_date, physical_health, mental_peace, energy_level, sleep_quality, emotional_stability, subjective_notes)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *""",
            state.user_id,
            state.tracked_date,
            state.physical_health,
            state.mental_peace,
            state.energy_level,
            state.sleep_quality,
            state.emotional_stability,
            state.subjective_notes,
        )
        return LifeStateTracking(**dict(row))
    except Exception as e:
        if "user_levels_fkey" in str(e):
            raise HTTPException(status_code=400, detail="用户不存在，请先创建用户画像")
        raise


@router.get("/life-state/{user_id}", response_model=List[LifeStateTracking])
async def get_life_state_tracking(user_id: str, limit: int = Query(default=30, ge=1, le=365)):
    """获取用户生活状态记录"""
    pool = require_pool()
    rows = await pool.fetch(
        """SELECT * FROM life_state_tracking
        WHERE user_id = $1
        ORDER BY tracked_date DESC
        LIMIT $2""",
        user_id,
        limit,
    )
    return [LifeStateTracking(**dict(row)) for row in rows]


@router.get("/life-state/{user_id}/summary")
async def get_life_state_summary(user_id: str, days: int = Query(default=30, ge=1, le=365)):
    """获取生活状态统计摘要"""
    pool = require_pool()
    rows = await pool.fetch(
        """SELECT
            AVG(physical_health) as avg_physical,
            AVG(mental_peace) as avg_mental,
            AVG(energy_level) as avg_energy,
            AVG(sleep_quality) as avg_sleep,
            AVG(emotional_stability) as avg_emotional,
            COUNT(*) as record_count
        FROM life_state_tracking
        WHERE user_id = $1
        AND tracked_date >= CURRENT_DATE - INTERVAL '1 day' * $2""",
        user_id,
        days,
    )
    row = rows[0]
    return {
        "user_id": user_id,
        "period_days": days,
        "physical_health": round(float(row["avg_physical"] or 0), 1),
        "mental_peace": round(float(row["avg_mental"] or 0), 1),
        "energy_level": round(float(row["avg_energy"] or 0), 1),
        "sleep_quality": round(float(row["avg_sleep"] or 0), 1),
        "emotional_stability": round(float(row["avg_emotional"] or 0), 1),
        "record_count": row["record_count"],
    }


# ==================== 练习记录 API ====================


@router.post("/practice", response_model=PracticeRecord)
async def create_practice_record(record: PracticeRecordCreate):
    """记录练习"""
    pool = require_pool()
    try:
        row = await pool.fetchrow(
            """INSERT INTO practice_records
            (user_id, concept, practice_type, practice_date, duration_minutes, subjective_feeling, difficulty_level, notes)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *""",
            record.user_id,
            record.concept,
            record.practice_type,
            record.practice_date,
            record.duration_minutes,
            record.subjective_feeling,
            record.difficulty_level,
            record.notes,
        )
        return PracticeRecord(**dict(row))
    except Exception as e:
        if "user_levels_fkey" in str(e):
            raise HTTPException(status_code=400, detail="用户不存在，请先创建用户画像")
        raise


@router.get("/practice/{user_id}", response_model=List[PracticeRecord])
async def get_practice_records(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    practice_type: Optional[str] = Query(default=None),
):
    """获取用户练习记录"""
    pool = require_pool()
    if practice_type:
        rows = await pool.fetch(
            """SELECT * FROM practice_records
            WHERE user_id = $1 AND practice_type = $2
            ORDER BY practice_date DESC
            LIMIT $3""",
            user_id,
            practice_type,
            limit,
        )
    else:
        rows = await pool.fetch(
            """SELECT * FROM practice_records
            WHERE user_id = $1
            ORDER BY practice_date DESC
            LIMIT $2""",
            user_id,
            limit,
        )
    return [PracticeRecord(**dict(row)) for row in rows]


@router.get("/practice/{user_id}/summary")
async def get_practice_summary(user_id: str, days: int = Query(default=30, ge=1, le=365)):
    """获取练习统计摘要"""
    pool = require_pool()
    rows = await pool.fetch(
        """SELECT
            COUNT(*) as record_count,
            SUM(duration_minutes) as total_minutes,
            AVG(duration_minutes) as avg_minutes,
            AVG(difficulty_level) as avg_difficulty,
            COUNT(DISTINCT practice_date::date) as practice_days
        FROM practice_records
        WHERE user_id = $1
        AND practice_date >= CURRENT_DATE - INTERVAL '1 day' * $2""",
        user_id,
        days,
    )
    row = rows[0]
    return {
        "user_id": user_id,
        "period_days": days,
        "record_count": row["record_count"],
        "total_minutes": int(row["total_minutes"] or 0),
        "avg_minutes": round(float(row["avg_minutes"] or 0), 1),
        "avg_difficulty": round(float(row["avg_difficulty"] or 0), 1),
        "practice_days": row["practice_days"],
    }


# ==================== 练习计划 API ====================


@router.post("/plans", response_model=PracticePlan)
async def create_practice_plan(plan: PracticePlanCreate):
    """创建练习计划"""
    pool = require_pool()
    try:
        row = await pool.fetchrow(
            """INSERT INTO practice_plans
            (user_id, plan_name, goal, plan_type, start_date, end_date)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *""",
            plan.user_id,
            plan.plan_name,
            plan.goal,
            plan.plan_type,
            plan.start_date,
            plan.end_date,
        )
        return PracticePlan(**dict(row))
    except Exception as e:
        if "user_levels_fkey" in str(e):
            raise HTTPException(status_code=400, detail="用户不存在，请先创建用户画像")
        raise


@router.get("/plans/{user_id}", response_model=List[PracticePlan])
async def get_practice_plans(user_id: str, status: Optional[str] = Query(default=None)):
    """获取用户练习计划"""
    pool = require_pool()
    if status:
        rows = await pool.fetch(
            """SELECT * FROM practice_plans
            WHERE user_id = $1 AND status = $2
            ORDER BY created_at DESC""",
            user_id,
            status,
        )
    else:
        rows = await pool.fetch(
            """SELECT * FROM practice_plans
            WHERE user_id = $1
            ORDER BY created_at DESC""",
            user_id,
        )
    return [PracticePlan(**dict(row)) for row in rows]


@router.put("/plans/{plan_id}", response_model=PracticePlan)
async def update_practice_plan(plan_id: int, plan: PracticePlanUpdate):
    """更新练习计划"""
    pool = require_pool()
    updates = []
    values = []
    param_count = 1

    if plan.plan_name is not None:
        updates.append(f"plan_name = ${param_count}")
        values.append(plan.plan_name)
        param_count += 1

    if plan.goal is not None:
        updates.append(f"goal = ${param_count}")
        values.append(plan.goal)
        param_count += 1

    if plan.status is not None:
        updates.append(f"status = ${param_count}")
        values.append(plan.status)
        param_count += 1

    if plan.end_date is not None:
        updates.append(f"end_date = ${param_count}")
        values.append(plan.end_date)
        param_count += 1

    if not updates:
        raise HTTPException(status_code=400, detail="没有提供更新内容")

    values.append(plan_id)
    query = f"""
        UPDATE practice_plans
        SET {', '.join(updates)}
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await pool.fetchrow(query, *values)
    if row is None:
        raise HTTPException(status_code=404, detail="计划不存在")
    return PracticePlan(**dict(row))


# ==================== 综合评估 API ====================


@router.get("/assessment/{user_id}", response_model=UserAssessmentResponse)
async def get_user_assessment(user_id: str):
    """获取用户综合评估"""
    pool = require_pool()

    # 获取用户画像
    profile_row = await pool.fetchrow("SELECT * FROM user_levels WHERE user_id = $1", user_id)
    if profile_row is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 获取练习统计
    practice_stats = await pool.fetchrow(
        """SELECT
            COUNT(*) as practice_count,
            SUM(duration_minutes) as total_minutes
        FROM practice_records
        WHERE user_id = $1
        AND practice_date >= CURRENT_DATE - INTERVAL '30 days'""",
        user_id,
    )

    # 获取生活状态平均
    life_state_stats = await pool.fetchrow(
        """SELECT
            AVG(physical_health) as avg_physical,
            AVG(mental_peace) as avg_mental,
            AVG(energy_level) as avg_energy,
            AVG(sleep_quality) as avg_sleep,
            AVG(emotional_stability) as avg_emotional
        FROM life_state_tracking
        WHERE user_id = $1
        AND tracked_date >= CURRENT_DATE - INTERVAL '30 days'""",
        user_id,
    )

    # 生成建议
    recommendations = []
    if practice_stats["practice_count"] < 10:
        recommendations.append("建议增加练习频次，每天保持一定时间的练习")
    if practice_stats["total_minutes"] < 300:
        recommendations.append("建议延长每次练习时间，循序渐进地增加练习时长")
    avg_energy = float(life_state_stats["avg_energy"] or 0)
    if avg_energy < 6:
        recommendations.append("精力水平偏低，建议注意休息和调整作息")
    avg_sleep = float(life_state_stats["avg_sleep"] or 0)
    if avg_sleep < 6:
        recommendations.append("睡眠质量有待提升，建议建立规律的睡眠习惯")

    if not recommendations:
        recommendations.append("保持当前练习状态，继续努力！")

    return UserAssessmentResponse(
        user_id=user_id,
        current_level=profile_row["current_level"],
        assessment_score=profile_row["assessment_score"],
        practice_count_last_30_days=practice_stats["practice_count"],
        total_practice_minutes_last_30_days=int(practice_stats["total_minutes"] or 0),
        life_state_avg_last_30_days={
            "physical_health": round(float(life_state_stats["avg_physical"] or 0), 1),
            "mental_peace": round(float(life_state_stats["avg_mental"] or 0), 1),
            "energy_level": round(float(life_state_stats["avg_energy"] or 0), 1),
            "sleep_quality": round(float(life_state_stats["avg_sleep"] or 0), 1),
            "emotional_stability": round(float(life_state_stats["avg_emotional"] or 0), 1),
        },
        recommendations=recommendations,
    )
