"""限流器 IP 获取逻辑测试

验证 RateLimitMiddleware 的可信代理逻辑，
确保攻击者不能通过伪造 X-Forwarded-For 绕过限流。
"""

import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from fastapi import FastAPI, Request
from starlette.testclient import TestClient
from backend.middleware.rate_limit import RateLimitMiddleware


def _get_ip(app, headers=None):
    captured = {}

    @app.get("/test")
    async def handler(request: Request):
        mw = RateLimitMiddleware(app)
        captured["ip"] = mw._get_client_ip(request)
        return {"ip": captured["ip"]}

    client = TestClient(app)
    client.get("/test", headers=headers or {})
    return captured.get("ip")


class TestIPNoTrustedProxies:
    def test_ignores_x_forwarded_for(self):
        assert _get_ip(FastAPI(), {"X-Forwarded-For": "9.9.9.9"}) == "testclient"

    def test_ignores_x_real_ip(self):
        assert _get_ip(FastAPI(), {"X-Real-IP": "8.8.8.8"}) == "testclient"

    def test_uses_direct_ip(self):
        assert _get_ip(FastAPI()) == "testclient"


class TestIPWithTrustedProxies:
    def _with_env(self, value, func):
        os.environ["TRUSTED_PROXIES"] = value
        try:
            return func()
        finally:
            del os.environ["TRUSTED_PROXIES"]

    def test_reads_x_forwarded_for_from_trusted(self):
        def check():
            return _get_ip(FastAPI(), {"X-Forwarded-For": "9.9.9.9"})
        assert self._with_env("testclient", check) == "9.9.9.9"

    def test_reads_x_real_ip_from_trusted(self):
        def check():
            return _get_ip(FastAPI(), {"X-Real-IP": "8.8.8.8"})
        assert self._with_env("testclient", check) == "8.8.8.8"

    def test_ignores_headers_from_untrusted(self):
        def check():
            return _get_ip(FastAPI(), {"X-Forwarded-For": "9.9.9.9"})
        assert self._with_env("10.0.0.1", check) == "testclient"

    def test_multiple_trusted_proxies(self):
        def check():
            return _get_ip(FastAPI(), {"X-Forwarded-For": "7.7.7.7"})
        assert self._with_env("10.0.0.1,testclient,10.0.0.2", check) == "7.7.7.7"


class TestXForwardedForParsing:
    def _with_env(self, func):
        os.environ["TRUSTED_PROXIES"] = "testclient"
        try:
            return func()
        finally:
            del os.environ["TRUSTED_PROXIES"]

    def test_takes_first_ip(self):
        def check():
            return _get_ip(FastAPI(), {"X-Forwarded-For": "1.1.1.1, 2.2.2.2, 3.3.3.3"})
        assert self._with_env(check) == "1.1.1.1"

    def test_strips_whitespace(self):
        def check():
            return _get_ip(FastAPI(), {"X-Forwarded-For": "  1.1.1.1  "})
        assert self._with_env(check) == "1.1.1.1"
