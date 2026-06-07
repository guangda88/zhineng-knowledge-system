# -*- coding: utf-8 -*-
"""数据导入工具 — asyncpg 版

批量导入数据到系统，支持多种数据格式和来源
"""

import asyncio
import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import aiofiles
import asyncpg

from backend.core.dependency_injection import get_db_pool

logger = logging.getLogger(__name__)

INPUT_DIR = Path("/home/ai/lingzhi/analytics/data")
BATCH_SIZE = 100


class DataImporter:
    """数据导入器"""

    def __init__(self, pool: asyncpg.Pool, batch_size: int = BATCH_SIZE):
        self.pool = pool
        self.batch_size = batch_size
        self.stats = {
            "users_imported": 0,
            "documents_imported": 0,
            "chunks_imported": 0,
            "annotations_imported": 0,
            "searches_imported": 0,
            "errors": [],
        }

    async def import_from_json(self, file_path: Path) -> Dict[str, Any]:
        logger.info(f"Importing data from JSON: {file_path}")

        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()
            data = json.loads(content)

        if "users" in data:
            await self._import_users_batch(data["users"])
        if "documents" in data:
            await self._import_documents_batch(data["documents"])
        if "search_history" in data:
            await self._import_search_history_batch(data["search_history"])

        logger.info(f"Done: imported data from {file_path}")
        return self.stats

    async def import_from_csv(self, file_path: Path, data_type: str) -> Dict[str, Any]:
        logger.info(f"Importing {data_type} from CSV: {file_path}")

        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()

        reader = csv.DictReader(content.splitlines())
        data = list(reader)

        if data_type == "users":
            await self._import_users_batch(data)
        elif data_type == "search_history":
            await self._import_search_history_batch(data)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

        logger.info(f"Done: imported {data_type} from {file_path}")
        return self.stats

    async def _import_users_batch(self, users_data: List[Dict[str, Any]]):
        logger.info(f"Importing {len(users_data)} users in batches...")

        async with self.pool.acquire() as conn:
            for i in range(0, len(users_data), self.batch_size):
                batch = users_data[i : i + self.batch_size]
                for user_data in batch:
                    try:
                        last_login = (
                            datetime.fromisoformat(user_data["last_login"])
                            if user_data.get("last_login")
                            else None
                        )
                        await conn.execute(
                            """INSERT INTO users (username, email, password_hash, full_name,
                               is_active, is_admin, last_login)
                               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                            user_data.get("username", f"imported_{self.stats['users_imported']}"),
                            user_data.get("email"),
                            user_data.get("password_hash", "placeholder_hash"),
                            user_data.get("full_name"),
                            user_data.get("is_active", True),
                            user_data.get("is_admin", False),
                            last_login,
                        )
                        self.stats["users_imported"] += 1
                    except Exception as e:
                        self.stats["errors"].append({"type": "user", "data": user_data, "error": str(e)})
                        logger.warning(f"Failed to import user: {e}")

                logger.info(f"Imported {self.stats['users_imported']}/{len(users_data)} users")

        logger.info(f"Done: {self.stats['users_imported']} users")

    async def _import_documents_batch(self, docs_data: List[Dict[str, Any]]):
        logger.info(f"Importing {len(docs_data)} documents in batches...")

        async with self.pool.acquire() as conn:
            for i in range(0, len(docs_data), self.batch_size):
                batch = docs_data[i : i + self.batch_size]
                for doc_data in batch:
                    try:
                        row = await conn.fetchrow(
                            """INSERT INTO documents (title, content, file_type, extension,
                               uploader_id, file_path, file_size, status)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, 'processed')
                               RETURNING id""",
                            doc_data.get("title", "Imported Document"),
                            doc_data.get("content", ""),
                            doc_data.get("file_type", "text/plain"),
                            doc_data.get("extension", ".txt"),
                            doc_data.get("uploader_id", 1),
                            doc_data.get("file_path", ""),
                            doc_data.get("file_size", 0),
                        )
                        doc_id = row["id"]
                        self.stats["documents_imported"] += 1

                        for j, chunk_data in enumerate(doc_data.get("chunks", [])):
                            metadata = json.dumps(chunk_data.get("metadata", {}))
                            await conn.execute(
                                """INSERT INTO document_chunks (document_id, chunk_index, content, metadata)
                                   VALUES ($1, $2, $3, $4)""",
                                doc_id, j, chunk_data.get("content", ""), metadata,
                            )
                            self.stats["chunks_imported"] += 1

                    except Exception as e:
                        self.stats["errors"].append({"type": "document", "data": doc_data, "error": str(e)})
                        logger.warning(f"Failed to import document: {e}")

                logger.info(f"Imported {self.stats['documents_imported']}/{len(docs_data)} documents")

        logger.info(f"Done: {self.stats['documents_imported']} documents")

    async def _import_search_history_batch(self, history_data: List[Dict[str, Any]]):
        logger.info(f"Importing {len(history_data)} search histories in batches...")

        async with self.pool.acquire() as conn:
            for i in range(0, len(history_data), self.batch_size):
                batch = history_data[i : i + self.batch_size]
                for hist_data in batch:
                    try:
                        created_at = (
                            datetime.fromisoformat(hist_data["created_at"])
                            if hist_data.get("created_at")
                            else datetime.now()
                        )
                        metadata = json.dumps(hist_data.get("metadata", {}))
                        await conn.execute(
                            """INSERT INTO search_history (user_id, query, search_type, results_count,
                               response_time_ms, created_at, metadata)
                               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                            hist_data.get("user_id", 1),
                            hist_data.get("query", ""),
                            hist_data.get("search_type", "keyword"),
                            hist_data.get("results_count", 0),
                            hist_data.get("response_time_ms", 0),
                            created_at,
                            metadata,
                        )
                        self.stats["searches_imported"] += 1
                    except Exception as e:
                        self.stats["errors"].append({"type": "search_history", "data": hist_data, "error": str(e)})
                        logger.warning(f"Failed to import search history: {e}")

                logger.info(f"Imported {self.stats['searches_imported']}/{len(history_data)} searches")

        logger.info(f"Done: {self.stats['searches_imported']} searches")

    async def export_import_log(self, output_dir: Path):
        log_file = output_dir / f"import_log_{datetime.now():%Y%m%d_%H%M%S}.json"
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "statistics": self.stats,
            "error_details": self.stats["errors"][:100],
        }
        async with aiofiles.open(log_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(log_data, ensure_ascii=False, indent=2, default=str))
        logger.info(f"Import log exported to {log_file}")
        return log_file


async def generate_sample_import_data(output_dir: Path):
    logger.info("Generating sample import data...")
    output_dir.mkdir(parents=True, exist_ok=True)

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
    async with aiofiles.open(users_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps({"users": users_data}, ensure_ascii=False, indent=2))
    logger.info(f"Done: {len(users_data)} sample users")

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
    async with aiofiles.open(search_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps({"search_history": search_data}, ensure_ascii=False, indent=2))
    logger.info(f"Done: {len(search_data)} sample searches")

    return {"users_file": str(users_file), "search_file": str(search_file)}


async def main():
    logger.info("=" * 50)
    logger.info("Starting Data Import (asyncpg)")
    logger.info("=" * 50)

    pool = get_db_pool()
    try:
        sample_files = await generate_sample_import_data(INPUT_DIR)
        importer = DataImporter(pool, batch_size=BATCH_SIZE)
        await importer.import_from_json(Path(sample_files["users_file"]))
        await importer.import_from_json(Path(sample_files["search_file"]))
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


if __name__ == "__main__":
    asyncio.run(main())
