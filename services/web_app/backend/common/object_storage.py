# -*- coding: utf-8 -*-
"""
对象存储服务
Object Storage Service

实现S3兼容的对象存储（MinIO/AWS S3），支持：
- 多存储桶管理
- 分片上传
- 文件元数据
- 存储分层（热/温/冷）
- CDN集成
- 自动压缩
- 生命周期管理
"""

import os
import logging
import mimetypes
import hashlib
import asyncio
from typing import Optional, Dict, List, Any, AsyncIterator, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from io import BytesIO
import json

# S3 SDK imports
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config
import aioboto3

logger = logging.getLogger(__name__)


class StorageTier(str, Enum):
    """存储层级"""

    HOT = "hot"  # 热数据（频繁访问，SSD，0延迟）
    WARM = "warm"  # 温数据（偶尔访问，HDD，低延迟）
    COLD = "cold"  # 冷数据（归档，对象存储，中延迟）
    ARCHIVE = "archive"  # 归档数据（深度归档，磁带/云存储，高延迟）


class StorageClass(str, Enum):
    """存储类（S3标准）"""

    STANDARD = "STANDARD"  # 标准存储（热数据）
    INFREQUENT_ACCESS = "STANDARD_IA"  # 不常访问（温数据）
    ARCHIVE = "GLACIER"  # 归档（冷数据）
    INTELLIGENT_TIERING = "INTELLIGENT_TIERING"  # 智能分层


class FileMetadata:
    """文件元数据管理"""

    @staticmethod
    def generate_metadata(
        file_name: str,
        content_type: str,
        user_id: int,
        tier: StorageTier = StorageTier.HOT,
        custom_metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        生成文件元数据

        Args:
            file_name: 文件名
            content_type: MIME类型
            user_id: 用户ID
            tier: 存储层级
            custom_metadata: 自定义元数据

        Returns:
            元数据字典
        """
        metadata = {
            "file-name": file_name,
            "content-type": content_type,
            "user-id": str(user_id),
            "storage-tier": tier.value,
            "uploaded-at": datetime.utcnow().isoformat(),
            "file-size": "0",  # 将在更新
            "file-hash": "",  # 将在更新
        }

        if custom_metadata:
            metadata.update(custom_metadata)

        return metadata

    @staticmethod
    def extract_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取元数据

        Args:
            metadata: S3元数据字典

        Returns:
            解析后的元数据
        """
        return {
            "file_name": metadata.get("file-name"),
            "content_type": metadata.get("content-type"),
            "user_id": int(metadata.get("user-id", 0)),
            "storage_tier": metadata.get("storage-tier"),
            "uploaded_at": metadata.get("uploaded-at"),
            "file_size": int(metadata.get("file-size", 0)),
            "file_hash": metadata.get("file-hash"),
            "custom": {
                k: v
                for k, v in metadata.items()
                if k
                not in [
                    "file-name",
                    "content-type",
                    "user-id",
                    "storage-tier",
                    "uploaded-at",
                    "file-size",
                    "file-hash",
                ]
            },
        }


@dataclass
class StorageConfig:
    """存储配置"""

    # S3/MinIO配置
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    region: str = "us-east-1"
    bucket_prefix: str = "zhineng"
    secure: bool = True

    # 存储桶配置
    hot_bucket: str = "zhineng-hot"
    warm_bucket: str = "zhineng-warm"
    cold_bucket: str = "zhineng-cold"
    archive_bucket: str = "zhineng-archive"

    # 分片上传配置
    multipart_threshold: int = 100 * 1024 * 1024  # 100MB
    multipart_chunksize: int = 25 * 1024 * 1024  # 25MB
    max_concurrent_uploads: int = 10

    # 生命周期配置
    transition_to_warm_days: int = 30
    transition_to_cold_days: int = 90
    transition_to_archive_days: int = 365
    expiration_days: int = 2555  # 7 years

    # CDN配置
    cdn_enabled: bool = False
    cdn_domain: Optional[str] = None

    # 压缩配置
    auto_compress: bool = True
    compress_mimes: List[str] = field(
        default_factory=lambda: [
            "text/plain",
            "text/html",
            "text/css",
            "application/javascript",
            "application/json",
            "application/xml",
        ]
    )

    # 缓存配置
    cache_control: str = "public, max-age=3600"
    cache_ttl: int = 3600  # 1 hour


class ObjectStorageService:
    """
    对象存储服务

    提供S3兼容的对象存储功能。

    Features:
    - 多存储桶管理
    - 分片上传
    - 存储分层
    - 元数据管理
    - CDN集成
    - 自动压缩
    - 生命周期管理
    """

    def __init__(self, config: StorageConfig):
        """
        初始化对象存储服务

        Args:
            config: 存储配置
        """
        self.config = config

        # 创建boto3 session（同步）
        self.session = boto3.Session(
            region_name=config.region,
        )

        # 创建S3客户端
        self.s3_client = self.session.client(
            "s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                max_pool_connections=50,
            ),
        )

        # 创建资源（异步）
        self.resource = self.session.resource(
            "s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
        )

        # 初始化存储桶
        self.buckets = {
            StorageTier.HOT: config.hot_bucket,
            StorageTier.WARM: config.warm_bucket,
            StorageTier.COLD: config.cold_bucket,
            StorageTier.ARCHIVE: config.archive_bucket,
        }

        logger.info(f"Object Storage Service initialized " f"(endpoint: {config.endpoint_url})")

    async def ensure_buckets_exist(self):
        """确保所有存储桶存在"""
        for tier, bucket_name in self.buckets.items():
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
                logger.debug(f"Bucket exists: {bucket_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    # 创建存储桶
                    self._create_bucket(bucket_name, tier)
                else:
                    logger.error(f"Error checking bucket {bucket_name}: {str(e)}")
                    raise

    def _create_bucket(self, bucket_name: str, tier: StorageTier):
        """
        创建存储桶

        Args:
            bucket_name: 存储桶名称
            tier: 存储层级
        """
        try:
            # 创建存储桶
            location_constraint = {
                StorageTier.HOT: None,
                StorageTier.WARM: None,
                StorageTier.COLD: None,
                StorageTier.ARCHIVE: "us-east-1",
            }[tier]

            if location_constraint:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": location_constraint},
                )
            else:
                self.s3_client.create_bucket(Bucket=bucket_name)

            # 配置生命周期策略
            self._configure_lifecycle(bucket_name, tier)

            # 配置版本控制
            self.s3_client.put_bucket_versioning(
                Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
            )

            logger.info(f"Bucket created: {bucket_name} (tier: {tier.value})")

        except ClientError as e:
            logger.error(f"Failed to create bucket {bucket_name}: {str(e)}")
            raise

    def _configure_lifecycle(self, bucket_name: str, tier: StorageTier):
        """
        配置生命周期策略

        Args:
            bucket_name: 存储桶名称
            tier: 存储层级
        """
        rules = []

        # 添加转换规则
        if tier == StorageTier.HOT:
            # 热数据 → 温数据
            rules.append(
                {
                    "ID": f"{bucket_name}-to-warm",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "Transitions": [
                        {"Days": self.config.transition_to_warm_days, "StorageClass": "STANDARD_IA"}
                    ],
                }
            )

        if tier in [StorageTier.HOT, StorageTier.WARM]:
            # 热/温数据 → 冷数据
            rules.append(
                {
                    "ID": f"{bucket_name}-to-cold",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "Transitions": [
                        {"Days": self.config.transition_to_cold_days, "StorageClass": "GLACIER"}
                    ],
                }
            )

        # 添加过期规则（所有层级）
        rules.append(
            {
                "ID": f"{bucket_name}-expiration",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "Expiration": {
                    "Days": self.config.expiration_days,
                },
            }
        )

        if rules:
            try:
                self.s3_client.put_bucket_lifecycle_configuration(
                    Bucket=bucket_name, LifecycleConfiguration={"Rules": rules}
                )
                logger.info(f"Lifecycle configured for {bucket_name}")
            except ClientError as e:
                logger.warning(f"Failed to configure lifecycle for {bucket_name}: {str(e)}")

    async def upload_file(
        self,
        file_path: str,
        object_key: str,
        tier: StorageTier = StorageTier.HOT,
        metadata: Optional[Dict[str, str]] = None,
        compress: bool = None,
    ) -> Dict[str, Any]:
        """
        上传文件

        Args:
            file_path: 本地文件路径
            object_key: 对象键（S3路径）
            tier: 存储层级
            metadata: 文件元数据
            compress: 是否压缩（None=使用配置）

        Returns:
            上传结果
        """
        # 确定是否压缩
        should_compress = compress if compress is not None else self.config.auto_compress
        compress = should_compress

        # 获取文件信息
        file_size = os.path.getsize(file_path)
        content_type = mimetypes.guess_type(file_path) or "application/octet-stream"
        file_name = os.path.basename(file_path)

        # 生成元数据
        final_metadata = FileMetadata.generate_metadata(
            file_name=file_name,
            content_type=content_type,
            user_id=0,  # TODO: 从参数获取
            tier=tier,
            custom_metadata=metadata,
        )

        # 更新文件大小和哈希
        file_hash = self._calculate_file_hash(file_path)
        final_metadata["file-size"] = str(file_size)
        final_metadata["file-hash"] = file_hash

        # 构建上传参数
        extra_args = {
            "Metadata": final_metadata,
        }

        # 添加压缩信息
        if compress:
            extra_args["ContentEncoding"] = "gzip"

        # 添加缓存控制
        extra_args["CacheControl"] = self.config.cache_control

        # 添加存储类
        storage_class = self._get_storage_class(tier)
        if storage_class:
            extra_args["StorageClass"] = storage_class

        # 根据文件大小选择上传方式
        if file_size < self.config.multipart_threshold:
            # 普通上传
            result = self.s3_client.upload_file(
                file_path,
                Bucket=self.buckets[tier],
                Key=object_key,
                ExtraArgs=extra_args,
            )
        else:
            # 分片上传
            result = await self._upload_multipart(
                file_path=file_path,
                object_key=object_key,
                tier=tier,
                extra_args=extra_args,
            )

        # 生成CDN URL
        cdn_url = self._get_cdn_url(tier, object_key)

        logger.info(
            f"File uploaded: {object_key} "
            f"(tier: {tier.value}, size: {file_size}, cdn: {cdn_url})"
        )

        return {
            "object_key": object_key,
            "bucket": self.buckets[tier],
            "tier": tier.value,
            "file_size": file_size,
            "file_hash": file_hash,
            "content_type": content_type,
            "cdn_url": cdn_url,
            "compressed": compress,
            "storage_class": storage_class,
            "metadata": final_metadata,
        }

    async def _upload_multipart(
        self,
        file_path: str,
        object_key: str,
        tier: StorageTier,
        extra_args: Dict[str, Any],
    ) -> Any:
        """
        分片上传

        Args:
            file_path: 文件路径
            object_key: 对象键
            tier: 存储层级
            extra_args: 额外参数

        Returns:
            上传结果
        """
        file_size = os.path.getsize(file_path)
        chunk_size = self.config.multipart_chunksize

        # 创建分片上传
        mpu = self.s3_client.create_multipart_upload(
            Bucket=self.buckets[tier], Key=object_key, **extra_args
        )

        parts = []

        # 上传分片
        with open(file_path, "rb") as f:
            part_number = 1
            while True:
                data = f.read(chunk_size)
                if not data:
                    break

                part = mpu.Part(part_number)
                part.upload(Body=data)

                parts.append({"PartNumber": part_number, "ETag": part.e_tag})

                part_number += 1

                logger.debug(f"Uploaded part {part_number}/{len(parts)} " f"for {object_key}")

        # 完成分片上传
        result = mpu.complete(MultipartUpload={"Parts": parts})

        return result

    async def download_file(
        self,
        object_key: str,
        tier: StorageTier = StorageTier.HOT,
        file_path: Optional[str] = None,
        range_header: Optional[str] = None,
    ) -> BytesIO:
        """
        下载文件

        Args:
            object_key: 对象键
            tier: 存储层级
            file_path: 保存路径（None=返回BytesIO）
            range_header: Range头（用于断点续传）

        Returns:
            文件内容（BytesIO）
        """
        try:
            # 构建下载参数
            params = {}
            if range_header:
                params["Range"] = range_header

            # 下载文件
            response = self.s3_client.get_object(
                Bucket=self.buckets[tier], Key=object_key, **params
            )

            # 获取文件内容
            content = response["Body"]

            # 如果指定了保存路径
            if file_path:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "wb") as f:
                    f.write(content.read())

                logger.info(f"File downloaded: {object_key} to {file_path}")
            else:
                logger.info(f"File downloaded: {object_key} to memory")

            return content

        except ClientError as e:
            logger.error(f"Failed to download {object_key}: {str(e)}")
            raise

    async def delete_file(
        self,
        object_key: str,
        tier: StorageTier = StorageTier.HOT,
        version_id: Optional[str] = None,
    ) -> bool:
        """
        删除文件

        Args:
            object_key: 对象键
            tier: 存储层级
            version_id: 版本ID（None=删除最新版本）

        Returns:
            是否成功
        """
        try:
            params = {"Bucket": self.buckets[tier], "Key": object_key}
            if version_id:
                params["VersionId"] = version_id

            self.s3_client.delete_object(**params)

            logger.info(f"File deleted: {object_key} (version: {version_id})")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete {object_key}: {str(e)}")
            return False

    async def move_file(
        self,
        source_key: str,
        source_tier: StorageTier,
        target_key: str,
        target_tier: StorageTier,
    ) -> bool:
        """
        移动文件（存储分层）

        Args:
            source_key: 源对象键
            source_tier: 源存储层级
            target_key: 目标对象键
            target_tier: 目标存储层级

        Returns:
            是否成功
        """
        try:
            # 复制对象
            copy_source = f"{self.buckets[source_tier]}/{source_key}"
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.buckets[target_tier],
                Key=target_key,
            )

            # 删除源对象
            await self.delete_file(source_key, source_tier)

            logger.info(
                f"File moved: {source_key} ({source_tier.value}) "
                f"→ {target_key} ({target_tier.value})"
            )
            return True

        except ClientError as e:
            logger.error(f"Failed to move {source_key}: {str(e)}")
            return False

    async def list_files(
        self,
        tier: StorageTier = StorageTier.HOT,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        列出文件

        Args:
            tier: 存储层级
            prefix: 前缀（用于分页或过滤）
            max_keys: 最大返回数量

        Returns:
            文件列表
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.buckets[tier],
                Prefix=prefix,
                MaxKeys=max_keys,
            )

            files = []
            for obj in response.get("Contents", []):
                files.append(
                    {
                        "object_key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "etag": obj["ETag"],
                        "storage_class": obj.get("StorageClass", "STANDARD"),
                        "metadata": obj.get("Metadata", {}),
                    }
                )

            return files

        except ClientError as e:
            logger.error(f"Failed to list files: {str(e)}")
            return []

    async def get_file_info(
        self,
        object_key: str,
        tier: StorageTier = StorageTier.HOT,
        version_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        获取文件信息

        Args:
            object_key: 对象键
            tier: 存储层级
            version_id: 版本ID

        Returns:
            文件信息
        """
        try:
            params = {"Bucket": self.buckets[tier], "Key": object_key}
            if version_id:
                params["VersionId"] = version_id

            response = self.s3_client.head_object(**params)

            return {
                "object_key": object_key,
                "size": response["ContentLength"],
                "last_modified": response["LastModified"],
                "etag": response["ETag"],
                "content_type": response["ContentType"],
                "metadata": response.get("Metadata", {}),
                "storage_class": response.get("StorageClass", "STANDARD"),
                "cdn_url": self._get_cdn_url(tier, object_key),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None
            logger.error(f"Failed to get file info: {str(e)}")
            raise

    def _get_storage_class(self, tier: StorageTier) -> str:
        """
        获取存储类

        Args:
            tier: 存储层级

        Returns:
            S3存储类
        """
        return {
            StorageTier.HOT: StorageClass.STANDARD.value,
            StorageTier.WARM: StorageClass.INFREQUENT_ACCESS.value,
            StorageTier.COLD: StorageClass.ARCHIVE.value,
            StorageTier.ARCHIVE: StorageClass.ARCHIVE.value,
        }[tier]

    def _get_cdn_url(self, tier: StorageTier, object_key: str) -> Optional[str]:
        """
        生成CDN URL

        Args:
            tier: 存储层级
            object_key: 对象键

        Returns:
            CDN URL（如果启用）
        """
        if not self.config.cdn_enabled or not self.config.cdn_domain:
            return None

        bucket = self.buckets[tier]
        return f"https://{self.config.cdn_domain}/{bucket}/{object_key}"

    def _calculate_file_hash(self, file_path: str) -> str:
        """
        计算文件哈希（SHA256）

        Args:
            file_path: 文件路径

        Returns:
            文件哈希
        """
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)

        return sha256.hexdigest()

    async def get_storage_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息

        Returns:
            存储统计字典
        """
        stats = {}

        for tier, bucket_name in self.buckets.items():
            try:
                # 获取存储桶大小
                cloudwatch = self.session.client("cloudwatch")

                # 注意：MinIO可能不支持CloudWatch
                # 使用S3 API计算大小
                total_size = 0
                file_count = 0

                continuation_token = None
                while True:
                    response = self.s3_client.list_objects_v2(
                        Bucket=bucket_name,
                        ContinuationToken=continuation_token,
                    )

                    for obj in response.get("Contents", []):
                        total_size += obj["Size"]
                        file_count += 1

                    continuation_token = response.get("NextContinuationToken")
                    if not continuation_token:
                        break

                stats[tier.value] = {
                    "bucket": bucket_name,
                    "total_size": total_size,
                    "file_count": file_count,
                    "size_mb": total_size / (1024 * 1024),
                    "size_gb": total_size / (1024 * 1024 * 1024),
                }

            except ClientError as e:
                logger.warning(f"Failed to get stats for {bucket_name}: {str(e)}")
                stats[tier.value] = {
                    "bucket": bucket_name,
                    "error": str(e),
                }

        return stats


# 全局对象存储服务实例
storage_service: Optional[ObjectStorageService] = None


def init_storage_service(config: StorageConfig) -> ObjectStorageService:
    """
    初始化对象存储服务

    Args:
        config: 存储配置

    Returns:
        ObjectStorageService实例

    Example:
    -------
    ```python
    from .object_storage import (
        init_storage_service,
        storage_service,
        StorageConfig,
        StorageTier,
    )

    # 创建配置
    config = StorageConfig(
        endpoint_url="http://localhost:9000",
        access_key_id="minioadmin",
        secret_access_key="minioadmin",
        region="us-east-1",
    )

    # 初始化服务
    storage_service = init_storage_service(config)

    # 确保存储桶存在
    await storage_service.ensure_buckets_exist()

    # 上传文件
    result = await storage_service.upload_file(
        file_path="/path/to/file.pdf",
        object_key="documents/user123/file.pdf",
        tier=StorageTier.HOT,
    )

    print(f"File uploaded: {result['cdn_url']}")
    ```
    """
    service = ObjectStorageService(config)

    # 导出全局实例
    global storage_service
    storage_service = service

    logger.info("Object Storage Service initialized")

    return service


__all__ = [
    "StorageTier",
    "StorageClass",
    "StorageConfig",
    "ObjectStorageService",
    "storage_service",
    "init_storage_service",
]
