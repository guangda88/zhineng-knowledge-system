"""配置模块测试

覆盖: BaseConfig, DatabaseConfig, RedisConfig, SecurityConfig
"""

import os

import pytest


class TestBaseConfig:
    """基础配置测试"""

    def test_config_import(self):
        from backend.config import get_config

        config = get_config()
        assert config is not None

    def test_config_singleton(self):
        from backend.config import get_config

        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_config_has_api_settings(self):
        from backend.config import get_config

        config = get_config()
        assert hasattr(config, "API_HOST")
        assert hasattr(config, "API_PORT")

    def test_config_has_categories(self):
        from backend.config import get_config

        config = get_config()
        assert hasattr(config, "VALID_CATEGORIES")

    def test_config_environment(self):
        from backend.config import get_config

        config = get_config()
        assert config.ENVIRONMENT in ("development", "testing", "production", "test")

    def test_config_log_level(self):
        from backend.config import get_config

        config = get_config()
        assert hasattr(config, "LOG_LEVEL")


class TestDatabaseConfig:
    """数据库配置测试"""

    def test_database_config_import(self):
        from backend.config.database import DatabaseConfig

        dc = DatabaseConfig()
        assert dc is not None

    def test_database_url_from_env(self):
        from backend.config.database import DatabaseConfig

        dc = DatabaseConfig()
        url = os.environ.get("DATABASE_URL", "")
        if url:
            assert hasattr(dc, "database_url") or hasattr(dc, "DATABASE_URL")


class TestRedisConfig:
    """Redis配置测试"""

    def test_redis_config_import(self):
        from backend.config.redis import RedisConfig

        rc = RedisConfig()
        assert rc is not None


class TestSecurityConfig:
    """安全配置测试"""

    def test_security_config_import(self):
        from backend.config.security import SecurityConfig

        sc = SecurityConfig()
        assert sc is not None

    def test_security_has_jwt_settings(self):
        from backend.config.security import SecurityConfig

        sc = SecurityConfig()
        assert hasattr(sc, "jwt_algorithm") or hasattr(sc, "JWT_ALGORITHM")


class TestConfigModule:
    """配置模块结构测试"""

    def test_config_init_exports(self):
        import backend.config as config_module

        assert hasattr(config_module, "get_config")

    def test_config_creates_instance(self):
        from backend.config import Config

        assert Config is not None
