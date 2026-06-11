import time

import pytest

from backend.monitoring.anomaly_detector import (
    Alert,
    AlertLevel,
    AnomalyDetector,
    ThresholdRule,
    get_anomaly_detector,
)


class TestThresholdRule:
    def test_defaults(self):
        rule = ThresholdRule(
            name="test",
            metric="latency_ms",
            warning_threshold=100.0,
            critical_threshold=500.0,
        )
        assert rule.window_seconds == 60.0
        assert rule.min_samples == 3


class TestAlert:
    def test_to_dict(self):
        alert = Alert(
            level=AlertLevel.WARNING,
            rule_name="test_rule",
            message="high latency",
            value=250.0,
            threshold=100.0,
        )
        d = alert.to_dict()
        assert d["level"] == "warning"
        assert d["rule_name"] == "test_rule"
        assert d["value"] == 250.0

    def test_critical_to_dict(self):
        alert = Alert(
            level=AlertLevel.CRITICAL,
            rule_name="disk",
            message="disk full",
            value=96.0,
            threshold=95.0,
        )
        assert alert.to_dict()["level"] == "critical"


class TestAnomalyDetector:
    def test_add_remove_rule(self):
        det = AnomalyDetector()
        rule = ThresholdRule("r1", "latency", 100, 500)
        det.add_rule(rule)
        assert "r1" in det._rules
        det.remove_rule("r1")
        assert "r1" not in det._rules

    def test_observe_stores_samples(self):
        det = AnomalyDetector()
        rule = ThresholdRule("r1", "latency_ms", 100, 500, min_samples=2)
        det.add_rule(rule)
        det.observe("latency_ms", 50)
        det.observe("latency_ms", 80)
        assert len(det._buffers["r1"]) == 2

    def test_no_alert_below_threshold(self):
        det = AnomalyDetector()
        rule = ThresholdRule("r1", "latency_ms", 100, 500, min_samples=1)
        det.add_rule(rule)
        det.observe("latency_ms", 50)
        assert det.check_rule("r1") is None

    def test_warning_alert(self):
        det = AnomalyDetector()
        rule = ThresholdRule("r1", "latency_ms", 100, 500, min_samples=1)
        det.add_rule(rule)
        det.observe("latency_ms", 150)
        alert = det.check_rule("r1")
        assert alert is not None
        assert alert.level == AlertLevel.WARNING

    def test_critical_alert(self):
        det = AnomalyDetector()
        rule = ThresholdRule("r1", "latency_ms", 100, 500, min_samples=1)
        det.add_rule(rule)
        det.observe("latency_ms", 600)
        alert = det.check_rule("r1")
        assert alert is not None
        assert alert.level == AlertLevel.CRITICAL

    def test_insufficient_samples(self):
        det = AnomalyDetector()
        rule = ThresholdRule("r1", "latency_ms", 100, 500, min_samples=5)
        det.add_rule(rule)
        for _ in range(3):
            det.observe("latency_ms", 600)
        assert det.check_rule("r1") is None

    def test_window_expiry(self):
        det = AnomalyDetector()
        rule = ThresholdRule("r1", "latency_ms", 100, 500, window_seconds=0.1, min_samples=1)
        det.add_rule(rule)
        det.observe("latency_ms", 600)
        time.sleep(0.15)
        assert det.check_rule("r1") is None

    def test_wrong_metric_ignored(self):
        det = AnomalyDetector()
        rule = ThresholdRule("r1", "latency_ms", 100, 500, min_samples=1)
        det.add_rule(rule)
        det.observe("other_metric", 600)
        assert det.check_rule("r1") is None

    def test_nonexistent_rule(self):
        det = AnomalyDetector()
        assert det.check_rule("nope") is None

    @pytest.mark.asyncio
    async def test_callback_fired(self):
        det = AnomalyDetector()
        rule = ThresholdRule("r1", "latency_ms", 100, 500, min_samples=1)
        det.add_rule(rule)
        received = []
        det.add_callback(lambda a: received.append(a))
        det.observe("latency_ms", 600)
        alerts = await det.check_all()
        assert len(alerts) == 1
        assert len(received) == 1
        assert received[0].level == AlertLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_no_duplicate_alert(self):
        det = AnomalyDetector()
        rule = ThresholdRule("r1", "latency_ms", 100, 500, min_samples=1)
        det.add_rule(rule)
        det.observe("latency_ms", 600)
        await det.check_all()
        det.observe("latency_ms", 700)
        alerts = await det.check_all()
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_recovery_clears_alert(self):
        det = AnomalyDetector()
        rule = ThresholdRule("r1", "latency_ms", 100, 500, window_seconds=0.1, min_samples=1)
        det.add_rule(rule)
        det.observe("latency_ms", 600)
        await det.check_all()
        assert "r1" in det.get_active_alerts()
        time.sleep(0.15)
        det.observe("latency_ms", 50)
        det.check_rule("r1")
        assert "r1" not in det.get_active_alerts()

    def test_get_status_healthy(self):
        det = AnomalyDetector()
        status = det.get_status()
        assert status["status"] == "healthy"
        assert status["running"] is False

    def test_get_status_with_active_warning(self):
        det = AnomalyDetector()
        det._active_alerts["r1"] = Alert(
            level=AlertLevel.WARNING, rule_name="r1", message="test", value=1, threshold=0
        )
        assert det.get_status()["status"] == "degraded"

    def test_get_status_with_active_critical(self):
        det = AnomalyDetector()
        det._active_alerts["r1"] = Alert(
            level=AlertLevel.CRITICAL, rule_name="r1", message="test", value=1, threshold=0
        )
        assert det.get_status()["status"] == "unhealthy"

    def test_get_history(self):
        det = AnomalyDetector()
        det._alert_history.append(
            Alert(level=AlertLevel.WARNING, rule_name="r1", message="a", value=1, threshold=0)
        )
        det._alert_history.append(
            Alert(level=AlertLevel.CRITICAL, rule_name="r2", message="b", value=2, threshold=0)
        )
        assert len(det.get_history()) == 2
        assert len(det.get_history(limit=1)) == 1


class TestGetAnomalyDetector:
    def test_singleton(self):
        d1 = get_anomaly_detector()
        d2 = get_anomaly_detector()
        assert d1 is d2

    def test_default_rules_loaded(self):
        det = get_anomaly_detector()
        assert "search_latency" in det._rules
        assert "http_429_rate" in det._rules
        assert "disk_usage_pct" in det._rules
