"""领域模块

支持多领域知识库的统一接口
"""

from .base import BaseDomain, DomainConfig, DomainStats, QueryResult
from .buddhist import BuddhistDomain
from .confucian import ConfucianDomain
from .daoist import DaoistDomain
from .general import GeneralDomain
from .martial import MartialDomain
from .philosophy import PhilosophyDomain
from .psychology import PsychologyDomain
from .qigong import QigongDomain
from .registry import DomainRegistry, get_registry, setup_domains
from .science import ScienceDomain
from .tcm import TcmDomain

__all__ = [
    "BaseDomain",
    "DomainConfig",
    "QueryResult",
    "DomainStats",
    "QigongDomain",
    "TcmDomain",
    "ConfucianDomain",
    "BuddhistDomain",
    "DaoistDomain",
    "MartialDomain",
    "PhilosophyDomain",
    "ScienceDomain",
    "PsychologyDomain",
    "GeneralDomain",
    "DomainRegistry",
    "setup_domains",
    "get_registry",
]
