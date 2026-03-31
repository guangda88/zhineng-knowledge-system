"""Tests for backend.common.db_helpers"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.common.db_helpers import (
    row_to_dict,
    rows_to_list,
    fetch_one_or_404,
    fetch_paginated,
    _validate_paginated_query,
    check_database_health,
)


class TestRowToDict:
    """Test row_to_dict conversion"""

    def test_converts_dict_like_to_dict(self):
        mock_record = {"id": 1, "name": "test"}
        result = row_to_dict(mock_record)
        assert result == {"id": 1, "name": "test"}

    def test_preserves_all_keys(self):
        mock_record = {"a": 1, "b": 2, "c": 3}
        result = row_to_dict(mock_record)
        assert len(result) == 3


class TestRowsToList:
    """Test rows_to_list conversion"""

    def test_converts_list_of_dicts(self):
        rows = [{"id": 1}, {"id": 2}]
        result = rows_to_list(rows)
        assert result == [{"id": 1}, {"id": 2}]

    def test_returns_empty_list_for_empty_input(self):
        assert rows_to_list([]) == []


class TestFetchOneOr404:
    """Test fetch_one_or_404"""

    @pytest.mark.asyncio
    async def test_returns_record_when_found(self):
        mock_pool = AsyncMock()
        mock_pool.fetchrow = AsyncMock(return_value={"id": 1, "title": "Test"})

        result = await fetch_one_or_404(mock_pool, "SELECT * FROM t WHERE id=$1", 1)
        assert result == {"id": 1, "title": "Test"}

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self):
        from fastapi import HTTPException

        mock_pool = AsyncMock()
        mock_pool.fetchrow = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await fetch_one_or_404(mock_pool, "SELECT * FROM t WHERE id=$1", 999)
        assert exc_info.value.status_code == 404


class TestValidatePaginatedQuery:
    """Test SQL validation for paginated queries"""

    def test_valid_select_passes(self):
        _validate_paginated_query("SELECT id FROM documents")

    def test_non_select_fails(self):
        with pytest.raises(ValueError, match="SELECT"):
            _validate_paginated_query("DELETE FROM documents")

    def test_dangerous_keyword_fails(self):
        with pytest.raises(ValueError, match="DROP"):
            _validate_paginated_query("SELECT id, DROP TABLE FROM t")


class TestFetchPaginated:
    """Test fetch_paginated"""

    @pytest.mark.asyncio
    async def test_returns_paginated_result(self):
        mock_pool = AsyncMock()
        mock_pool.fetchval = AsyncMock(return_value=10)
        mock_pool.fetch = AsyncMock(return_value=[{"id": 1}, {"id": 2}])

        result = await fetch_paginated(mock_pool, "SELECT id FROM t", limit=2, offset=0)
        assert result["total"] == 10
        assert result["limit"] == 2
        assert result["offset"] == 0
        assert len(result["results"]) == 2


class TestCheckDatabaseHealth:
    """Test check_database_health"""

    @pytest.mark.asyncio
    async def test_returns_degraded_on_failure(self):
        mock_pool = AsyncMock()
        mock_pool.acquire = AsyncMock(side_effect=Exception("Connection refused"))

        result = await check_database_health(mock_pool)
        assert result["status"] == "degraded"
