"""Schema迁移幂等检查工具

每次schema变更前检查是否已执行，防止重复运行。
用法: python3 -m backend.services.retrieval.idempotent <migration_name>
"""

import hashlib
import json
import logging
from pathlib import Path
logger = logging.getLogger(__name__)

MIGRATION_LOG = Path(__file__).resolve().parent.parent.parent.parent / "data" / "migration_log.json"


def _load_log() -> dict:
    if MIGRATION_LOG.exists():
        return json.loads(MIGRATION_LOG.read_text(encoding="utf-8"))
    return {"migrations": {}}


def _save_log(log: dict) -> None:
    MIGRATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    MIGRATION_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash_sql(sql: str) -> str:
    return hashlib.sha256(sql.strip().encode()).hexdigest()[:16]


def check_and_record(migration_name: str, sql: str, dry_run: bool = False) -> bool:
    log = _load_log()
    migrations = log["migrations"]
    sql_hash = _hash_sql(sql)

    if migration_name in migrations:
        existing = migrations[migration_name]
        if existing.get("status") == "completed" and existing.get("sql_hash") == sql_hash:
            logger.info(f"迁移 {migration_name} 已完成（hash={sql_hash}），跳过")
            return False
        if existing.get("status") == "completed" and existing.get("sql_hash") != sql_hash:
            logger.warning(f"迁移 {migration_name} SQL已变更（旧={existing.get('sql_hash')}, 新={sql_hash}），需重新执行")

    if dry_run:
        logger.info(f"[DRY RUN] 迁移 {migration_name} 将执行")
        return True

    migrations[migration_name] = {
        "status": "in_progress",
        "sql_hash": sql_hash,
    }
    _save_log(log)
    return True


def mark_completed(migration_name: str, rows_affected: int = 0) -> None:
    log = _load_log()
    entry = log["migrations"].get(migration_name, {})
    entry["status"] = "completed"
    entry["rows_affected"] = rows_affected
    import datetime
    entry["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log["migrations"][migration_name] = entry
    _save_log(log)
    logger.info(f"迁移 {migration_name} 完成（{rows_affected} rows）")


def mark_failed(migration_name: str, error: str) -> None:
    log = _load_log()
    entry = log["migrations"].get(migration_name, {})
    entry["status"] = "failed"
    entry["error"] = error
    import datetime
    entry["failed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log["migrations"][migration_name] = entry
    _save_log(log)
    logger.error(f"迁移 {migration_name} 失败: {error}")


def list_migrations() -> dict:
    return _load_log()["migrations"]
