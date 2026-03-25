# -*- coding: utf-8 -*-
"""
存储分层管理器
Storage Tiering Manager

智能管理数据在不同存储层级的移动：
- 热数据（频繁访问，SSD）
- 温数据（偶尔访问，HDD）
- 冷数据（归档，对象存储）
- 访问频率追踪
- 自动转换策略
- 成本优化
"""

import logging
import asyncio
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque

from .object_storage import (
    ObjectStorageService,
    StorageTier,
    FileMetadata,
)

logger = logging.getLogger(__name__)


class AccessFrequency(str, Enum):
    """访问频率"""

    FREQUENT = "frequent"      # 每天多次
    MODERATE = "moderate"      # 每周多次
    RARE = "rare"            # 每月多次
    ARCHIVE = "archive"        # 很少访问


@dataclass
class FileAccessInfo:
    """文件访问信息"""

    object_key: str
    tier: StorageTier
    access_count: int = 0
    last_access_time: Optional[datetime] = None
    access_history: deque = field(default_factory=lambda: deque(maxlen=100))
    total_access_duration: float = 0.0  # seconds
    file_size: int = 0

    def record_access(self, access_time: datetime, duration: float = 0.0):
        """
        记录访问

        Args:
            access_time: 访问时间
            duration: 访问持续时间
        """
        self.access_count += 1
        self.last_access_time = access_time
        self.access_history.append({
            'timestamp': access_time,
            'duration': duration,
        })
        self.total_access_duration += duration

    def calculate_frequency(self, days: int = 30) -> AccessFrequency:
        """
        计算访问频率

        Args:
            days: 分析周期（天）

        Returns:
            访问频率
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)

        # 统计周期内的访问次数
        recent_accesses = [
            access for access in self.access_history
            if access['timestamp'] >= cutoff_time
        ]

        access_count = len(recent_accesses)

        # 计算频率
        if access_count == 0:
            return AccessFrequency.ARCHIVE
        elif access_count < 2:
            return AccessFrequency.RARE
        elif access_count < 10:
            return AccessFrequency.MODERATE
        else:
            return AccessFrequency.FREQUENT

    def get_avg_access_duration(self) -> float:
        """
        获取平均访问持续时间

        Returns:
            平均持续时间（秒）
        """
        if not self.access_history:
            return 0.0

        durations = [
            access['duration'] for access in self.access_history
            if access['duration'] > 0
        ]

        if not durations:
            return 0.0

        return sum(durations) / len(durations)


@dataclass
class TieringConfig:
    """分层配置"""

    # 频率阈值（分析周期：天）
    FREQUENT_THRESHOLD_DAYS: int = 7
    MODERATE_THRESHOLD_DAYS: int = 30
    RARE_THRESHOLD_DAYS: int = 90
    ARCHIVE_THRESHOLD_DAYS: int = 180

    # 访问次数阈值
    FREQUENT_MIN_ACCESSES: int = 10
    MODERATE_MIN_ACCESSES: int = 5
    RARE_MIN_ACCESSES: int = 2

    # 成本因素（存储层级相对成本）
    COST_FACTORS: Dict[StorageTier, float] = field(default_factory=lambda: {
        StorageTier.HOT: 1.0,       # SSD: 1.0x
        StorageTier.WARM: 0.5,     # HDD: 0.5x
        StorageTier.COLD: 0.1,     # Object: 0.1x
        StorageTier.ARCHIVE: 0.05, # Archive: 0.05x
    })

    # 性能因素（相对延迟）
    LATENCY_FACTORS: Dict[StorageTier, float] = field(default_factory=lambda: {
        StorageTier.HOT: 1.0,       # < 1ms
        StorageTier.WARM: 5.0,     # ~ 5ms
        StorageTier.COLD: 50.0,    # ~ 50ms
        StorageTier.ARCHIVE: 200.0, # ~ 200ms
    })

    # 转换配置
    enable_auto_tiering: bool = True
    tiering_check_interval_hours: int = 24  # 每日检查
    minimum_tiering_age_days: int = 7  # 文件至少存在7天
    cooldown_between_transitions_days: int = 7  # 两次转换间隔7天

    # 批量处理配置
    max_files_per_tiering_run: int = 1000  # 单次最多处理1000个文件
    tiering_batch_size: int = 50  # 每批50个文件


class StorageTieringManager:
    """
    存储分层管理器

    Features:
    - 访问频率追踪
    - 智能分层决策
    - 自动转换策略
    - 成本优化
    - 性能优化
    - 批量转换处理
    """

    def __init__(
        self,
        storage_service: ObjectStorageService,
        config: Optional[TieringConfig] = None,
    ):
        """
        初始化分层管理器

        Args:
            storage_service: 对象存储服务
            config: 分层配置
        """
        self.storage = storage_service
        self.config = config or TieringConfig()

        # 文件访问追踪
        self.file_access_info: Dict[str, FileAccessInfo] = {}

        # 转换历史
        self.tiering_history: List[Dict[str, Any]] = []

        # 统计信息
        self.stats = {
            "total_analyzed": 0,
            "files_moved": 0,
            "total_cost_savings": 0.0,
            "avg_access_improvement": 0.0,
        }

        logger.info("Storage Tiering Manager initialized")

    async def initialize(self):
        """
        初始化分层管理器

        - 从存储加载现有文件
        - 初始化访问统计
        - 启动自动分层
        """
        logger.info("Initializing storage tiering...")

        # 加载所有存储层级的文件
        for tier in StorageTier:
            files = await self.storage.list_files(tier=tier)

            for file_info in files:
                object_key = file_info['object_key']

                # 创建访问信息
                self.file_access_info[object_key] = FileAccessInfo(
                    object_key=object_key,
                    tier=tier,
                    file_size=file_info['size'],
                )

                # 更新统计
                self.stats["total_analyzed"] += 1

        logger.info(
            f"Tiering initialized: "
            f"{len(self.file_access_info)} files tracked"
        )

    async def record_access(
        self,
        object_key: str,
        duration: float = 0.0,
    ):
        """
        记录文件访问

        Args:
            object_key: 对象键
            duration: 访问持续时间（秒）
        """
        if object_key not in self.file_access_info:
            # 获取文件信息（如果不存在）
            # 简化处理，创建新的访问信息
            logger.warning(
                f"Access recorded for untracked file: {object_key}"
            )
            return

        # 记录访问
        access_info = self.file_access_info[object_key]
        access_info.record_access(datetime.utcnow(), duration)

        logger.debug(
            f"Access recorded: {object_key} "
            f"(count: {access_info.access_count}, duration: {duration})"
        )

    async def analyze_and_tier(self) -> List[Dict[str, Any]]:
        """
        分析并执行分层

        Returns:
            转换操作列表
        """
        logger.info("Starting storage tiering analysis...")

        # 收集需要转换的文件
        transitions = []

        for object_key, access_info in self.file_access_info.items():
            # 跳过太新的文件
            if not access_info.last_access_time:
                continue

            file_age = (datetime.utcnow() - access_info.last_access_time).days
            if file_age < self.config.minimum_tiering_age_days:
                continue

            # 计算访问频率
            frequency = access_info.calculate_frequency()

            # 确定目标层级
            target_tier = self._determine_target_tier(
                access_info=access_info,
                frequency=frequency,
            )

            # 如果需要转换
            if target_tier != access_info.tier:
                # 检查冷却时间
                if await self._check_cooldown(object_key, access_info.tier):
                    transition = {
                        'object_key': object_key,
                        'source_tier': access_info.tier,
                        'target_tier': target_tier,
                        'frequency': frequency.value,
                        'access_count': access_info.access_count,
                        'file_size': access_info.file_size,
                        'reason': self._get_transition_reason(frequency),
                    }
                    transitions.append(transition)

        logger.info(
            f"Tiering analysis complete: {len(transitions)} "
            f"transitions needed"
        )

        return transitions

    async def execute_tiering(
        self,
        transitions: List[Dict[str, Any]],
        batch_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        执行分层转换

        Args:
            transitions: 转换列表
            batch_size: 批次大小

        Returns:
            转换结果
        """
        batch_size = batch_size or self.config.tiering_batch_size

        results = {
            'success_count': 0,
            'failed_count': 0,
            'total_size': 0,
            'cost_savings': 0.0,
            'latency_improvement': 0.0,
        }

        # 分批处理
        for i in range(0, len(transitions), batch_size):
            batch = transitions[i:i + batch_size]

            logger.info(
                f"Processing tiering batch {i // batch_size + 1}: "
                f"{len(batch)} files"
            )

            # 并发处理批次
            tasks = [
                self._execute_transition(transition)
                for transition in batch
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 统计结果
            for result in batch_results:
                if isinstance(result, Exception):
                    results['failed_count'] += 1
                    logger.error(f"Transition failed: {str(result)}")
                else:
                    results['success_count'] += 1
                    results['total_size'] += result['file_size']
                    results['cost_savings'] += result['cost_savings']
                    results['latency_improvement'] += result['latency_improvement']

        # 更新统计
        self.stats['files_moved'] = results['success_count']
        self.stats['total_cost_savings'] += results['cost_savings']

        # 记录历史
        self.tiering_history.append({
            'timestamp': datetime.utcnow().isoformat(),
            'transitions_executed': results['success_count'],
            'transitions_failed': results['failed_count'],
            'total_size_moved': results['total_size'],
            'cost_savings': results['cost_savings'],
        })

        logger.info(
            f"Tiering execution complete: "
            f"{results['success_count']} succeeded, "
            f"{results['failed_count']} failed"
        )

        return results

    async def _execute_transition(
        self,
        transition: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行单个转换

        Args:
            transition: 转换信息

        Returns:
            转换结果
        """
        object_key = transition['object_key']
        source_tier = transition['source_tier']
        target_tier = transition['target_tier']
        file_size = transition['file_size']

        try:
            # 移动文件
            success = await self.storage.move_file(
                source_key=object_key,
                source_tier=source_tier,
                target_key=object_key,  # 保持相同的键
                target_tier=target_tier,
            )

            if success:
                # 更新访问信息
                self.file_access_info[object_key].tier = target_tier

                # 计算成本节省
                source_cost = file_size * self.config.COST_FACTORS[source_tier]
                target_cost = file_size * self.config.COST_FACTORS[target_tier]
                cost_savings = source_cost - target_cost

                # 计算延迟改进
                source_latency = self.config.LATENCY_FACTORS[source_tier]
                target_latency = self.config.LATENCY_FACTORS[target_tier]
                latency_improvement = source_latency - target_latency

                logger.info(
                    f"File tiered: {object_key} "
                    f"({source_tier.value} → {target_tier.value})"
                )

                return {
                    'object_key': object_key,
                    'success': True,
                    'file_size': file_size,
                    'cost_savings': cost_savings,
                    'latency_improvement': latency_improvement,
                }
            else:
                return {
                    'object_key': object_key,
                    'success': False,
                    'error': 'Move operation failed',
                    'file_size': file_size,
                    'cost_savings': 0.0,
                    'latency_improvement': 0.0,
                }

        except Exception as e:
            logger.error(
                f"Failed to tier {object_key}: {str(e)}",
                exc_info=True
            )
            return {
                'object_key': object_key,
                'success': False,
                'error': str(e),
                'file_size': file_size,
                'cost_savings': 0.0,
                'latency_improvement': 0.0,
            }

    def _determine_target_tier(
        self,
        access_info: FileAccessInfo,
        frequency: AccessFrequency,
    ) -> StorageTier:
        """
        确定目标存储层级

        Args:
            access_info: 文件访问信息
            frequency: 访问频率

        Returns:
            目标存储层级
        """
        # 根据访问频率确定层级
        if frequency == AccessFrequency.FREQUENT:
            return StorageTier.HOT
        elif frequency == AccessFrequency.MODERATE:
            return StorageTier.WARM
        elif frequency == AccessFrequency.RARE:
            return StorageTier.COLD
        else:
            return StorageTier.ARCHIVE

    async def _check_cooldown(
        self,
        object_key: str,
        current_tier: StorageTier
    ) -> bool:
        """
        检查转换冷却时间

        Args:
            object_key: 对象键
            current_tier: 当前层级

        Returns:
            是否可以转换
        """
        # 检查历史记录
        for history in reversed(self.tiering_history):
            if history.get('object_key') == object_key:
                transition_time = datetime.fromisoformat(history['timestamp'])
                time_since_transition = (datetime.utcnow() - transition_time).days

                if time_since_transition < self.config.cooldown_between_transitions_days:
                    return False

        return True

    def _get_transition_reason(self, frequency: AccessFrequency) -> str:
        """
        获取转换原因

        Args:
            frequency: 访问频率

        Returns:
            转换原因描述
        """
        reasons = {
            AccessFrequency.FREQUENT: "Frequent access (HOT tier for optimal performance)",
            AccessFrequency.MODERATE: "Moderate access (WARM tier for cost/performance balance)",
            AccessFrequency.RARE: "Rare access (COLD tier for cost optimization)",
            AccessFrequency.ARCHIVE: "Very rare access (ARCHIVE tier for long-term storage)",
        }
        return reasons[frequency]

    async def get_tiering_stats(self) -> Dict[str, Any]:
        """
        获取分层统计信息

        Returns:
            分层统计字典
        """
        # 统计各层级的文件数量
        tier_counts = defaultdict(int)
        tier_sizes = defaultdict(int)

        for access_info in self.file_access_info.values():
            tier_counts[access_info.tier] += 1
            tier_sizes[access_info.tier] += access_info.file_size

        # 计算总成本和延迟
        total_cost = 0.0
        total_latency_weight = 0.0

        for tier, count in tier_counts.items():
            size = tier_sizes[tier]
            cost_factor = self.config.COST_FACTORS[tier]
            latency_factor = self.config.LATENCY_FACTORS[tier]

            tier_cost = size * cost_factor * count
            tier_latency = latency_factor * count

            total_cost += tier_cost
            total_latency_weight += tier_latency

        return {
            'tier_distribution': {
                tier.value: {
                    'file_count': count,
                    'total_size': tier_sizes[tier],
                    'size_gb': tier_sizes[tier] / (1024 * 1024 * 1024),
                }
                for tier in StorageTier
            },
            'total_files': len(self.file_access_info),
            'total_size_gb': sum(tier_sizes.values()) / (1024 * 1024 * 1024),
            'estimated_monthly_cost': total_cost * 30,  # 简化计算
            'estimated_monthly_cost_savings': self.stats['total_cost_savings'] * 30,
            'files_moved': self.stats['files_moved'],
            'transitions_executed': len(self.tiering_history),
            'cost_savings_pct': (
                self.stats['total_cost_savings'] / total_cost * 100
                if total_cost > 0 else 0
            ),
        }

    async def run_auto_tiering(self):
        """
        运行自动分层（定期任务）

        1. 分析所有文件
        2. 确定需要转换的文件
        3. 执行转换
        4. 更新统计
        """
        if not self.config.enable_auto_tiering:
            logger.debug("Auto-tiering is disabled")
            return

        logger.info("Running auto-tiering...")

        # 分析并确定转换
        transitions = await self.analyze_and_tier()

        if not transitions:
            logger.info("No tiering transitions needed")
            return

        # 执行转换（限制每次运行的数量）
        transitions_to_execute = transitions[:self.config.max_files_per_tiering_run]

        if len(transitions_to_execute) > 0:
            # 执行转换
            results = await self.execute_tiering(transitions_to_execute)

            logger.info(
                f"Auto-tiering complete: "
                f"{results['success_count']} files moved, "
                f"${results['cost_savings']:.2f} cost savings"
            )


# 全局分层管理器实例
tiering_manager: Optional[StorageTieringManager] = None


def init_tiering_manager(
    storage_service: ObjectStorageService,
    config: Optional[TieringConfig] = None,
) -> StorageTieringManager:
    """
    初始化存储分层管理器

    Args:
        storage_service: 对象存储服务
        config: 分层配置

    Returns:
        StorageTieringManager实例

    Example:
    -------
    ```python
    from .storage_tiering import (
        init_tiering_manager,
        tiering_manager,
        StorageTieringConfig,
    )

    # 初始化
    tiering_manager = init_tiering_manager(
        storage_service=storage_service,
        config=StorageTieringConfig(
            enable_auto_tiering=True,
            tiering_check_interval_hours=24,
        ),
    )

    # 初始化（加载现有文件）
    await tiering_manager.initialize()

    # 记录访问
    await tiering_manager.record_access("documents/file123.pdf")

    # 运行自动分层
    await tiering_manager.run_auto_tiering()

    # 获取统计
    stats = await tiering_manager.get_tiering_stats()
    print(f"Cost savings: ${stats['estimated_monthly_cost_savings']:.2f}/month")
    ```
    """
    manager = StorageTieringManager(
        storage_service=storage_service,
        config=config,
    )

    # 导出全局实例
    global tiering_manager
    tiering_manager = manager

    logger.info("Storage Tiering Manager initialized")

    return manager


__all__ = [
    "AccessFrequency",
    "FileAccessInfo",
    "TieringConfig",
    "StorageTieringManager",
    "tiering_manager",
    "init_tiering_manager",
]
