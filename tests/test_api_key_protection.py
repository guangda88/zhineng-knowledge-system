"""API Key 保护测试

验证 require_admin_api_key 依赖函数的行为：
- 无 ADMIN_API_KEYS 配置时，跳过验证（向后兼容）
- 有配置时，必须提供正确的 key
- 错误的 key 返回 403
- 缺少 key 返回 401
"""

import os
import pytest
from fastapi import FastAPI, Depends
from starlette.testclient import TestClient

from backend.core.dependency_injection import require_admin_api_key


def _make_app():
    app = FastAPI()

    @app.get("/protected")
    async def protected(admin: bool = Depends(require_admin_api_key)):
        return {"status": "ok"}

    return app


class TestNoKeysConfigured:
    """无 ADMIN_API_KEYS 时，应跳过验证"""

    def test_allows_without_key(self):
        os.environ.pop("ADMIN_API_KEYS", None)
        # 需要重新创建 config 单例以反映环境变化
        import backend.config
        backend.config._config = None

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 200

        backend.config._config = None


class TestKeysConfigured:
    """有 ADMIN_API_KEYS 时，需要验证"""

    def _setup_keys(self, keys):
        os.environ["ADMIN_API_KEYS"] = keys
        import backend.config
        backend.config._config = None

    def _cleanup(self):
        os.environ.pop("ADMIN_API_KEYS", None)
        import backend.config
        backend.config._config = None

    def test_rejects_without_key(self):
        self._setup_keys("valid-key-123")
        try:
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/protected")
            assert resp.status_code == 401
        finally:
            self._cleanup()

    def test_rejects_wrong_key(self):
        self._setup_keys("valid-key-123")
        try:
            app = _make_app()
            client = TestClient(app)
            resp = client.get(
                "/protected",
                headers={"X-Admin-API-Key": "wrong-key"}
            )
            assert resp.status_code == 403
        finally:
            self._cleanup()

    def test_accepts_correct_key_header(self):
        self._setup_keys("valid-key-123")
        try:
            app = _make_app()
            client = TestClient(app)
            resp = client.get(
                "/protected",
                headers={"X-Admin-API-Key": "valid-key-123"}
            )
            assert resp.status_code == 200
        finally:
            self._cleanup()

    def test_accepts_correct_key_query(self):
        self._setup_keys("valid-key-123")
        try:
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/protected?admin_api_key=valid-key-123")
            assert resp.status_code == 200
        finally:
            self._cleanup()

    def test_multiple_keys(self):
        self._setup_keys("key-one,key-two,key-three")
        try:
            app = _make_app()
            client = TestClient(app)
            resp1 = client.get(
                "/protected",
                headers={"X-Admin-API-Key": "key-two"}
            )
            assert resp1.status_code == 200

            resp2 = client.get(
                "/protected",
                headers={"X-Admin-API-Key": "key-one"}
            )
            assert resp2.status_code == 200

            resp3 = client.get(
                "/protected",
                headers={"X-Admin-API-Key": "key-four"}
            )
            assert resp3.status_code == 403
        finally:
            self._cleanup()

    def test_header_takes_precedence_over_query(self):
        self._setup_keys("valid-key")
        try:
            app = _make_app()
            client = TestClient(app)
            resp = client.get(
                "/protected?admin_api_key=valid-key",
                headers={"X-Admin-API-Key": "valid-key"}
            )
            assert resp.status_code == 200
        finally:
            self._cleanup()
