"""领域模块

支持多领域知识库的统一接口
"""

from .base import BaseDomain, DomainConfig, QueryResult, DomainStats
from .qigong import QigongDomain
from .tcm import TcmDomain
from .confucian import ConfucianDomain
from .general import GeneralDomain
from .registry import DomainRegistry, setup_domains, get_registry

__all__ = [
    'BaseDomain',
    'DomainConfig',
    'QueryResult',
    'DomainStats',
    'QigongDomain',
    'TcmDomain',
    'ConfucianDomain',
    'GeneralDomain',
    'DomainRegistry',
    'setup_domains',
    'get_registry'
]
