# -*- coding: utf-8 -*-
"""
数据导入工具
Data Importer

批量导入数据到系统，支持多种数据格式和来源
"""

import sys
sys.path.insert(0, '/home/ai/zhineng-knowledge-system/services/web_app/backend')

import asyncio
import logging
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import aiofiles

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func

from database.models import (
    Base, User, Document, DocumentChunk, Annotation,
    SearchHistory
)
from database.repository import UserRepository, DocumentRepository, ChunkRepository
from common.logging_config import setup_logging

logger = setup_logging(__name__)

# =============================================================================
# 配置
# =============================================================================

DATABASE_URL = "postgresql+asyncpg://tcm_admin:tcm_secure_pass_2024@localhost:5432/tcm_kb"
INPUT_DIR = Path("/home/ai/zhineng-knowledge-system/analytics/data")
BATCH_SIZE = 100  # 每批处理数量
MAX_CONCURRENT = 5  # 最大并发数

# =============================================================================
# 数据导入器类
# =============================================================================

class DataImporter:
    """数据导入器"""

    def __init__(self, engine, batch_size: int = BATCH_SIZE):
        self.engine = engine
        self.batch_size = batch_size
        self.session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

        # 创建仓储
        self.user_repo = UserRepository
        self.doc_repo = DocumentRepository
        self.chunk_repo = ChunkRepository

        self.stats = {
            "users_imported": 0,
            "documents_imported": 0,
            "chunks_imported": 0,
            "annotations_imported": 0,
            "searches_imported": 0,
            "errors": [],
        }

    async def import_from_json(self, file_path: Path) -> Dict[str, Any]:
        """从JSON文件导入数据"""
        logger.info(f"Importing data from JSON: {file_path}")

        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = json.loads(content)

        # 根据数据类型导入
        if "users" in data:
            await self._import_users_batch(data["users"])

        if "documents" in data:
            await self._import_documents_batch(data["documents"])

        if "search_history" in data:
            await self._import_search_history_batch(data["search_history"])

        logger.info(f"✅ Imported data from {file_path}")
        return self.stats

    async def import_from_csv(self, file_path: Path, data_type: str) -> Dict[str, Any]:
        """从CSV文件导入数据"""
        logger.info(f"Importing {data_type} from CSV: {file_path}")

        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()

        # 解析CSV
        reader = csv.DictReader(content.splitlines())
        data = list(reader)

        # 根据数据类型导入
        if data_type == "users":
            await self._import_users_batch(data)
        elif data_type == "search_history":
            await self._import_search_history_batch(data)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

        logger.info(f"✅ Imported {data_type} from {file_path}")
        return self.stats

    async def _import_users_batch(self, users_data: List[Dict[str, Any]]):
        """批量导入用户数据"""
        logger.info(f"Importing {len(users_data)} users in batches...")

        async with self.session_factory() as session:
            for i in range(0, len(users_data), self.batch_size):
                batch = users_data[i:i + self.batch_size]

                for user_data in batch:
                    try:
                        user = User(
                            username=user_data.get("username", f"imported_{self.stats['users_imported']}"),
                            email=user_data.get("email"),
                            password_hash=user_data.get("password_hash", "placeholder_hash"),
                            full_name=user_data.get("full_name"),
                            is_active=user_data.get("is_active", True),
                            is_admin=user_data.get("is_admin", False),
                            last_login=datetime.fromisoformat(user_data["last_login"]) if user_data.get("last_login") else None,
                        )

                        session.add(user)
                        self.stats["users_imported"] += 1

                    except Exception as e:
                        self.stats["errors"].append({
                            "type": "user",
                            "data": user_data,
                            "error": str(e),
                        })
                        logger.warning(f"Failed to import user: {e}")

                await session.commit()
                logger.info(f"Imported {self.stats['users_imported']}/{len(users_data)} users")

        logger.info(f"✅ Imported {self.stats['users_imported']} users")

    async def _import_documents_batch(self, docs_data: List[Dict[str, Any]]):
        """批量导入文档数据"""
        logger.info(f"Importing {len(docs_data)} documents in batches...")

        async with self.session_factory() as session:
            for i in range(0, len(docs_data), self.batch_size):
                batch = docs_data[i:i + self.batch_size]

                for doc_data in batch:
                    try:
                        document = Document(
                            title=doc_data.get("title", "Imported Document"),
                            content=doc_data.get("content", ""),
                            file_type=doc_data.get("file_type", "text/plain"),
                            extension=doc_data.get("extension", ".txt"),
                            uploader_id=doc_data.get("uploader_id", 1),
                            file_path=doc_data.get("file_path", ""),
                            file_size=doc_data.get("file_size", 0),
                            status="processed",
                        )

                        session.add(document)
                        self.stats["documents_imported"] += 1

                        # 导入文档块
                        chunks_data = doc_data.get("chunks", [])
                        for j, chunk_data in enumerate(chunks_data):
                            chunk = DocumentChunk(
                                document_id=self.stats["documents_imported"],  # 注意：这里需要调整
                                chunk_index=j,
                                content=chunk_data.get("content", ""),
                                metadata=chunk_data.get("metadata", {}),
                            )

                            session.add(chunk)
                            self.stats["chunks_imported"] += 1

                    except Exception as e:
                        self.stats["errors"].append({
                            "type": "document",
                            "data": doc_data,
                            "error": str(e),
                        })
                        logger.warning(f"Failed to import document: {e}")

                await session.commit()
                logger.info(f"Imported {self.stats['documents_imported']}/{len(docs_data)} documents")

        logger.info(f"✅ Imported {self.stats['documents_imported']} documents")

    async def _import_search_history_batch(self, history_data: List[Dict[str, Any]]):
        """批量导入搜索历史数据"""
        logger.info(f"Importing {len(history_data)} search histories in batches...")

        async with self.session_factory() as session:
            for i in range(0, len(history_data), self.batch_size):
                batch = history_data[i:i + self.batch_size]

                for hist_data in batch:
                    try:
                        history = SearchHistory(
                            user_id=hist_data.get("user_id", 1),
                            query=hist_data.get("query", ""),
                            search_type=hist_data.get("search_type", "keyword"),
                            results_count=hist_data.get("results_count", 0),
                            response_time_ms=hist_data.get("response_time_ms", 0),
                            created_at=datetime.fromisoformat(hist_data["created_at"]) if hist_data.get("created_at") else datetime.now(),
                            metadata=hist_data.get("metadata", {}),
                        )

                        session.add(history)
                        self.stats["searches_imported"] += 1

                    except Exception as e:
                        self.stats["errors"].append({
                            "type": "search_history",
                            "data": hist_data,
                            "error": str(e),
                        })
                        logger.warning(f"Failed to import search history: {e}")

                await session.commit()
                logger.info(f"Imported {self.stats['searches_imported']}/{len(history_data)} searches")

        logger.info(f"✅ Imported {self.stats['searches_imported']} searches")

    async def export_import_log(self, output_dir: Path):
        """导出导入日志"""
        log_file = output_dir / f"import_log_{datetime.now():%Y%m%d_%H%M%S}.json"

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "statistics": self.stats,
            "error_details": self.stats["errors"][:100],  # 只保留前100个错误
        }

        async with aiofiles.open(log_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(log_data, ensure_ascii=False, indent=2, default=str))

        logger.info(f"✅ Import log exported to {log_file}")

        return log_file


# =============================================================================
# 示例数据生成器
# =============================================================================

async def generate_sample_import_data(output_dir: Path):
    """生成示例导入数据"""
    logger.info("Generating sample import data...")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成用户数据
    users_data = []
    for i in range(1, 101):
        users_data.append({
            "username": f"import_user_{i}",
            "email": f"import_user_{i}@example.com",
            "password_hash": "placeholder_hash",
            "full_name": f"Import User {i}",
            "is_active": True,
            "is_admin": False,
            "last_login": datetime.now().isoformat(),
        })

    users_file = output_dir / "sample_users.json"
    async with aiofiles.open(users_file, 'w', encoding='utf-8') as f:
        await f.write(json.dumps({"users": users_data}, ensure_ascii=False, indent=2))

    logger.info(f"✅ Generated sample users: {len(users_data)}")

    # 生成搜索历史数据
    search_data = []
    for i in range(1, 1001):
        search_data.append({
            "user_id": (i % 100) + 1,
            "query": f"搜索查询 {i}",
            "search_type": "keyword",
            "results_count": i % 50,
            "response_time_ms": (i % 1000) + 50,
            "created_at": datetime.now().isoformat(),
            "metadata": {},
        })

    search_file = output_dir / "sample_search_history.json"
    async with aiofiles.open(search_file, 'w', encoding='utf-8') as f:
        await f.write(json.dumps({"search_history": search_data}, ensure_ascii=False, indent=2))

    logger.info(f"✅ Generated sample searches: {len(search_data)}")

    return {
        "users_file": str(users_file),
        "search_file": str(search_file),
    }


# =============================================================================
# 主函数
# =============================================================================

async def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("Starting Data Import")
    logger.info("=" * 50)

    # 创建数据库引擎
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20
    )

    try:
        # 生成示例数据
        sample_files = await generate_sample_import_data(INPUT_DIR)

        # 创建导入器
        importer = DataImporter(engine, batch_size=BATCH_SIZE)

        # 导入用户
        await importer.import_from_json(Path(sample_files["users_file"]))

        # 导入搜索历史
        await importer.import_from_json(Path(sample_files["search_file"]))

        # 导出导入日志
        await importer.export_import_log(INPUT_DIR)

        logger.info("=" * 50)
        logger.info("Data Import Complete")
        logger.info(f"Users imported: {importer.stats['users_imported']}")
        logger.info(f"Searches imported: {importer.stats['searches_imported']}")
        logger.info(f"Errors: {len(importer.stats['errors'])}")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Error importing data: {e}", exc_info=True)
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
