"""Tests for backend.common.rate_limiter — DistributedRateLimiter"""

from unittest.mock import MagicMock, patch

from backend.common.rate_limiter import DistributedRateLimiter


class TestDistributedRateLimiterInit:
    """Test limiter initialization"""

    @patch("backend.common.rate_limiter._get_sync_redis")
    def test_init_sets_defaults(self, mock_redis):
        mock_redis.return_value = MagicMock()
        limiter = DistributedRateLimiter()
        assert limiter.max_calls == 60
        assert limiter.period == 60
        assert limiter.burst == 10

    @patch("backend.common.rate_limiter._get_sync_redis")
    def test_init_custom_params(self, mock_redis):
        mock_redis.return_value = MagicMock()
        limiter = DistributedRateLimiter(max_calls=100, period=120, burst=20)
        assert limiter.max_calls == 100
        assert limiter.period == 120
        assert limiter.burst == 20


class TestGetUsage:
    """Test get_usage method"""

    @patch("backend.common.rate_limiter._get_sync_redis")
    def test_get_usage_with_active_calls(self, mock_redis):
        mock_conn = MagicMock()
        mock_conn.get.return_value = b"30"
        mock_conn.ttl.return_value = 45
        mock_redis.return_value = mock_conn

        limiter = DistributedRateLimiter()
        usage = limiter.get_usage("test_key")
        assert usage["current_calls"] == 30
        assert usage["max_calls"] == 60
        assert usage["usage_percent"] == 50.0

    @patch("backend.common.rate_limiter._get_sync_redis")
    def test_get_usage_no_active_calls(self, mock_redis):
        mock_conn = MagicMock()
        mock_conn.get.return_value = None
        mock_redis.return_value = mock_conn

        limiter = DistributedRateLimiter()
        usage = limiter.get_usage("test_key")
        assert usage["current_calls"] == 0
        assert usage["usage_percent"] == 0

    @patch("backend.common.rate_limiter._get_sync_redis")
    def test_get_usage_at_max(self, mock_redis):
        mock_conn = MagicMock()
        mock_conn.get.return_value = b"60"
        mock_conn.ttl.return_value = 30
        mock_redis.return_value = mock_conn

        limiter = DistributedRateLimiter()
        usage = limiter.get_usage("test_key")
        assert usage["current_calls"] == 60
        assert usage["usage_percent"] == 100.0
