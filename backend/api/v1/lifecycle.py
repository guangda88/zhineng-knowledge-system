"""生命周期追踪 API

提供用户等级、生命状态、练习记录、练习计划等接口。
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lifecycle", tags=["生命周期追踪"])


# ==================== 请求/响应模型 ====================


class UserLevelCreate(BaseModel):
    user_id: str = Field(..., description="用户ID")
    current_level: str = Field(default="入门", description="等级: 入门/初级/中级/高级")
    notes: Optional[str] = None


class LifeStateRecord(BaseModel):
    user_id: str = Field(..., description="用户ID")
    tracked_date: Optional[date] = None
    physical_health: int = Field(..., ge=1, le=10, description="身体健康 (1-10)")
    mental_peace: int = Field(..., ge=1, le=10, description="心境平和 (1-10)")
    energy_level: int = Field(..., ge=1, le=10, description="精力水平 (1-10)")
    sleep_quality: Optional[int] = Field(None, ge=1, le=10, description="睡眠质量 (1-10)")
    emotional_stability: Optional[int] = Field(None, ge=1, le=10, description="情绪稳定 (1-10)")
    subjective_notes: Optional[str] = None


class PracticeRecordCreate(BaseModel):
    user_id: str = Field(..., description="用户ID")
    concept: Optional[str] = Field(None, description="练习概念/名称")
    practice_type: Optional[str] = Field(None, description="类型: 站桩/打坐/八段锦/呼吸法/其他")
    duration_minutes: Optional[int] = Field(None, ge=1, description="时长(分钟)")
    subjective_feeling: Optional[str] = None
    difficulty_level: Optional[int] = Field(None, ge=1, le=5, description="难度 (1-5)")
    notes: Optional[str] = None


class PracticePlanCreate(BaseModel):
    user_id: str = Field(..., description="用户ID")
    plan_name: str = Field(..., description="计划名称")
    goal: Optional[str] = None
    plan_type: str = Field(default="manual", description="类型: manual/ai_generated/template")
    start_date: date
    end_date: date
    daily_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    milestones: List[Dict[str, Any]] = Field(default_factory=list)
    template_id: Optional[str] = None


class PracticePlanUpdate(BaseModel):
    plan_name: Optional[str] = None
    goal: Optional[str] = None
    status: Optional[str] = Field(None, description="状态: active/completed/paused/abandoned")
    daily_tasks: Optional[List[Dict[str, Any]]] = None
    milestones: Optional[List[Dict[str, Any]]] = None


# ==================== 用户等级 ====================


@router.post("/user-level")
async def create_user_level(request: UserLevelCreate):
    """创建或更新用户等级"""
    try:
        from backend.core.database import init_db_pool

        pool = await init_db_pool()

        existing = await pool.fetchrow(
            "SELECT user_id FROM user_levels WHERE user_id = $1",
            request.user_id,
        )

        if existing:
            await pool.execute(
                """UPDATE user_levels
                   SET current_level = $1, notes = $2,
                       level_history = level_history || $3::jsonb,
                       updated_at = NOW()
                   WHERE user_id = $4""",
                request.current_level,
                request.notes,
                [{"level": request.current_level, "changed_at": datetime.now().isoformat()}],
                request.user_id,
            )
        else:
            await pool.execute(
                """INSERT INTO user_levels (user_id, current_level, notes)
                   VALUES ($1, $2, $3)""",
                request.user_id,
                request.current_level,
                request.notes,
            )

        return {
            "status": "ok",
            "data": {"user_id": request.user_id, "level": request.current_level},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_user_level failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建用户等级失败")


@router.get("/user-level/{user_id}")
async def get_user_level(user_id: str):
    """获取用户等级"""
    try:
        from backend.core.database import init_db_pool

        pool = await init_db_pool()
        row = await pool.fetchrow(
            "SELECT user_id, current_level, level_history, notes, created_at, updated_at "
            "FROM user_levels WHERE user_id = $1",
            user_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {"status": "ok", "data": dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_user_level failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询用户等级失败")


# ==================== 生命状态 ====================


@router.post("/life-state/record")
async def record_life_state(request: LifeStateRecord):
    """记录生命状态自评"""
    try:
        from backend.core.database import init_db_pool

        pool = await init_db_pool()

        user_exists = await pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM user_levels WHERE user_id = $1)",
            request.user_id,
        )
        if not user_exists:
            raise HTTPException(status_code=404, detail="用户不存在，请先创建用户等级")

        tracked = request.tracked_date or date.today()

        existing = await pool.fetchval(
            "SELECT id FROM life_state_tracking " "WHERE user_id = $1 AND tracked_date = $2",
            request.user_id,
            tracked,
        )
        if existing:
            await pool.execute(
                """UPDATE life_state_tracking
                   SET physical_health = $1, mental_peace = $2,
                       energy_level = $3, sleep_quality = $4,
                       emotional_stability = $5, subjective_notes = $6
                   WHERE id = $7""",
                request.physical_health,
                request.mental_peace,
                request.energy_level,
                request.sleep_quality,
                request.emotional_stability,
                request.subjective_notes,
                existing,
            )
            return {"status": "ok", "data": {"id": existing, "updated": True}}

        row = await pool.fetchrow(
            """INSERT INTO life_state_tracking
                (user_id, tracked_date, physical_health, mental_peace,
                 energy_level, sleep_quality, emotional_stability, subjective_notes)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               RETURNING id, tracked_date""",
            request.user_id,
            tracked,
            request.physical_health,
            request.mental_peace,
            request.energy_level,
            request.sleep_quality,
            request.emotional_stability,
            request.subjective_notes,
        )

        return {"status": "ok", "data": dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"record_life_state failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="记录生命状态失败")


@router.get("/life-state/{user_id}")
async def get_life_state_history(
    user_id: str,
    limit: int = Query(default=30, ge=1, le=365),
):
    """获取生命状态历史"""
    try:
        from backend.core.database import init_db_pool

        pool = await init_db_pool()
        rows = await pool.fetch(
            """SELECT id, tracked_date, physical_health, mental_peace,
                      energy_level, sleep_quality, emotional_stability,
                      subjective_notes, created_at
               FROM life_state_tracking
               WHERE user_id = $1
               ORDER BY tracked_date DESC
               LIMIT $2""",
            user_id,
            limit,
        )
        return {"status": "ok", "data": [dict(r) for r in rows]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_life_state_history failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询生命状态历史失败")


# ==================== 练习记录 ====================


@router.post("/practice/record")
async def record_practice(request: PracticeRecordCreate):
    """记录一次练习"""
    try:
        from backend.core.database import init_db_pool

        pool = await init_db_pool()

        user_exists = await pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM user_levels WHERE user_id = $1)",
            request.user_id,
        )
        if not user_exists:
            raise HTTPException(status_code=404, detail="用户不存在，请先创建用户等级")

        row = await pool.fetchrow(
            """INSERT INTO practice_records
                (user_id, concept, practice_type, duration_minutes,
                 subjective_feeling, difficulty_level, notes)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING id, practice_date, concept, duration_minutes""",
            request.user_id,
            request.concept,
            request.practice_type,
            request.duration_minutes,
            request.subjective_feeling,
            request.difficulty_level,
            request.notes,
        )

        return {"status": "ok", "data": dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"record_practice failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="记录练习失败")


@router.get("/practice/my-records")
async def get_practice_records(
    user_id: str = Query(..., description="用户ID"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """查看我的练习记录"""
    try:
        from backend.core.database import init_db_pool

        pool = await init_db_pool()

        total = await pool.fetchval(
            "SELECT COUNT(*) FROM practice_records WHERE user_id = $1",
            user_id,
        )

        rows = await pool.fetch(
            """SELECT id, concept, practice_type, practice_date,
                      duration_minutes, subjective_feeling, difficulty_level, notes
               FROM practice_records
               WHERE user_id = $1
               ORDER BY practice_date DESC
               LIMIT $2 OFFSET $3""",
            user_id,
            limit,
            offset,
        )

        return {
            "status": "ok",
            "data": {
                "total": total,
                "items": [dict(r) for r in rows],
                "limit": limit,
                "offset": offset,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_practice_records failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询练习记录失败")


# ==================== 练习计划 ====================


@router.post("/practice/plan")
async def create_practice_plan(request: PracticePlanCreate):
    """创建练习计划"""
    try:
        from backend.core.database import init_db_pool

        pool = await init_db_pool()

        user_exists = await pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM user_levels WHERE user_id = $1)",
            request.user_id,
        )
        if not user_exists:
            raise HTTPException(status_code=404, detail="用户不存在，请先创建用户等级")

        if request.start_date >= request.end_date:
            raise HTTPException(status_code=400, detail="结束日期必须晚于开始日期")

        row = await pool.fetchrow(
            """INSERT INTO practice_plans
                (user_id, plan_name, goal, plan_type, start_date, end_date,
                 daily_tasks, milestones, template_id)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING id, plan_name, start_date, end_date, status""",
            request.user_id,
            request.plan_name,
            request.goal,
            request.plan_type,
            request.start_date,
            request.end_date,
            request.daily_tasks,
            request.milestones,
            request.template_id,
        )

        return {"status": "ok", "data": dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_practice_plan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建练习计划失败")


@router.get("/practice/plans")
async def get_practice_plans(
    user_id: str = Query(..., description="用户ID"),
    status: Optional[str] = Query(None, description="计划状态过滤"),
):
    """查看我的练习计划"""
    try:
        from backend.core.database import init_db_pool

        pool = await init_db_pool()

        conditions = ["user_id = $1"]
        params: list = [user_id]
        idx = 2

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where = " AND ".join(conditions)

        rows = await pool.fetch(
            f"""SELECT id, plan_name, goal, plan_type, start_date, end_date,
                      status, daily_tasks, milestones, created_at, updated_at
               FROM practice_plans
               WHERE {where}
               ORDER BY created_at DESC""",
            *params,
        )

        return {"status": "ok", "data": [dict(r) for r in rows]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_practice_plans failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询练习计划失败")


@router.put("/practice/plan/{plan_id}")
async def update_practice_plan(plan_id: int, request: PracticePlanUpdate):
    """更新练习计划"""
    try:
        from backend.core.database import init_db_pool

        pool = await init_db_pool()

        existing = await pool.fetchrow(
            "SELECT id FROM practice_plans WHERE id = $1",
            plan_id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="计划不存在")

        updates = []
        params: list = []
        idx = 1

        for field in ["plan_name", "goal", "status", "daily_tasks", "milestones"]:
            val = getattr(request, field, None)
            if val is not None:
                updates.append(f"{field} = ${idx}")
                params.append(val)
                idx += 1

        if not updates:
            return {"status": "ok", "data": {"updated": False}}

        params.append(plan_id)
        await pool.execute(
            f"UPDATE practice_plans SET {', '.join(updates)} WHERE id = ${idx}",
            *params,
        )

        return {"status": "ok", "data": {"updated": True}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_practice_plan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新练习计划失败")


# ==================== 统计概览 ====================


@router.get("/dashboard/{user_id}")
async def get_user_dashboard(user_id: str):
    """用户综合概览"""
    try:
        from backend.core.database import init_db_pool

        pool = await init_db_pool()

        user = await pool.fetchrow(
            "SELECT user_id, current_level, created_at FROM user_levels WHERE user_id = $1",
            user_id,
        )
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        total_practice = await pool.fetchval(
            "SELECT COUNT(*) FROM practice_records WHERE user_id = $1",
            user_id,
        )

        total_minutes = await pool.fetchval(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM practice_records WHERE user_id = $1",
            user_id,
        )

        latest_state = await pool.fetchrow(
            """SELECT physical_health, mental_peace, energy_level,
                      sleep_quality, emotional_stability, tracked_date
               FROM life_state_tracking
               WHERE user_id = $1
               ORDER BY tracked_date DESC LIMIT 1""",
            user_id,
        )

        active_plans = await pool.fetchval(
            "SELECT COUNT(*) FROM practice_plans WHERE user_id = $1 AND status = 'active'",
            user_id,
        )

        return {
            "status": "ok",
            "data": {
                "user": dict(user),
                "total_practice_sessions": total_practice,
                "total_practice_minutes": total_minutes,
                "latest_life_state": dict(latest_state) if latest_state else None,
                "active_plans": active_plans,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_user_dashboard failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询用户概览失败")
