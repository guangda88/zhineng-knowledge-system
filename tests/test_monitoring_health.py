"""Tests for backend.monitoring.health — HealthChecker"""

import pytest

from backend.monitoring.health import HealthChecker, HealthCheckResult, HealthStatus


class TestHealthStatus:
    """Test HealthStatus enum"""

    def test_values(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestHealthCheckResult:
    """Test HealthCheckResult dataclass"""

    def test_to_dict(self):
        result = HealthCheckResult(name="db", status=HealthStatus.HEALTHY, message="OK")
        d = result.to_dict()
        assert d["name"] == "db"
        assert d["status"] == "healthy"

    def test_default_values(self):
        result = HealthCheckResult(name="test", status=HealthStatus.UNKNOWN)
        assert result.message == ""
        assert result.details == {}
        assert result.duration == 0.0


class TestHealthChecker:
    """Test HealthChecker"""

    def test_init(self):
        checker = HealthChecker()
        assert checker is not None

    @pytest.mark.asyncio
    async def test_check_unknown_name(self):
        checker = HealthChecker()
        result = await checker.check("nonexistent")
        assert isinstance(result, HealthCheckResult)
        assert result.name == "nonexistent"
