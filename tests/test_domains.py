"""Tests for backend.domains modules — domain creation and dead code removal verification"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.domains.qigong import QigongDomain
from backend.domains.tcm import TcmDomain
from backend.domains.confucian import ConfucianDomain
from backend.domains.general import GeneralDomain
from backend.domains.base import BaseDomain, DomainConfig, DomainType


class TestQigongDomainDeadCodeRemoved:
    """Verify dead methods were removed from QigongDomain"""

    def test_no_get_practice_tips(self):
        assert not hasattr(QigongDomain, "get_practice_tips"), \
            "get_practice_tips should have been removed (dead code)"

    def test_no_get_related_exercises(self):
        assert not hasattr(QigongDomain, "get_related_exercises"), \
            "get_related_exercises should have been removed (dead code)"

    def test_has_required_methods(self):
        assert hasattr(QigongDomain, "query")
        assert hasattr(QigongDomain, "search")
        assert hasattr(QigongDomain, "get_exercise_by_name")


class TestQigongDomainInit:
    """Test QigongDomain initialization"""

    def test_creates_with_defaults(self):
        domain = QigongDomain()
        assert domain.name == "qigong"
        assert domain.config.domain_type == DomainType.QIGONG
        assert domain.config.priority == 10

    def test_creates_with_db_pool(self):
        mock_pool = MagicMock()
        domain = QigongDomain(db_pool=mock_pool)
        assert domain._db_pool is mock_pool


class TestDomainSearchWithoutPool:
    """Test that domain search returns empty without pool"""

    @pytest.mark.asyncio
    async def test_qigong_search_no_pool(self):
        domain = QigongDomain()
        result = await domain.search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_tcm_search_no_pool(self):
        domain = TcmDomain()
        result = await domain.search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_confucian_search_no_pool(self):
        domain = ConfucianDomain()
        result = await domain.search("test")
        assert result == []


class TestDomainQueryWithoutPool:
    """Test query returns low confidence without pool"""

    @pytest.mark.asyncio
    async def test_qigong_query_no_pool(self):
        domain = QigongDomain()
        result = await domain.query("什么是气功")
        assert result.confidence == 0.2
        assert result.domain == "qigong"
