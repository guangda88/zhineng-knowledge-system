#!/usr/bin/env python3
"""
古籍快速映射脚本 - 使用本地数据库建立映射

原理:
1. 从本地 guoxue.db 读取 wx* 表的 bid 和内容
2. 使用 bid 作为关键索引
3. 从 openlist API 扫描扫描文档
4. 通过文件名匹配建立映射
"""

import asyncio
import aiohttp
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import re

# Openlist API
OPENLIST_BASE = "http://100.66.1.8:2455"
API_DELAY = 0.3

# 本地数据库
SQLITE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"

# 扫描路径
SCAN_PATHS = [
    "/书籍/丛刊/殆知閣古代文獻2.0（旧版）",
    "/书籍/智能气功专业图书馆/2、古籍参考文献",
]


async def fetch_directory(session: aiohttp.ClientSession, path: str, page: int = 1) -> dict:
    """获取目录内容"""
    await asyncio.sleep(API_DELAY)

    payload = {
        "path": path,
        "password": "",
        "page": page,
        "per_page": 200,
        "refresh": False
    }

    async with session.post(f"{OPENLIST_BASE}/api/fs/list", json=payload) as resp:
        data = await resp.json()
        if data.get('code') == 200:
            return data.get('data', {})
        return {}


async def scan_files_recursive(
    session: aiohttp.ClientSession,
    base_path: str,
    max_depth: int = 4,
    depth: int = 0
) -> List[dict]:
    """递归扫描文件"""
    if depth >= max_depth:
        return []

    try:
        result = await fetch_directory(session, base_path)
        if not result:
            return []
    except Exception as e:
        print(f"    ⚠️  无法访问 {base_path}: {e}")
        return []

    items = result.get('content')
    if not items:
        return []

    files = []

    for item in items:
        name = item.get('name', '')
        is_dir = item.get('is_dir', False)
        path = item.get('path', f"{base_path}/{name}")

        if is_dir:
            sub_files = await scan_files_recursive(session, path, max_depth, depth + 1)
            files.extend(sub_files)
        else:
            ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
            files.append({
                'name': name,
                'path': path,
                'ext': ext
            })

    return files


def extract_book_id_from_filename(filename: str) -> Tuple[Optional[int], str]:
    """从文件名提取 book_id"""
    # 尝试匹配数字前缀
    match = re.match(r'^(\d+)', filename)
    if match:
        return int(match.group(1)), filename

    # 尝试匹配 wx 模式
    match = re.search(r'wx(\d+)', filename, re.IGNORECASE)
    if match:
        return int(match.group(1)), filename

    # 尝试匹配 bid 模式
    match = re.search(r'bid[:\s]*(\d+)', filename, re.IGNORECASE)
    if match:
        return int(match.group(1)), filename

    return None, filename


async def main():
    """主函数"""
    print("=" * 60)
    print("📚 古籍快速映射")
    print("=" * 60)
    print(f"时间: {datetime.now()}")
    print()

    # 1. 从本地数据库读取 bid 信息
    print("📖 读取本地数据库...")
    if not SQLITE_DB.exists():
        print(f"  ❌ 数据库不存在: {SQLITE_DB}")
        return

    conn = sqlite3.connect(str(SQLITE_DB))
    cursor = conn.cursor()

    # 获取所有 wx 表
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wx%'"
    )
    tables = [row[0] for row in cursor.fetchall()]
    print(f"  找到 {len(tables)} 个 wx 表")

    # 读取每个表的 bid 范围
    bid_info = {}
    for table in tables[:30]:  # 限制数量
        try:
            cursor.execute(f"SELECT MIN(bid), MAX(bid), COUNT(DISTINCT bid) FROM {table}")
            min_bid, max_bid, count = cursor.fetchone()
            if min_bid and max_bid:
                # 提取数字部分
                table_num = re.search(r'\d+', table)
                if table_num:
                    num = int(table_num.group())
                    bid_info[num] = {
                        'table': table,
                        'min_bid': min_bid,
                        'max_bid': max_bid,
                        'count': count
                    }
        except Exception:
            continue

    conn.close()

    print(f"  读取到 {len(bid_info)} 个表的信息")
    print()

    # 2. 扫描 openlist 文件
    print("📁 扫描 openlist 文件...")
    async with aiohttp.ClientSession() as session:
        all_files = []

        for base_path in SCAN_PATHS:
            print(f"  扫描: {base_path}")
            files = await scan_files_recursive(session, base_path, max_depth=5)
            print(f"    找到 {len(files)} 个文件")
            all_files.extend(files)

    print(f"  总计: {len(all_files)} 个文件")
    print()

    # 3. 分析文件名模式
    print("🔬 分析文件名...")
    name_patterns = {}
    for f in all_files:
        name = f['name']
        # 去除扩展名
        base_name = name.rsplit('.', 1)[0] if '.' in name else name

        # 分类
        if re.match(r'^\d+', base_name):
            pattern = '数字开头'
        elif re.match(r'^[a-zA-Z]', base_name):
            pattern = '字母开头'
        elif re.match(r'^[一-龥]', base_name):
            pattern = '中文开头'
        else:
            pattern = '其他'

        name_patterns[pattern] = name_patterns.get(pattern, 0) + 1

    for pattern, count in name_patterns.items():
        print(f"  {pattern}: {count}")

    # 4. 尝试建立映射
    print("\n🔗 尝试建立映射...")

    # 连接 PostgreSQL
    import asyncpg
    pg_conn = await asyncpg.connect(
        'postgresql://zhineng:zhineng123@localhost:5436/zhineng_kb'
    )

    # 清空旧映射
    await pg_conn.execute("TRUNCATE TABLE guji_scan_mapping")

    mapped = 0
    for f in all_files:
        book_id, name = extract_book_id_from_filename(f['name'])

        if book_id:
            # 查找对应的 source_table
            source_table = None
            for num, info in bid_info.items():
                if info['min_bid'] <= book_id <= info['max_bid']:
                    source_table = f"wx{num}"
                    break

            if source_table:
                await pg_conn.execute("""
                    INSERT INTO guji_scan_mapping
                    (file_name, file_path, file_type, book_id, source_table)
                    VALUES ($1, $2, $3, $4, $5)
                """, f['name'], f['path'], f['ext'], book_id, source_table)

                mapped += 1
                if mapped % 50 == 0:
                    print(f"  已映射 {mapped} 个文件...")

    await pg_conn.close()

    print(f"  ✅ 完成: {mapped} 个文件已映射")
    print()

    # 5. 显示统计
    print("📊 映射统计:")
    print(f"  扫描文件数: {len(all_files)}")
    print(f"  成功映射数: {mapped}")
    print(f"  映射率: {mapped/len(all_files)*100:.1f}%")

    print("\n" + "=" * 60)
    print("✅ 完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
