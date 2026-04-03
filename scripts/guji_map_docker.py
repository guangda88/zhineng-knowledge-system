#!/usr/bin/env python3
"""
古籍映射脚本 - 使用 Docker 执行 SQL

通过 Docker exec 执行数据库操作，避免直接连接问题
"""

import asyncio
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import aiohttp

# Openlist API
OPENLIST_BASE = "http://100.66.1.8:2455"
API_DELAY = 0.2

# 扫描路径
SCAN_PATHS = [
    "/书籍/丛刊/殆知閣古代文獻2.0（旧版）",
    "/书籍/智能气功专业图书馆/2、古籍参考文献",
    "/书籍/丛刊/四部丛刊",
]

# Docker 配置
POSTGRES_CONTAINER = "dfdd3b278296_zhineng-postgres"


async def fetch_directory(session: aiohttp.ClientSession, path: str, page: int = 1) -> dict:
    """获取目录内容"""
    await asyncio.sleep(API_DELAY)

    payload = {"path": path, "password": "", "page": page, "per_page": 200, "refresh": False}

    async with session.post(f"{OPENLIST_BASE}/api/fs/list", json=payload) as resp:
        data = await resp.json()
        if data.get("code") == 200:
            return data.get("data", {})
        return {}


async def scan_files_recursive(
    session: aiohttp.ClientSession, base_path: str, max_depth: int = 6, depth: int = 0
) -> List[dict]:
    """递归扫描文件"""
    if depth >= max_depth:
        return []

    try:
        result = await fetch_directory(session, base_path)
    except Exception:
        return []

    if not result:
        return []

    items = result.get("content")
    if not items:
        return []

    files = []

    for item in items:
        name = item.get("name", "")
        is_dir = item.get("is_dir", False)
        path = item.get("path", f"{base_path}/{name}")

        if is_dir:
            sub_files = await scan_files_recursive(session, path, max_depth, depth + 1)
            files.extend(sub_files)
        else:
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            files.append({"name": name, "path": path, "ext": ext})

    return files


def exec_sql(sql: str) -> bool:
    """通过 Docker 执行 SQL"""
    cmd = [
        "docker",
        "exec",
        POSTGRES_CONTAINER,
        "psql",
        "-U",
        "zhineng",
        "-d",
        "zhineng_kb",
        "-c",
        sql,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception:
        return False


async def main():
    """主函数"""
    print("=" * 70)
    print("📚 古籍扫描文档映射 (Docker 模式)")
    print("=" * 70)
    print(f"时间: {datetime.now()}")
    print()

    # 1. 读取本地数据库的 bid 信息
    print("📖 读取本地数据库...")
    sqlite_db = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"

    if not sqlite_db.exists():
        print(f"  ❌ 数据库不存在: {sqlite_db}")
        return

    conn = sqlite3.connect(str(sqlite_db))
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wx%'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"  找到 {len(tables)} 个 wx 表")

    # 读取 bid 范围
    bid_ranges = {}
    for table in tables[:50]:
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [col[1] for col in cursor.fetchall()]

            if "bid" not in cols:
                continue

            cursor.execute(f"SELECT MIN(bid), MAX(bid) FROM {table}")
            min_bid, max_bid = cursor.fetchone()

            if min_bid and max_bid:
                table_num = re.search(r"\d+", table)
                if table_num:
                    num = int(table_num.group())
                    bid_ranges[num] = (min_bid, max_bid, table)
        except Exception:
            continue

    conn.close()

    print(f"  读取到 {len(bid_ranges)} 个表的 bid 范围")
    print()

    # 2. 扫描 openlist 文件
    print("📁 扫描 openlist 文件...")
    async with aiohttp.ClientSession() as session:
        all_files = []

        for base_path in SCAN_PATHS:
            print(f"  扫描: {base_path}")
            files = await scan_files_recursive(session, base_path)
            print(f"    找到 {len(files)} 个文件")
            all_files.extend(files)

    print(f"  总计: {len(all_files)} 个文件")
    print()

    # 3. 分析文件并分类
    print("🔬 分析文件...")

    numeric_files = []  # 数字开头
    chinese_files = []  # 中文开头

    for f in all_files:
        name = f["name"]

        # 去除扩展名
        base_name = name.rsplit(".", 1)[0] if "." in name else name

        # 检查数字开头
        match = re.match(r"^0*(\d+)", base_name)
        if match:
            bid = int(match.group(1))
            numeric_files.append((bid, f))
        else:
            chinese_files.append(f)

    print(f"  数字开头: {len(numeric_files)} 个")
    print(f"  中文开头: {len(chinese_files)} 个")
    print()

    # 4. 建立映射
    print("🔗 建立映射...")

    # 清空旧映射
    print("  清空旧映射...")
    exec_sql("TRUNCATE TABLE guji_scan_mapping")

    # 映射数字开头的文件
    print("  映射数字开头的文件...")
    mapped = 0
    batch_sql = []

    for bid, f in numeric_files:
        # 查找匹配的表
        source_table = None
        for num, (min_b, max_b, table) in bid_ranges.items():
            if min_b <= bid <= max_b:
                source_table = f"wx{num}"
                break

        if source_table:
            # 转义单引号
            safe_name = f["name"].replace("'", "''")
            safe_path = f["path"].replace("'", "''")

            batch_sql.append(
                f"('{safe_name}', '{safe_path}', '{f['ext']}', {bid}, '{source_table}')"
            )

            if len(batch_sql) >= 100:
                sql = f"""
                    INSERT INTO guji_scan_mapping
                    (file_name, file_path, file_type, book_id, source_table)
                    VALUES {', '.join(batch_sql)}
                """
                if exec_sql(sql):
                    mapped += len(batch_sql)
                    if mapped % 500 == 0:
                        print(f"    已映射 {mapped} 个文件...")
                batch_sql = []

    # 插入剩余的
    if batch_sql:
        sql = f"""
            INSERT INTO guji_scan_mapping
            (file_name, file_path, file_type, book_id, source_table)
            VALUES {', '.join(batch_sql)}
        """
        if exec_sql(sql):
            mapped += len(batch_sql)

    print(f"  ✅ 数字文件映射完成: {mapped} 个")
    print()

    # 5. 显示统计
    print("📊 映射统计:")

    # 获取统计信息
    result = subprocess.run(
        [
            "docker",
            "exec",
            POSTGRES_CONTAINER,
            "psql",
            "-U",
            "zhineng",
            "-d",
            "zhineng_kb",
            "-t",
            "-c",
            "SELECT COUNT(*) FROM guji_scan_mapping",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        total = result.stdout.strip()
        print(f"  数据库记录数: {total}")

    result = subprocess.run(
        [
            "docker",
            "exec",
            POSTGRES_CONTAINER,
            "psql",
            "-U",
            "zhineng",
            "-d",
            "zhineng_kb",
            "-c",
            "SELECT source_table, COUNT(*) as cnt FROM guji_scan_mapping GROUP BY source_table ORDER BY cnt DESC LIMIT 10",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("\n  按来源表统计:")
        for line in result.stdout.strip().split("\n"):
            if line and not line.startswith("-") and "source_table" not in line:
                print(f"    {line}")

    # 示例映射
    result = subprocess.run(
        [
            "docker",
            "exec",
            POSTGRES_CONTAINER,
            "psql",
            "-U",
            "zhineng",
            "-d",
            "zhineng_kb",
            "-c",
            "SELECT file_name, book_id, source_table FROM guji_scan_mapping LIMIT 10",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("\n  映射示例:")
        for line in result.stdout.strip().split("\n"):
            if line and not line.startswith("-") and "file_name" not in line:
                print(f"    {line}")

    print()
    print("=" * 70)
    print("✅ 映射完成")
    print(f"  扫描文件: {len(all_files)}")
    print(f"  成功映射: {mapped}")
    print(f"  中文文件待处理: {len(chinese_files)}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
