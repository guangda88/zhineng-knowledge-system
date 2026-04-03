# -*- coding: utf-8 -*-
"""
自动化备份和恢复系统
Automated Backup and Recovery System

实现完整的备份策略，支持：
- 增量备份
- 定时备份
- 跨区域复制
- 自动恢复测试
- 备份验证
- 保留策略
"""

import os
import logging
import gzip
import shutil
import hashlib
import json
import asyncio
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from io import BytesIO
import subprocess

# Database imports
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

# Object storage imports
from .object_storage import (
    ObjectStorageService,
    StorageTier,
)

logger = logging.getLogger(__name__)


class BackupType(str, Enum):
    """备份类型"""

    FULL = "full"  # 全量备份
    INCREMENTAL = "incremental"  # 增量备份
    DIFFERENTIAL = "differential"  # 差异备份
    LOGICAL = "logical"  # 逻辑备份（pg_dump）
    PHYSICAL = "physical"  # 物理备份（pg_basebackup）


class BackupStatus(str, Enum):
    """备份状态"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RESTORING = "restoring"
    RESTORED = "restored"


class RecoveryStatus(str, Enum):
    """恢复状态"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATED = "validated"


@dataclass
class BackupConfig:
    """备份配置"""

    # 数据库配置
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "zhineng_kb"
    db_user: str = "postgres"
    db_password: str = ""

    # 备份存储配置
    backup_dir: str = "/backups"
    backup_bucket: str = "zhineng-backups"
    backup_tier: StorageTier = StorageTier.COLD

    # 备份策略
    backup_type: BackupType = BackupType.LOGICAL
    enable_compression: bool = True
    compression_level: int = 6
    enable_checksum: bool = True
    checksum_algorithm: str = "sha256"

    # 保留策略
    retention_policy: Dict[str, int] = field(
        default_factory=lambda: {
            "daily": 7,  # 保留7天
            "weekly": 4,  # 保留4周
            "monthly": 12,  # 保留12月
            "yearly": 3,  # 保留3年
        }
    )

    # 调度配置
    enable_scheduled_backups: bool = True
    full_backup_interval_hours: int = 24  # 每24小时
    incremental_backup_interval_hours: int = 1  # 每1小时

    # 恢复测试配置
    enable_recovery_tests: bool = True
    recovery_test_interval_days: int = 7  # 每7天
    recovery_test_db_name: str = "zhineng_kb_test"

    # 跨区域复制
    enable_cross_region_replication: bool = False
    secondary_bucket: str = "zhineng-backups-secondary"
    secondary_region: str = "us-west-2"

    # 通知配置
    notify_on_success: bool = True
    notify_on_failure: bool = True
    notify_on_recovery_test: bool = True


@dataclass
class BackupMetadata:
    """备份元数据"""

    backup_id: str
    backup_type: BackupType
    status: BackupStatus
    created_at: datetime
    started_at: datetime
    completed_at: Optional[datetime] = None
    file_size: int = 0
    file_hash: str = ""
    checksum: str = ""
    is_compressed: bool = False
    location: str = ""
    backup_url: Optional[str] = None
    db_name: str = ""
    db_version: str = ""
    table_count: int = 0
    row_count: int = 0
    error: Optional[str] = None
    validated: bool = False
    recovery_tested: bool = False
    recovery_test_passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "backup_id": self.backup_id,
            "backup_type": self.backup_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat(),
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "checksum": self.checksum,
            "is_compressed": self.is_compressed,
            "location": self.location,
            "backup_url": self.backup_url,
            "db_name": self.db_name,
            "db_version": self.db_version,
            "table_count": self.table_count,
            "row_count": self.row_count,
            "error": self.error,
            "validated": self.validated,
            "recovery_tested": self.recovery_tested,
            "recovery_test_passed": self.recovery_test_passed,
        }


class BackupManager:
    """
    备份管理器

    提供完整的备份和恢复功能。

    Features:
    - 全量/增量备份
    - 定时备份
    - 压缩和校验和
    - 跨区域复制
    - 自动恢复测试
    - 备份验证
    - 保留策略
    - 元数据管理
    """

    def __init__(
        self,
        config: Optional[BackupConfig] = None,
        storage_service: Optional[ObjectStorageService] = None,
    ):
        """
        初始化备份管理器

        Args:
            config: 备份配置
            storage_service: 对象存储服务
        """
        self.config = config or BackupConfig()
        self.storage = storage_service

        # 备份历史
        self.backup_history: List[BackupMetadata] = []

        # 统计信息
        self.stats = {
            "total_backups": 0,
            "successful_backups": 0,
            "failed_backups": 0,
            "total_backup_size": 0,
            "total_restore_tests": 0,
            "successful_restore_tests": 0,
            "failed_restore_tests": 0,
            "avg_backup_duration": 0.0,
            "avg_restore_duration": 0.0,
        }

        # 确保备份目录存在
        os.makedirs(self.config.backup_dir, exist_ok=True)

        logger.info("Backup Manager initialized")

    async def create_backup(
        self,
        backup_type: BackupType = BackupType.LOGICAL,
        compress: bool = None,
    ) -> BackupMetadata:
        """
        创建备份

        Args:
            backup_type: 备份类型
            compress: 是否压缩（None=使用配置）

        Returns:
            备份元数据
        """
        # 确定是否压缩
        should_compress = compress if compress is not None else self.config.enable_compression

        # 生成备份ID
        backup_id = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # 创建备份元数据
        metadata = BackupMetadata(
            backup_id=backup_id,
            backup_type=backup_type,
            status=BackupStatus.IN_PROGRESS,
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            is_compressed=should_compress,
            db_name=self.config.db_name,
            db_version=await self._get_db_version(),
        )

        logger.info(f"Creating backup: {backup_id} (type: {backup_type.value})")

        try:
            # 执行备份
            if backup_type == BackupType.LOGICAL:
                file_path = await self._create_logical_backup(metadata, should_compress)
            elif backup_type == BackupType.PHYSICAL:
                file_path = await self._create_physical_backup(metadata, should_compress)
            else:
                raise ValueError(f"Unsupported backup type: {backup_type}")

            # 更新元数据
            metadata.status = BackupStatus.COMPLETED
            metadata.completed_at = datetime.utcnow()
            metadata.file_size = os.path.getsize(file_path)
            metadata.location = file_path

            # 计算校验和
            if self.config.enable_checksum:
                metadata.checksum = self._calculate_checksum(file_path)
                metadata.file_hash = self._calculate_file_hash(file_path)

            # 上传到对象存储
            if self.storage:
                backup_url = await self._upload_backup(file_path, metadata)
                metadata.backup_url = backup_url

                # 跨区域复制
                if self.config.enable_cross_region_replication:
                    await self._replicate_backup(file_path, metadata)

            # 验证备份
            if self.storage:
                metadata.validated = await self._validate_backup(metadata)

            # 更新统计
            duration = (metadata.completed_at - metadata.started_at).total_seconds()
            self._update_backup_stats(duration, True, metadata.file_size)

            logger.info(
                f"Backup completed: {backup_id} "
                f"(size: {metadata.file_size}, duration: {duration:.2f}s)"
            )

        except Exception as e:
            metadata.status = BackupStatus.FAILED
            metadata.error = str(e)
            metadata.completed_at = datetime.utcnow()

            # 更新统计
            duration = (metadata.completed_at - metadata.started_at).total_seconds()
            self._update_backup_stats(duration, False, 0)

            logger.error(f"Backup failed: {backup_id} - {str(e)}", exc_info=True)

        # 添加到历史
        self.backup_history.append(metadata)

        return metadata

    async def _create_logical_backup(
        self,
        metadata: BackupMetadata,
        compress: bool,
    ) -> str:
        """
        创建逻辑备份（pg_dump）

        Args:
            metadata: 备份元数据
            compress: 是否压缩

        Returns:
            备份文件路径
        """
        # 生成文件名
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{metadata.backup_id}.sql"
        file_path = os.path.join(self.config.backup_dir, filename)

        # 构建pg_dump命令
        pg_env = {
            "PGPASSWORD": self.config.db_password,
        }

        pg_dump_cmd = [
            "pg_dump",
            "-h",
            self.config.db_host,
            "-p",
            str(self.config.db_port),
            "-U",
            self.config.db_user,
            "-d",
            self.config.db_name,
            "-f",
            file_path,
            "--verbose",
        ]

        # 如果压缩，使用自定义格式
        if compress:
            filename = f"{filename}.gz"
            file_path = os.path.join(self.config.backup_dir, filename)
            pg_dump_cmd.extend(
                [
                    "--format=custom",
                    f"--compress={self.config.compression_level}",
                ]
            )

        # 执行pg_dump
        process = await asyncio.create_subprocess_exec(
            *pg_dump_cmd,
            env=pg_env,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {stderr.decode('utf-8')}")

        # 获取数据库统计
        metadata.table_count = await self._get_table_count()
        metadata.row_count = await self._get_row_count()

        logger.info(f"Logical backup created: {file_path}")
        return file_path

    async def _create_physical_backup(
        self,
        metadata: BackupMetadata,
        compress: bool,
    ) -> str:
        """
        创建物理备份（pg_basebackup）

        Args:
            metadata: 备份元数据
            compress: 是否压缩

        Returns:
            备份目录路径
        """
        # 生成目录名
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dir_name = f"{metadata.backup_id}"
        dir_path = os.path.join(self.config.backup_dir, dir_name)

        # 构建pg_basebackup命令
        pg_env = {
            "PGPASSWORD": self.config.db_password,
        }

        pg_basebackup_cmd = [
            "pg_basebackup",
            "-h",
            self.config.db_host,
            "-p",
            str(self.config.db_port),
            "-U",
            self.config.db_user,
            "-D",
            dir_path,
            "--verbose",
        ]

        # 执行pg_basebackup
        process = await asyncio.create_subprocess_exec(
            *pg_basebackup_cmd,
            env=pg_env,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"pg_basebackup failed: {stderr.decode('utf-8')}")

        # 计算目录大小
        total_size = 0
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)

        metadata.file_size = total_size

        logger.info(f"Physical backup created: {dir_path}")
        return dir_path

    async def _upload_backup(
        self,
        file_path: str,
        metadata: BackupMetadata,
    ) -> str:
        """
        上传备份到对象存储

        Args:
            file_path: 本地备份路径
            metadata: 备份元数据

        Returns:
            备份URL
        """
        # 构建对象键
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        object_key = f"backups/{timestamp}/{metadata.backup_id}"

        # 上传文件
        result = await self.storage.upload_file(
            file_path=file_path,
            object_key=object_key,
            tier=self.config.backup_tier,
            compress=metadata.is_compressed,
        )

        logger.info(f"Backup uploaded: {metadata.backup_id} to {result['cdn_url']}")

        return result["cdn_url"]

    async def _replicate_backup(
        self,
        file_path: str,
        metadata: BackupMetadata,
    ):
        """
        跨区域复制备份

        Args:
            file_path: 本地备份路径
            metadata: 备份元数据
        """
        # 注意：需要配置secondary存储桶
        # 这里实现基本逻辑
        if not self.config.secondary_bucket:
            logger.warning("Secondary bucket not configured, skipping replication")
            return

        logger.info(f"Replicating backup: {metadata.backup_id}")

        # TODO: 实现跨区域复制逻辑
        pass

    async def _validate_backup(
        self,
        metadata: BackupMetadata,
    ) -> bool:
        """
        验证备份

        Args:
            metadata: 备份元数据

        Returns:
            是否有效
        """
        try:
            # 检查文件存在
            if not os.path.exists(metadata.location):
                logger.error(f"Backup file not found: {metadata.location}")
                return False

            # 验证校验和
            if self.config.enable_checksum:
                calculated_checksum = self._calculate_checksum(metadata.location)
                if calculated_checksum != metadata.checksum:
                    logger.error(f"Backup checksum mismatch: {metadata.backup_id}")
                    return False

            # 验证文件哈希
            calculated_hash = self._calculate_file_hash(metadata.location)
            if calculated_hash != metadata.file_hash:
                logger.error(f"Backup file hash mismatch: {metadata.backup_id}")
                return False

            # 恢复测试（如果启用）
            if self.config.enable_recovery_tests:
                passed = await self._test_recovery(metadata)
                metadata.recovery_tested = True
                metadata.recovery_test_passed = passed

                if not passed:
                    logger.warning(f"Backup recovery test failed: {metadata.backup_id}")
                    return False

            logger.info(f"Backup validated: {metadata.backup_id}")
            return True

        except Exception as e:
            logger.error(
                f"Backup validation failed: {metadata.backup_id} - {str(e)}", exc_info=True
            )
            return False

    async def restore_backup(
        self,
        backup_id: str,
        target_db_name: Optional[str] = None,
        validate: bool = True,
    ) -> Dict[str, Any]:
        """
        恢复备份

        Args:
            backup_id: 备份ID
            target_db_name: 目标数据库名（None=原数据库）
            validate: 是否验证恢复

        Returns:
            恢复结果
        """
        # 查找备份
        metadata = self._find_backup(backup_id)
        if not metadata:
            raise ValueError(f"Backup not found: {backup_id}")

        # 更新状态
        metadata.status = BackupStatus.RESTORING
        target_db = target_db_name or self.config.db_name

        logger.info(f"Restoring backup: {backup_id} to {target_db}")

        try:
            # 下载备份
            if self.storage and metadata.backup_url:
                file_path = await self._download_backup(
                    metadata.backup_url,
                    backup_id,
                )
            else:
                file_path = metadata.location

            start_time = datetime.utcnow()

            # 执行恢复
            if metadata.backup_type == BackupType.LOGICAL:
                await self._restore_logical_backup(file_path, target_db, metadata)
            elif metadata.backup_type == BackupType.PHYSICAL:
                await self._restore_physical_backup(file_path, target_db, metadata)

            # 验证恢复
            if validate:
                is_valid = await self._validate_restore(target_db)
            else:
                is_valid = True

            end_time = datetime.utcnow()

            # 更新统计
            duration = (end_time - start_time).total_seconds()
            self._update_restore_stats(duration, is_valid)

            result = {
                "backup_id": backup_id,
                "status": "success" if is_valid else "validation_failed",
                "target_db": target_db,
                "duration_seconds": duration,
                "validated": is_valid,
                "restored_at": end_time.isoformat(),
            }

            logger.info(
                f"Backup restored: {backup_id} "
                f"(duration: {duration:.2f}s, validated: {is_valid})"
            )

            return result

        except Exception as e:
            logger.error(f"Backup restoration failed: {backup_id} - {str(e)}", exc_info=True)

            return {
                "backup_id": backup_id,
                "status": "failed",
                "error": str(e),
            }

    async def _restore_logical_backup(
        self,
        file_path: str,
        target_db: str,
        metadata: BackupMetadata,
    ):
        """
        恢复逻辑备份（psql）

        Args:
            file_path: 备份文件路径
            target_db: 目标数据库
            metadata: 备份元数据
        """
        # 如果是压缩文件，解压
        if metadata.is_compressed and file_path.endswith(".gz"):
            # 解压到临时文件
            import tempfile

            temp_file = tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=".sql",
                delete=False,
            )
            temp_path = temp_file.name

            with gzip.open(file_path, "rb") as f:
                temp_file.write(f.read())
            temp_file.close()

            file_path = temp_path

        # 构建psql命令
        pg_env = {
            "PGPASSWORD": self.config.db_password,
        }

        psql_cmd = [
            "psql",
            "-h",
            self.config.db_host,
            "-p",
            str(self.config.db_port),
            "-U",
            self.config.db_user,
            "-d",
            "postgres",  # 连接到默认数据库
            "-c",
            f"DROP DATABASE IF EXISTS {target_db};",
        ]

        # 删除现有数据库
        process = await asyncio.create_subprocess_exec(
            *psql_cmd,
            env=pg_env,
        )
        await process.communicate()

        # 创建数据库
        psql_cmd = [
            "psql",
            "-h",
            self.config.db_host,
            "-p",
            str(self.config.db_port),
            "-U",
            self.config.db_user,
            "-d",
            "postgres",
            "-c",
            f"CREATE DATABASE {target_db};",
        ]

        process = await asyncio.create_subprocess_exec(
            *psql_cmd,
            env=pg_env,
        )
        await process.communicate()

        # 恢复备份
        psql_cmd = [
            "psql",
            "-h",
            self.config.db_host,
            "-p",
            str(self.config.db_port),
            "-U",
            self.config.db_user,
            "-d",
            target_db,
            "-f",
            file_path,
            "--verbose",
        ]

        process = await asyncio.create_subprocess_exec(
            *psql_cmd,
            env=pg_env,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"psql restore failed: {stderr.decode('utf-8')}")

        logger.info(f"Logical backup restored to {target_db}")

    async def _restore_physical_backup(
        self,
        file_path: str,
        target_db: str,
        metadata: BackupMetadata,
    ):
        """
        恢复物理备份

        Args:
            file_path: 备份目录路径
            target_db: 目标数据库
            metadata: 备份元数据
        """
        # 物理备份恢复需要停止PostgreSQL并复制文件
        # 这里实现基本逻辑

        logger.info("Physical backup restore requires manual intervention")
        # TODO: 实现完整的物理恢复逻辑
        raise NotImplementedError("Physical backup restore requires manual intervention")

    async def _test_recovery(
        self,
        metadata: BackupMetadata,
    ) -> bool:
        """
        测试恢复

        Args:
            metadata: 备份元数据

        Returns:
            是否通过测试
        """
        test_db = self.config.recovery_test_db_name

        try:
            # 恢复到测试数据库
            result = await self.restore_backup(
                metadata.backup_id,
                target_db_name=test_db,
                validate=False,
            )

            if result["status"] != "success":
                return False

            # 验证数据库
            is_valid = await self._validate_restore(test_db)

            # 清理测试数据库
            await self._cleanup_test_db(test_db)

            return is_valid

        except Exception as e:
            logger.error(f"Recovery test failed: {metadata.backup_id} - {str(e)}", exc_info=True)
            return False

    async def _validate_restore(self, db_name: str) -> bool:
        """
        验证恢复的数据库

        Args:
            db_name: 数据库名称

        Returns:
            是否有效
        """
        try:
            # 连接到数据库
            conn = await asyncpg.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                user=self.config.db_user,
                password=self.config.db_password,
                database=db_name,
            )

            # 执行验证查询
            async with conn.transaction():
                # 检查表数量
                result = await conn.fetchval(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )

                if result == 0:
                    return False

                # 检查示例查询
                await conn.fetchval("SELECT 1")

            await conn.close()

            logger.info(f"Restore validated: {db_name}")
            return True

        except Exception as e:
            logger.error(f"Restore validation failed for {db_name}: {str(e)}", exc_info=True)
            return False

    async def _cleanup_test_db(self, db_name: str):
        """
        清理测试数据库

        Args:
            db_name: 数据库名称
        """
        pg_env = {
            "PGPASSWORD": self.config.db_password,
        }

        psql_cmd = [
            "psql",
            "-h",
            self.config.db_host,
            "-p",
            str(self.config.db_port),
            "-U",
            self.config.db_user,
            "-d",
            "postgres",
            "-c",
            f"DROP DATABASE IF EXISTS {db_name};",
        ]

        process = await asyncio.create_subprocess_exec(
            *psql_cmd,
            env=pg_env,
        )
        await process.communicate()

        logger.info(f"Test database cleaned up: {db_name}")

    async def _download_backup(
        self,
        backup_url: str,
        backup_id: str,
    ) -> str:
        """
        下载备份

        Args:
            backup_url: 备份URL
            backup_id: 备份ID

        Returns:
            下载的文件路径
        """
        # 确定下载路径
        download_dir = os.path.join(self.config.backup_dir, "downloads")
        os.makedirs(download_dir, exist_ok=True)
        file_path = os.path.join(download_dir, f"{backup_id}.sql")

        # 下载文件
        # 注意：这里简化处理，实际应该使用requests/httpx
        logger.info(f"Downloading backup from {backup_url}")

        # TODO: 实现实际的下载逻辑
        pass

        return file_path

    def _find_backup(self, backup_id: str) -> Optional[BackupMetadata]:
        """
        查找备份

        Args:
            backup_id: 备份ID

        Returns:
            备份元数据
        """
        for metadata in reversed(self.backup_history):
            if metadata.backup_id == backup_id:
                return metadata
        return None

    def _calculate_checksum(self, file_path: str) -> str:
        """计算文件校验和"""
        checksum = self.config.checksum_algorithm.lower()

        if checksum == "sha256":
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        elif checksum == "md5":
            md5 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5.update(chunk)
            return md5.hexdigest()
        else:
            raise ValueError(f"Unsupported checksum algorithm: {checksum}")

    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希（SHA256）"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _get_db_version(self) -> str:
        """获取数据库版本"""
        try:
            conn = await asyncpg.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                user=self.config.db_user,
                password=self.config.db_password,
                database=self.config.db_name,
            )

            version = await conn.fetchval("SELECT version()")
            await conn.close()

            return version

        except Exception as e:
            logger.warning(f"Failed to get DB version: {str(e)}")
            return "unknown"

    async def _get_table_count(self) -> int:
        """获取表数量"""
        try:
            conn = await asyncpg.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                user=self.config.db_user,
                password=self.config.db_password,
                database=self.config.db_name,
            )

            count = await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables " "WHERE table_schema = 'public'"
            )
            await conn.close()

            return count

        except Exception as e:
            logger.warning(f"Failed to get table count: {str(e)}")
            return 0

    async def _get_row_count(self) -> int:
        """获取行数量（估计）"""
        try:
            conn = await asyncpg.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                user=self.config.db_user,
                password=self.config.db_password,
                database=self.config.db_name,
            )

            # 获取所有表的行数估计
            result = await conn.fetch(
                "SELECT reltuples::bigint AS row_count "
                "FROM pg_class c "
                "JOIN pg_namespace n ON c.relnamespace = n.oid "
                "WHERE n.nspname = 'public' "
                "AND c.relkind = 'r'"
            )

            total = sum(row["row_count"] for row in result)
            await conn.close()

            return total

        except Exception as e:
            logger.warning(f"Failed to get row count: {str(e)}")
            return 0

    def _update_backup_stats(
        self,
        duration: float,
        success: bool,
        file_size: int,
    ):
        """更新备份统计"""
        self.stats["total_backups"] += 1
        self.stats["total_backup_size"] += file_size

        if success:
            self.stats["successful_backups"] += 1
        else:
            self.stats["failed_backups"] += 1

        # 更新平均持续时间
        n = self.stats["total_backups"]
        old_avg = self.stats["avg_backup_duration"]
        new_avg = (old_avg * (n - 1) + duration) / n
        self.stats["avg_backup_duration"] = new_avg

    def _update_restore_stats(
        self,
        duration: float,
        success: bool,
    ):
        """更新恢复统计"""
        self.stats["total_restore_tests"] += 1

        if success:
            self.stats["successful_restore_tests"] += 1
        else:
            self.stats["failed_restore_tests"] += 1

        # 更新平均持续时间
        n = self.stats["total_restore_tests"]
        old_avg = self.stats["avg_restore_duration"]
        new_avg = (old_avg * (n - 1) + duration) / n
        self.stats["avg_restore_duration"] = new_avg

    async def cleanup_old_backups(self):
        """清理旧备份（根据保留策略）"""
        logger.info("Cleaning up old backups...")

        now = datetime.utcnow()
        backups_to_remove = []

        for metadata in self.backup_history:
            age = (now - metadata.created_at).days

            # 检查是否应该删除
            should_remove = False

            if age > 365:  # 1年
                if self.stats["total_backups"] > self.config.retention_policy.get("yearly", 3):
                    should_remove = True
            elif age > 30:  # 1月
                if self.stats["total_backups"] > self.config.retention_policy.get("monthly", 12):
                    should_remove = True
            elif age > 7:  # 1周
                if self.stats["total_backups"] > self.config.retention_policy.get("weekly", 4):
                    should_remove = True
            elif age > 1:  # 1天
                if self.stats["total_backups"] > self.config.retention_policy.get("daily", 7):
                    should_remove = True

            if should_remove:
                backups_to_remove.append(metadata)

        # 删除旧备份
        for metadata in backups_to_remove:
            try:
                # 删除本地文件
                if os.path.exists(metadata.location):
                    if os.path.isfile(metadata.location):
                        os.remove(metadata.location)
                    else:
                        shutil.rmtree(metadata.location)

                # 删除对象存储中的备份
                if self.storage and metadata.backup_url:
                    # 从URL提取对象键
                    object_key = metadata.backup_url.split("/")[-1]
                    await self.storage.delete_file(object_key)

                # 从历史中移除
                self.backup_history.remove(metadata)

                logger.info(f"Old backup removed: {metadata.backup_id}")

            except Exception as e:
                logger.error(f"Failed to remove backup {metadata.backup_id}: {str(e)}")

    async def get_backup_stats(self) -> Dict[str, Any]:
        """
        获取备份统计信息

        Returns:
            备份统计字典
        """
        # 统计各类型的备份
        backup_type_counts = {}
        for metadata in self.backup_history:
            backup_type = metadata.backup_type.value
            if backup_type not in backup_type_counts:
                backup_type_counts[backup_type] = 0
            backup_type_counts[backup_type] += 1

        return {
            "total_backups": len(self.backup_history),
            "backup_types": backup_type_counts,
            "total_size_mb": (sum(m.file_size for m in self.backup_history) / (1024 * 1024)),
            "total_size_gb": (sum(m.file_size for m in self.backup_history) / (1024 * 1024 * 1024)),
            "recent_backups": [m.to_dict() for m in reversed(self.backup_history[-10:])],
            "stats": self.stats,
            "next_scheduled_backup": (
                (
                    datetime.utcnow() + timedelta(hours=self.config.full_backup_interval_hours)
                ).isoformat()
                if self.config.enable_scheduled_backups
                else None
            ),
        }


# 全局备份管理器实例
backup_manager: Optional[BackupManager] = None


def init_backup_manager(
    config: Optional[BackupConfig] = None,
    storage_service: Optional[ObjectStorageService] = None,
) -> BackupManager:
    """
    初始化备份管理器

    Args:
        config: 备份配置
        storage_service: 对象存储服务

    Returns:
        BackupManager实例

    Example:
    -------
    ```python
    from .backup_manager import (
        init_backup_manager,
        backup_manager,
        BackupConfig,
    )

    # 创建配置
    config = BackupConfig(
        db_host="localhost",
        db_name="zhineng_kb",
        backup_dir="/backups",
        enable_compression=True,
        enable_recovery_tests=True,
    )

    # 初始化
    backup_manager = init_backup_manager(config, storage_service)

    # 创建备份
    metadata = await backup_manager.create_backup()

    print(f"Backup created: {metadata.backup_id}")

    # 恢复备份
    result = await backup_manager.restore_backup(
        backup_id=metadata.backup_id,
        target_db_name="zhineng_kb_restored",
    )

    print(f"Restore status: {result['status']}")

    # 获取统计
    stats = await backup_manager.get_backup_stats()
    print(f"Backup stats: {stats}")
    ```
    """
    manager = BackupManager(
        config=config,
        storage_service=storage_service,
    )

    # 导出全局实例
    global backup_manager
    backup_manager = manager

    logger.info("Backup Manager initialized")

    return manager


__all__ = [
    "BackupType",
    "BackupStatus",
    "RecoveryStatus",
    "BackupConfig",
    "BackupMetadata",
    "BackupManager",
    "backup_manager",
    "init_backup_manager",
]
