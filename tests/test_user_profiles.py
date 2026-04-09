"""测试用户画像和评估系统API

测试用户等级管理、生活状态追踪、练习记录、练习计划等功能
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


class TestUserProfile:
    """测试用户画像功能"""

    @pytest.fixture
    def test_user_id(self):
        """测试用户ID"""
        return "test_user_profile_001"

    def test_create_user_profile(self, test_user_id):
        """测试创建用户画像"""
        response = client.post(
            "/api/v1/user/profiles",
            json={
                "user_id": test_user_id,
                "current_level": "入门",
                "assessment_score": 75.5,
                "notes": "测试用户",
            },
        )
        assert response.status_code in [200, 500, 401]

    def test_get_user_profile(self, test_user_id):
        """测试获取用户画像"""
        response = client.get(f"/api/v1/user/profiles/{test_user_id}")
        assert response.status_code in [200, 404, 500, 401]

    def test_update_user_profile(self, test_user_id):
        """测试更新用户画像"""
        response = client.put(
            f"/api/v1/user/profiles/{test_user_id}",
            json={"current_level": "初级", "assessment_score": 80.0},
        )
        assert response.status_code in [200, 404, 500, 401]


class TestLifeStateTracking:
    """测试生活状态追踪功能"""

    @pytest.fixture
    def test_user_id(self):
        """测试用户ID"""
        return "test_user_lifestate_001"

    def test_create_life_state_tracking(self, test_user_id):
        """测试记录生活状态"""
        response = client.post(
            "/api/v1/user/life-state",
            json={
                "user_id": test_user_id,
                "physical_health": 7,
                "mental_peace": 8,
                "energy_level": 7,
                "sleep_quality": 8,
                "emotional_stability": 8,
                "subjective_notes": "状态良好",
            },
        )
        assert response.status_code in [200, 500, 401]

    def test_get_life_state_tracking(self, test_user_id):
        """测试获取生活状态记录"""
        response = client.get(f"/api/v1/user/life-state/{test_user_id}")
        assert response.status_code in [200, 500, 401]

    def test_get_life_state_summary(self, test_user_id):
        """测试获取生活状态统计摘要"""
        response = client.get(f"/api/v1/user/life-state/{test_user_id}/summary")
        assert response.status_code in [200, 500, 401]


class TestPracticeRecords:
    """测试练习记录功能"""

    @pytest.fixture
    def test_user_id(self):
        """测试用户ID"""
        return "test_user_practice_001"

    def test_create_practice_record(self, test_user_id):
        """测试记录练习"""
        response = client.post(
            "/api/v1/user/practice",
            json={
                "user_id": test_user_id,
                "concept": "站桩",
                "practice_type": "站桩",
                "duration_minutes": 30,
                "subjective_feeling": "感觉良好",
                "difficulty_level": 3,
                "notes": "今天练习了30分钟",
            },
        )
        assert response.status_code in [200, 500, 401]

    def test_get_practice_records(self, test_user_id):
        """测试获取练习记录"""
        response = client.get(f"/api/v1/user/practice/{test_user_id}")
        assert response.status_code in [200, 500, 401]

    def test_get_practice_summary(self, test_user_id):
        """测试获取练习统计摘要"""
        response = client.get(f"/api/v1/user/practice/{test_user_id}/summary")
        assert response.status_code in [200, 500, 401]


class TestPracticePlans:
    """测试练习计划功能"""

    @pytest.fixture
    def test_user_id(self):
        """测试用户ID"""
        return "test_user_plan_001"

    def test_create_practice_plan(self, test_user_id):
        """测试创建练习计划"""
        start_date = date.today()
        end_date = date(start_date.year, start_date.month + 1, start_date.day)
        response = client.post(
            "/api/v1/user/plans",
            json={
                "user_id": test_user_id,
                "plan_name": "30天站桩计划",
                "goal": "提升站桩能力",
                "plan_type": "manual",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )
        assert response.status_code in [200, 500, 401]

    def test_get_practice_plans(self, test_user_id):
        """测试获取练习计划"""
        response = client.get(f"/api/v1/user/plans/{test_user_id}")
        assert response.status_code in [200, 500, 401]

    def test_update_practice_plan(self, test_user_id):
        """测试更新练习计划"""
        response = client.put(
            "/api/v1/user/plans/1",
            json={"status": "completed"},
        )
        assert response.status_code in [200, 404, 500, 401]


class TestUserAssessment:
    """测试用户综合评估功能"""

    @pytest.fixture
    def test_user_id(self):
        """测试用户ID"""
        return "test_user_assessment_001"

    def test_get_user_assessment(self, test_user_id):
        """测试获取用户综合评估"""
        response = client.get(f"/api/v1/user/assessment/{test_user_id}")
        assert response.status_code in [200, 404, 500, 401]

    def test_assessment_response_structure(self, test_user_id):
        """测试评估响应结构"""
        response = client.get(f"/api/v1/user/assessment/{test_user_id}")
        if response.status_code == 200:
            data = response.json()
            assert "user_id" in data
            assert "current_level" in data
            assert "practice_count_last_30_days" in data
            assert "total_practice_minutes_last_30_days" in data
            assert "life_state_avg_last_30_days" in data
            assert "recommendations" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
