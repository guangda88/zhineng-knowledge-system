"""Tests for backend.config modules — Pydantic V2 model_config validation"""
import os
import pytest

from backend.config.base import BaseConfig
from backend.config.database import DatabaseConfig
from backend.config.redis import RedisConfig


class TestBaseConfigV2:
    """Test BaseConfig uses Pydantic V2 model_config"""

    def test_model_config_is_dict(self):
        assert isinstance(BaseConfig.model_config, dict)

    def test_model_config_has_env_file(self):
        assert BaseConfig.model_config.get("env_file") == ".env"

    def test_model_config_case_sensitive(self):
        assert BaseConfig.model_config.get("case_sensitive") is True

    def test_model_config_extra_ignore(self):
        assert BaseConfig.model_config.get("extra") == "ignore"

    def test_instantiation_with_defaults(self):
        cfg = BaseConfig()
        assert cfg.ENVIRONMENT in ("development", "test", "production")

    def test_deepseek_defaults(self):
        cfg = BaseConfig()
        assert cfg.DEEPSEEK_MODEL == "deepseek-chat"


class TestDatabaseConfigV2:
    """Test DatabaseConfig uses Pydantic V2 model_config"""

    def test_model_config_is_dict(self):
        assert isinstance(DatabaseConfig.model_config, dict)

    def test_model_config_has_env_file(self):
        assert DatabaseConfig.model_config.get("env_file") == ".env"

    def test_instantiation_with_defaults(self):
        cfg = DatabaseConfig()
        assert cfg.DB_POOL_SIZE > 0
        assert cfg.QUERY_TIMEOUT > 0


class TestRedisConfigV2:
    """Test RedisConfig uses Pydantic V2 model_config"""

    def test_model_config_is_dict(self):
        assert isinstance(RedisConfig.model_config, dict)

    def test_model_config_has_env_file(self):
        assert RedisConfig.model_config.get("env_file") == ".env"

    def test_instantiation_with_defaults(self):
        cfg = RedisConfig()
        assert cfg.REDIS_HOST == "localhost"
        assert cfg.REDIS_PORT == 6379

    def test_get_redis_url_without_password(self):
        cfg = RedisConfig()
        cfg.REDIS_PASSWORD = ""
        url = cfg.get_redis_url()
        assert url == "redis://localhost:6379/0"

    def test_get_redis_url_with_password(self):
        cfg = RedisConfig()
        cfg.REDIS_PASSWORD = "secret"
        url = cfg.get_redis_url()
        assert ":secret@" in url
