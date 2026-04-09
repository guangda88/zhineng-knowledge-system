"""通用工具测试

覆盖: db_helpers, singleton, typing utilities
"""

from unittest.mock import MagicMock


class TestDbHelpers:
    """数据库工具函数测试"""

    def test_import_db_helpers(self):
        from backend.common.db_helpers import require_pool, row_to_dict

        assert callable(require_pool)
        assert callable(row_to_dict)

    def test_row_to_dict_with_mapping(self):
        from backend.common.db_helpers import row_to_dict

        mock_row = {"id": 1, "name": "test", "value": 42}
        result = row_to_dict(mock_row)
        assert result == {"id": 1, "name": "test", "value": 42}

    def test_row_to_dict_with_record(self):
        from backend.common.db_helpers import row_to_dict

        mock_record = MagicMock()
        mock_record.keys.return_value = ["id", "name"]
        mock_record.__getitem__ = lambda self, key: {"id": 1, "name": "test"}[key]
        result = row_to_dict(mock_record)
        assert isinstance(result, dict)

    def test_import_fetch_helpers(self):
        from backend.common.db_helpers import fetch_one_or_404, fetch_paginated

        assert callable(fetch_one_or_404)
        assert callable(fetch_paginated)


class TestSingleton:
    """单例模式测试"""

    def test_singleton_import(self):
        from backend.common.singleton import async_singleton

        assert callable(async_singleton)

    def test_async_singleton_decorator(self):
        import asyncio

        from backend.common.singleton import async_singleton

        _thing_instance = None

        @async_singleton("_thing_instance")
        async def get_thing():
            nonlocal _thing_instance
            if _thing_instance is None:
                _thing_instance = "result"
            return _thing_instance

        async def run():
            r1 = await get_thing()
            r2 = await get_thing()
            assert r1 == r2 == "result"

        asyncio.run(run())


class TestTyping:
    """类型工具测试"""

    def test_typing_import(self):
        from backend.common.typing import APIResult, SearchResult

        assert APIResult is not None
        assert SearchResult is not None
