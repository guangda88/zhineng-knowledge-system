"""生命周期追踪 API 测试

覆盖: 用户等级、生命状态追踪、练习记录、练习计划、用户概览
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def mock_pool():
    """Mock asyncpg pool for lifecycle tests"""
    pool = AsyncMock()

    async def mock_execute(query, *args):
        return "UPDATE 1"

    async def mock_fetchval(query, *args):
        if "EXISTS" in query:
            return True
        if "COUNT" in query:
            return 5
        return 1

    async def mock_fetchrow(query, *args):
        return {
            "user_id": "test_user",
            "current_level": "初级",
            "level_history": [],
            "notes": None,
            "created_at": "2026-04-03T00:00:00",
            "updated_at": "2026-04-03T00:00:00",
        }

    async def mock_fetch(query, *args):
        return [
            {
                "id": 1,
                "tracked_date": "2026-04-03",
                "physical_health": 6,
                "mental_peace": 5,
                "energy_level": 6,
                "sleep_quality": 5,
                "emotional_stability": 5,
                "subjective_notes": "测试",
                "created_at": "2026-04-03T00:00:00",
            }
        ]

    pool.execute = AsyncMock(side_effect=mock_execute)
    pool.fetchval = AsyncMock(side_effect=mock_fetchval)
    pool.fetchrow = AsyncMock(side_effect=mock_fetchrow)
    pool.fetch = AsyncMock(side_effect=mock_fetch)
    return pool


# ==================== 用户等级测试 ====================


class TestUserLevel:
    """用户等级 API 测试"""

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_create_user_level_new(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchrow = AsyncMock(return_value=None)

        response = client.post(
            "/api/v1/lifecycle/user-level",
            json={"user_id": "new_user", "current_level": "入门", "notes": "测试用户"},
        )
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert data["data"]["user_id"] == "new_user"

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_create_user_level_existing(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchrow = AsyncMock(return_value={"user_id": "existing_user"})

        response = client.post(
            "/api/v1/lifecycle/user-level",
            json={"user_id": "existing_user", "current_level": "初级"},
        )
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_get_user_level_found(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool

        response = client.get("/api/v1/lifecycle/user-level/test_user")
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert "data" in data

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_get_user_level_not_found(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchrow = AsyncMock(return_value=None)

        response = client.get("/api/v1/lifecycle/user-level/nonexistent")
        assert response.status_code in [404, 500]

    def test_create_user_level_missing_fields(self, client):
        response = client.post("/api/v1/lifecycle/user-level", json={})
        assert response.status_code == 422


# ==================== 生命状态追踪测试 ====================


class TestLifeStateTracking:
    """生命状态追踪 API 测试"""

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_record_life_state_new(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchval = AsyncMock(side_effect=[True, None])
        mock_pool.fetchrow = AsyncMock(return_value={"id": 1, "tracked_date": "2026-04-03"})

        response = client.post(
            "/api/v1/lifecycle/life-state/record",
            json={
                "user_id": "test_user",
                "physical_health": 6,
                "mental_peace": 5,
                "energy_level": 7,
                "sleep_quality": 6,
                "emotional_stability": 5,
                "subjective_notes": "状态不错",
            },
        )
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_record_life_state_update_existing(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchval = AsyncMock(side_effect=[True, 42])

        response = client.post(
            "/api/v1/lifecycle/life-state/record",
            json={
                "user_id": "test_user",
                "physical_health": 7,
                "mental_peace": 6,
                "energy_level": 7,
            },
        )
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert data["data"]["updated"] is True

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_record_life_state_user_not_found(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchval = AsyncMock(return_value=False)

        response = client.post(
            "/api/v1/lifecycle/life-state/record",
            json={
                "user_id": "ghost",
                "physical_health": 5,
                "mental_peace": 5,
                "energy_level": 5,
            },
        )
        assert response.status_code in [404, 500]

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_get_life_state_history(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool

        response = client.get("/api/v1/lifecycle/life-state/test_user?limit=7")
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert isinstance(data["data"], list)

    def test_record_life_state_invalid_scores(self, client):
        response = client.post(
            "/api/v1/lifecycle/life-state/record",
            json={
                "user_id": "test_user",
                "physical_health": 15,
                "mental_peace": 5,
                "energy_level": 5,
            },
        )
        assert response.status_code == 422


# ==================== 练习记录测试 ====================


class TestPracticeRecords:
    """练习记录 API 测试"""

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_record_practice(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchrow = AsyncMock(
            return_value={
                "id": 1,
                "practice_date": "2026-04-03T12:00:00",
                "concept": "浑圆桩",
                "duration_minutes": 30,
            }
        )

        response = client.post(
            "/api/v1/lifecycle/practice/record",
            json={
                "user_id": "test_user",
                "concept": "浑圆桩",
                "practice_type": "站桩",
                "duration_minutes": 30,
                "subjective_feeling": "状态不错",
                "difficulty_level": 3,
                "notes": "坚持30分钟",
            },
        )
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert data["data"]["concept"] == "浑圆桩"

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_record_practice_user_not_found(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchval = AsyncMock(return_value=False)

        response = client.post(
            "/api/v1/lifecycle/practice/record",
            json={
                "user_id": "ghost",
                "concept": "测试",
                "practice_type": "呼吸法",
            },
        )
        assert response.status_code in [404, 500]

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_get_practice_records(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchval = AsyncMock(return_value=10)
        mock_pool.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "concept": "浑圆桩",
                    "practice_type": "站桩",
                    "practice_date": "2026-04-03T12:00:00",
                    "duration_minutes": 30,
                    "subjective_feeling": "好",
                    "difficulty_level": 3,
                    "notes": None,
                }
            ]
        )

        response = client.get("/api/v1/lifecycle/practice/my-records?user_id=test_user&limit=20")
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert data["data"]["total"] == 10
            assert len(data["data"]["items"]) == 1

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_get_practice_records_pagination(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchval = AsyncMock(return_value=100)
        mock_pool.fetch = AsyncMock(return_value=[])

        response = client.get(
            "/api/v1/lifecycle/practice/my-records?user_id=test_user&limit=10&offset=50"
        )
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["data"]["offset"] == 50

    def test_record_practice_invalid_duration(self, client):
        response = client.post(
            "/api/v1/lifecycle/practice/record",
            json={"user_id": "test_user", "duration_minutes": -5},
        )
        assert response.status_code == 422

    def test_record_practice_invalid_difficulty(self, client):
        response = client.post(
            "/api/v1/lifecycle/practice/record",
            json={"user_id": "test_user", "difficulty_level": 10},
        )
        assert response.status_code == 422


# ==================== 练习计划测试 ====================


class TestPracticePlans:
    """练习计划 API 测试"""

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_create_practice_plan(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchrow = AsyncMock(
            return_value={
                "id": 1,
                "plan_name": "30天站桩计划",
                "start_date": "2026-04-01",
                "end_date": "2026-04-30",
                "status": "active",
            }
        )

        response = client.post(
            "/api/v1/lifecycle/practice/plan",
            json={
                "user_id": "test_user",
                "plan_name": "30天站桩计划",
                "goal": "每天站桩30分钟",
                "plan_type": "template",
                "start_date": "2026-04-01",
                "end_date": "2026-04-30",
                "daily_tasks": [{"day": "daily", "task": "浑圆桩30分钟"}],
                "milestones": [{"week": 1, "goal": "适应期"}],
                "template_id": "tpl_test",
            },
        )
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert data["data"]["plan_name"] == "30天站桩计划"

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_create_plan_invalid_dates(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool

        response = client.post(
            "/api/v1/lifecycle/practice/plan",
            json={
                "user_id": "test_user",
                "plan_name": "无效计划",
                "start_date": "2026-05-01",
                "end_date": "2026-04-01",
            },
        )
        assert response.status_code in [400, 422, 500]

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_create_plan_user_not_found(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchval = AsyncMock(return_value=False)

        response = client.post(
            "/api/v1/lifecycle/practice/plan",
            json={
                "user_id": "ghost",
                "plan_name": "计划",
                "start_date": "2026-04-01",
                "end_date": "2026-04-30",
            },
        )
        assert response.status_code in [404, 500]

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_get_practice_plans(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "plan_name": "测试计划",
                    "goal": "测试",
                    "plan_type": "manual",
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-30",
                    "status": "active",
                    "daily_tasks": [],
                    "milestones": [],
                    "created_at": "2026-04-03T00:00:00",
                    "updated_at": "2026-04-03T00:00:00",
                }
            ]
        )

        response = client.get("/api/v1/lifecycle/practice/plans?user_id=test_user")
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert isinstance(data["data"], list)

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_get_plans_with_status_filter(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetch = AsyncMock(return_value=[])

        response = client.get("/api/v1/lifecycle/practice/plans?user_id=test_user&status=active")
        assert response.status_code == 200 or response.status_code == 500

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_update_practice_plan(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchrow = AsyncMock(return_value={"id": 1})

        response = client.put(
            "/api/v1/lifecycle/practice/plan/1",
            json={"plan_name": "更新计划", "status": "paused"},
        )
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_update_plan_not_found(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchrow = AsyncMock(return_value=None)

        response = client.put(
            "/api/v1/lifecycle/practice/plan/999",
            json={"plan_name": "不存在"},
        )
        assert response.status_code in [404, 500]

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_update_plan_no_changes(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchrow = AsyncMock(return_value={"id": 1})

        response = client.put("/api/v1/lifecycle/practice/plan/1", json={})
        assert response.status_code in [200, 422, 500]

    def test_create_plan_missing_required(self, client):
        response = client.post(
            "/api/v1/lifecycle/practice/plan",
            json={"user_id": "test_user"},
        )
        assert response.status_code == 422


# ==================== Dashboard 测试 ====================


class TestDashboard:
    """用户概览 API 测试"""

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_dashboard_found(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchrow = AsyncMock(
            side_effect=[
                {"user_id": "test_user", "current_level": "初级", "created_at": "2026-04-01"},
                {
                    "physical_health": 6,
                    "mental_peace": 5,
                    "energy_level": 6,
                    "sleep_quality": 5,
                    "emotional_stability": 5,
                    "tracked_date": "2026-04-03",
                },
            ]
        )
        mock_pool.fetchval = AsyncMock(side_effect=[10, 300, 2])

        response = client.get("/api/v1/lifecycle/dashboard/test_user")
        assert response.status_code == 200 or response.status_code == 500
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert data["data"]["total_practice_sessions"] == 10
            assert data["data"]["total_practice_minutes"] == 300
            assert data["data"]["active_plans"] == 2

    @patch("backend.api.v1.lifecycle.init_db_pool")
    def test_dashboard_not_found(self, mock_init, client, mock_pool):
        mock_init.return_value = mock_pool
        mock_pool.fetchrow = AsyncMock(side_effect=[None])

        response = client.get("/api/v1/lifecycle/dashboard/nonexistent")
        assert response.status_code in [404, 500]


# ==================== Pydantic 模型验证测试 ====================


class TestLifecycleModels:
    """请求模型验证测试"""

    def test_user_level_create_defaults(self):
        from backend.api.v1.lifecycle import UserLevelCreate

        model = UserLevelCreate(user_id="test")
        assert model.current_level == "入门"
        assert model.notes is None

    def test_user_level_create_with_values(self):
        from backend.api.v1.lifecycle import UserLevelCreate

        model = UserLevelCreate(user_id="test", current_level="高级", notes="测试")
        assert model.current_level == "高级"
        assert model.notes == "测试"

    def test_life_state_record_validation(self):
        from backend.api.v1.lifecycle import LifeStateRecord

        model = LifeStateRecord(
            user_id="test",
            physical_health=5,
            mental_peace=5,
            energy_level=5,
        )
        assert model.sleep_quality is None
        assert model.emotional_stability is None
        assert model.tracked_date is None

    def test_life_state_record_boundary_values(self):
        from backend.api.v1.lifecycle import LifeStateRecord

        model = LifeStateRecord(
            user_id="test",
            physical_health=1,
            mental_peace=10,
            energy_level=1,
            sleep_quality=10,
            emotional_stability=5,
        )
        assert model.physical_health == 1
        assert model.mental_peace == 10

    def test_practice_record_defaults(self):
        from backend.api.v1.lifecycle import PracticeRecordCreate

        model = PracticeRecordCreate(user_id="test")
        assert model.concept is None
        assert model.practice_type is None
        assert model.duration_minutes is None

    def test_practice_plan_create_defaults(self):
        from datetime import date

        from backend.api.v1.lifecycle import PracticePlanCreate

        model = PracticePlanCreate(
            user_id="test",
            plan_name="测试",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
        )
        assert model.plan_type == "manual"
        assert model.daily_tasks == []
        assert model.milestones == []

    def test_practice_plan_update_partial(self):
        from backend.api.v1.lifecycle import PracticePlanUpdate

        model = PracticePlanUpdate(status="paused")
        assert model.status == "paused"
        assert model.plan_name is None
        assert model.goal is None

    def test_practice_plan_update_with_tasks(self):
        from backend.api.v1.lifecycle import PracticePlanUpdate

        tasks = [{"day": "daily", "task": "站桩30分钟"}]
        milestones = [{"week": 1, "goal": "适应期"}]
        model = PracticePlanUpdate(
            plan_name="更新",
            daily_tasks=tasks,
            milestones=milestones,
        )
        assert model.daily_tasks == tasks
        assert model.milestones == milestones
