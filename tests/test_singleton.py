"""Tests for backend.common.singleton — async_singleton decorator and sentinel fix"""

import asyncio
import sys
import types

import pytest

from backend.common.singleton import _INIT_FAILED_SENTINEL


def _make_module(name: str, var_name: str):
    module = types.ModuleType(name)
    setattr(module, var_name, None)
    sys.modules[name] = module
    return module


def _cleanup_module(name: str):
    sys.modules.pop(name, None)


class TestAsyncSingletonBasic:
    """Test basic singleton creation and caching"""

    def test_creates_and_caches_instance(self):
        name = "test_singleton_mod_a"
        var = "_svc_a"
        _make_module(name, var)

        # Define the function in the module context
        code = """
import asyncio
from backend.common.singleton import async_singleton

@async_singleton("_svc_a")
async def get_svc():
    return {"id": 1}
"""
        exec(code, sys.modules[name].__dict__)

        get_svc = sys.modules[name].__dict__["get_svc"]
        result = asyncio.run(get_svc())
        assert result == {"id": 1}

        r2 = asyncio.run(get_svc())
        assert r2 is result  # same cached instance

        _cleanup_module(name)


class TestAsyncSingletonFailureSentinel:
    """Test that _INIT_FAILED_SENTINEL is properly handled"""

    def test_failed_init_sets_sentinel(self):
        name = "test_singleton_mod_fail"
        var = "_fail_svc"
        _make_module(name, var)

        code = """
from backend.common.singleton import async_singleton

@async_singleton("_fail_svc")
async def get_fail_svc():
    raise ConnectionError("DB down")
"""
        exec(code, sys.modules[name].__dict__)

        get_fail_svc = sys.modules[name].__dict__["get_fail_svc"]

        with pytest.raises(ConnectionError, match="DB down"):
            asyncio.run(get_fail_svc())

        assert getattr(sys.modules[name], var) is _INIT_FAILED_SENTINEL

        _cleanup_module(name)

    def test_failed_init_raises_runtime_on_retry(self):
        name = "test_singleton_mod_retry"
        var = "_retry_svc"
        _make_module(name, var)

        code = """
from backend.common.singleton import async_singleton

@async_singleton("_retry_svc")
async def get_retry_svc():
    raise ValueError("init error")
"""
        exec(code, sys.modules[name].__dict__)

        get_retry_svc = sys.modules[name].__dict__["get_retry_svc"]

        with pytest.raises(ValueError):
            asyncio.run(get_retry_svc())

        with pytest.raises(RuntimeError, match="previously failed"):
            asyncio.run(get_retry_svc())

        _cleanup_module(name)

    def test_sentinel_not_returned_on_fast_path(self):
        name = "test_singleton_mod_fast"
        var = "_fast_svc"
        _make_module(name, var)

        code = """
from backend.common.singleton import async_singleton

@async_singleton("_fast_svc")
async def get_fast_svc():
    raise RuntimeError("boom")
"""
        exec(code, sys.modules[name].__dict__)

        get_fast_svc = sys.modules[name].__dict__["get_fast_svc"]

        with pytest.raises(RuntimeError, match="boom"):
            asyncio.run(get_fast_svc())

        with pytest.raises(RuntimeError, match="previously failed"):
            asyncio.run(get_fast_svc())

        _cleanup_module(name)


class TestAsyncSingletonWithInitFunc:
    """Test async_singleton with custom init_func"""

    def test_uses_init_func_when_provided(self):
        name = "test_singleton_mod_init"
        var = "_init_svc"
        _make_module(name, var)

        code = """
from backend.common.singleton import async_singleton

async def custom_init():
    return {"custom": True}

@async_singleton("_init_svc", init_func=custom_init)
async def get_init_svc():
    return {"custom": False}
"""
        exec(code, sys.modules[name].__dict__)

        get_init_svc = sys.modules[name].__dict__["get_init_svc"]
        result = asyncio.run(get_init_svc())
        assert result == {"custom": True}

        _cleanup_module(name)
