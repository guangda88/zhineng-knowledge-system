# -*- coding: utf-8 -*-
"""数据验证工具 — asyncpg 版

验证数据质量，包括完整性、准确性、一致性、有效性、唯一性等
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import asyncpg

from backend.core.dependency_injection import get_db_pool

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/home/ai/lingzhi/analytics/reports")


class DataQualityMetric:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.pass_count = 0
        self.fail_count = 0
        self.total_count = 0
        self.issues: List[str] = []

    def add_pass(self, count: int = 1):
        self.pass_count += count
        self.total_count += count

    def add_fail(self, issue: str):
        self.fail_count += 1
        self.total_count += 1
        self.issues.append(issue)

    def get_score(self) -> float:
        if self.total_count == 0:
            return 100.0
        return (self.pass_count / self.total_count) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "score": self.get_score(),
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "total_count": self.total_count,
            "sample_issues": self.issues[:10],
            "total_issues": len(self.issues),
        }


class DataValidator:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.metrics: Dict[str, DataQualityMetric] = {}

    async def validate_all(self) -> Dict[str, Any]:
        logger.info("=" * 50)
        logger.info("Starting Data Validation (asyncpg)")
        logger.info("=" * 50)

        results = {}
        results["users"] = await self._validate_users()
        results["documents"] = await self._validate_documents()
        results["document_chunks"] = await self._validate_document_chunks()
        results["annotations"] = await self._validate_annotations()
        results["search_history"] = await self._validate_search_history()
        results["processing_jobs"] = await self._validate_processing_jobs()
        results["consistency"] = await self._validate_consistency()
        results["overall_score"] = self._calculate_overall_score(results)

        logger.info(f"Overall Data Quality Score: {results['overall_score']:.2f}%")
        return results

    async def _validate_users(self) -> Dict[str, Any]:
        logger.info("Validating users...")
        metric = DataQualityMetric("用户数据质量", "验证用户数据的完整性和准确性")

        async with self.pool.acquire() as conn:
            for field in ["username", "email", "password_hash"]:
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM users WHERE {field} IS NULL")
                cnt = row["cnt"]
                if cnt > 0:
                    metric.add_fail(f"用户{field}字段为空的数量: {cnt}")
                else:
                    metric.add_pass()

            for field in ["username", "email"]:
                row = await conn.fetchrow(
                    f"SELECT COUNT(*) as cnt FROM (SELECT {field}, COUNT(*) as c FROM users GROUP BY {field} HAVING COUNT(*) > 1) sub"
                )
                if row["cnt"] > 0:
                    metric.add_fail(f"用户{field}存在重复: {row['cnt']}个")
                else:
                    metric.add_pass()

            rows = await conn.fetch("SELECT email FROM users")
            bad_email = False
            for r in rows:
                if r["email"] and not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", r["email"]):
                    metric.add_fail(f"无效邮箱格式: {r['email']}")
                    bad_email = True
                    break
            if not bad_email:
                metric.add_pass()

            row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM users WHERE LENGTH(username) < 3")
            if row["cnt"] > 0:
                metric.add_fail(f"用户名长度不足3字符: {row['cnt']}个")
            else:
                metric.add_pass()

            row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM users WHERE LENGTH(password_hash) = 0")
            if row["cnt"] > 0:
                metric.add_fail(f"密码哈希为空: {row['cnt']}个")
            else:
                metric.add_pass()

        self.metrics["users"] = metric
        return metric.to_dict()

    async def _validate_documents(self) -> Dict[str, Any]:
        logger.info("Validating documents...")
        metric = DataQualityMetric("文档数据质量", "验证文档数据的完整性和有效性")

        async with self.pool.acquire() as conn:
            for field in ["title", "content", "uploader_id"]:
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM documents WHERE {field} IS NULL")
                if row["cnt"] > 0:
                    metric.add_fail(f"文档{field}字段为空: {row['cnt']}个")
                else:
                    metric.add_pass()

            row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM documents WHERE LENGTH(title) = 0")
            if row["cnt"] > 0:
                metric.add_fail(f"文档标题为空: {row['cnt']}个")
            else:
                metric.add_pass()

            row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM documents WHERE LENGTH(content) < 10")
            if row["cnt"] > 0:
                metric.add_fail(f"文档内容过短: {row['cnt']}个")
            else:
                metric.add_pass()

            valid_ext = [".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv"]
            placeholders = ",".join([f"${i+1}" for i in range(len(valid_ext))])
            row = await conn.fetchrow(
                f"SELECT COUNT(*) as cnt FROM documents WHERE extension NOT IN ({placeholders})",
                *valid_ext,
            )
            if row["cnt"] > 0:
                metric.add_fail(f"无效文件扩展名: {row['cnt']}个")
            else:
                metric.add_pass()

            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM documents WHERE file_size < 0 OR file_size > 52428800"
            )
            if row["cnt"] > 0:
                metric.add_fail(f"无效文件大小: {row['cnt']}个")
            else:
                metric.add_pass()

        self.metrics["documents"] = metric
        return metric.to_dict()

    async def _validate_document_chunks(self) -> Dict[str, Any]:
        logger.info("Validating document chunks...")
        metric = DataQualityMetric("文档块数据质量", "验证文档块数据的完整性和一致性")

        async with self.pool.acquire() as conn:
            for field in ["document_id", "content", "chunk_index"]:
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM document_chunks WHERE {field} IS NULL")
                if row["cnt"] > 0:
                    metric.add_fail(f"文档块{field}字段为空: {row['cnt']}个")
                else:
                    metric.add_pass()

            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM document_chunks WHERE LENGTH(content) < 100 OR LENGTH(content) > 10000"
            )
            if row["cnt"] > 0:
                metric.add_fail(f"文档块大小异常: {row['cnt']}个")
            else:
                metric.add_pass()

            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM document_chunks WHERE document_id NOT IN (SELECT id FROM documents)"
            )
            if row["cnt"] > 0:
                metric.add_fail(f"孤立的文档块: {row['cnt']}个")
            else:
                metric.add_pass()

        self.metrics["document_chunks"] = metric
        return metric.to_dict()

    async def _validate_annotations(self) -> Dict[str, Any]:
        logger.info("Validating annotations...")
        metric = DataQualityMetric("标注数据质量", "验证标注数据的完整性和有效性")

        async with self.pool.acquire() as conn:
            for field in ["document_id", "user_id", "content"]:
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM annotations WHERE {field} IS NULL")
                if row["cnt"] > 0:
                    metric.add_fail(f"标注{field}字段为空: {row['cnt']}个")
                else:
                    metric.add_pass()

            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM annotations WHERE end_offset < start_offset"
            )
            if row["cnt"] > 0:
                metric.add_fail(f"无效偏移量: {row['cnt']}个")
            else:
                metric.add_pass()

            for field, table in [("document_id", "documents"), ("user_id", "users")]:
                row = await conn.fetchrow(
                    f"SELECT COUNT(*) as cnt FROM annotations WHERE {field} NOT IN (SELECT id FROM {table})"
                )
                if row["cnt"] > 0:
                    metric.add_fail(f"孤立标注（{field}）: {row['cnt']}个")
                else:
                    metric.add_pass()

        self.metrics["annotations"] = metric
        return metric.to_dict()

    async def _validate_search_history(self) -> Dict[str, Any]:
        logger.info("Validating search history...")
        metric = DataQualityMetric("搜索历史数据质量", "验证搜索历史数据的完整性和有效性")

        async with self.pool.acquire() as conn:
            for field in ["user_id", "query", "search_type"]:
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM search_history WHERE {field} IS NULL")
                if row["cnt"] > 0:
                    metric.add_fail(f"搜索历史{field}字段为空: {row['cnt']}个")
                else:
                    metric.add_pass()

            row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM search_history WHERE LENGTH(query) = 0")
            if row["cnt"] > 0:
                metric.add_fail(f"空查询: {row['cnt']}个")
            else:
                metric.add_pass()

            row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM search_history WHERE response_time_ms < 0")
            if row["cnt"] > 0:
                metric.add_fail(f"无效响应时间: {row['cnt']}个")
            else:
                metric.add_pass()

            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM search_history WHERE user_id NOT IN (SELECT id FROM users)"
            )
            if row["cnt"] > 0:
                metric.add_fail(f"孤立搜索历史: {row['cnt']}个")
            else:
                metric.add_pass()

        self.metrics["search_history"] = metric
        return metric.to_dict()

    async def _validate_processing_jobs(self) -> Dict[str, Any]:
        logger.info("Validating processing jobs...")
        metric = DataQualityMetric("处理任务数据质量", "验证处理任务数据的完整性和有效性")

        async with self.pool.acquire() as conn:
            for field in ["document_id", "file_path", "status"]:
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM processing_jobs WHERE {field} IS NULL")
                if row["cnt"] > 0:
                    metric.add_fail(f"处理任务{field}字段为空: {row['cnt']}个")
                else:
                    metric.add_pass()

        self.metrics["processing_jobs"] = metric
        return metric.to_dict()

    async def _validate_consistency(self) -> Dict[str, Any]:
        logger.info("Validating data consistency...")
        metric = DataQualityMetric("数据一致性", "验证跨表数据的一致性")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM documents WHERE uploader_id NOT IN (SELECT id FROM users)"
            )
            if row["cnt"] > 0:
                metric.add_fail(f"孤立文档（无有效上传者）: {row['cnt']}个")
            else:
                metric.add_pass()

            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM document_chunks WHERE document_id NOT IN (SELECT id FROM documents)"
            )
            if row["cnt"] > 0:
                metric.add_fail(f"孤立文档块（无有效文档）: {row['cnt']}个")
            else:
                metric.add_pass()

            row = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM search_history WHERE user_id NOT IN (SELECT id FROM users)"
            )
            if row["cnt"] > 0:
                metric.add_fail(f"孤立搜索历史（无有效用户）: {row['cnt']}个")
            else:
                metric.add_pass()

        self.metrics["consistency"] = metric
        return metric.to_dict()

    def _calculate_overall_score(self, results: Dict[str, Any]) -> float:
        total_score = 0.0
        count = 0
        for table_name, table_result in results.items():
            if table_name != "overall_score":
                total_score += table_result.get("score", 0)
                count += 1
        return total_score / count if count > 0 else 0.0

    async def export_report(self, results: Dict[str, Any], output_dir: Path):
        logger.info("Exporting validation report...")
        output_dir.mkdir(parents=True, exist_ok=True)

        report_file = output_dir / f"data_validation_report_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"Validation report exported to {report_file}")

        summary_file = output_dir / "validation_summary.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("=" * 50 + "\n")
            f.write("数据质量验证摘要\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"总体得分: {results['overall_score']:.2f}%\n\n")
            for table_name, table_result in results.items():
                if table_name != "overall_score":
                    f.write(f"\n{table_result['name']}\n")
                    f.write("-" * 50 + "\n")
                    f.write(f"得分: {table_result['score']:.2f}%\n")
                    f.write(f"通过: {table_result['pass_count']}\n")
                    f.write(f"失败: {table_result['fail_count']}\n")
                    f.write(f"总数: {table_result['total_count']}\n")
                    f.write(f"问题: {table_result['total_issues']}\n")

        logger.info(f"Summary exported to {summary_file}")


async def main():
    logger.info("=" * 50)
    logger.info("Starting Data Validation (asyncpg)")
    logger.info("=" * 50)

    pool = get_db_pool()
    try:
        validator = DataValidator(pool)
        results = await validator.validate_all()
        await validator.export_report(results, OUTPUT_DIR)
        logger.info("Data Validation Complete")
    except Exception as e:
        logger.error(f"Error validating data: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
