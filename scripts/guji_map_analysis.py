#!/usr/bin/env python3
"""
古籍映射分析脚本 - 纯分析模式

功能:
1. 扫描 openlist 中的古籍扫描文档
2. 分析文件名模式
3. 生成映射报告
"""

import asyncio
import aiohttp
import re
import sys
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from collections import defaultdict

# Openlist API
OPENLIST_BASE = "http://100.66.1.8:2455"
API_DELAY = 0.2

# 扫描路径
SCAN_PATHS = [
    "/书籍/丛刊/殆知閣古代文獻2.0（旧版）",
    "/书籍/智能气功专业图书馆/2、古籍参考文献",
    "/书籍/丛刊/四部丛刊",
]

# 本地数据库
SQLITE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"


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
    max_depth: int = 5,
    depth: int = 0,
    stats: dict = None
) -> List[dict]:
    """递归扫描文件"""
    if stats is None:
        stats = {'dirs': 0, 'files': 0, 'errors': 0}

    if depth >= max_depth:
        return []

    try:
        result = await fetch_directory(session, base_path)
    except Exception as e:
        stats['errors'] += 1
        return []

    if not result:
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
            stats['dirs'] += 1
            sub_files = await scan_files_recursive(
                session, path, max_depth, depth + 1, stats
            )
            files.extend(sub_files)
        else:
            stats['files'] += 1
            ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
            files.append({
                'name': name,
                'path': path,
                'ext': ext,
                'size': item.get('size', 0)
            })

        if stats['files'] % 500 == 0 and depth == 0:
            print(f"    已扫描 {stats['files']} 个文件...")

    return files


def analyze_local_db() -> dict:
    """分析本地数据库结构"""
    import sqlite3

    print("📖 分析本地数据库...")

    if not SQLITE_DB.exists():
        print(f"  ⚠️  数据库不存在: {SQLITE_DB}")
        return {}

    conn = sqlite3.connect(str(SQLITE_DB))
    cursor = conn.cursor()

    # 获取所有 wx 表
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wx%'"
    )
    tables = [row[0] for row in cursor.fetchall()]

    # 分析每个表
    table_info = {}
    for table in tables[:50]:  # 限制处理数量
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]

            cursor.execute(f"PRAGMA table_info({table})")
            cols = [col[1] for col in cursor.fetchall()]

            # 获取 bid 范围
            if 'bid' in cols:
                cursor.execute(f"SELECT MIN(bid), MAX(bid) FROM {table}")
                min_bid, max_bid = cursor.fetchone()
            else:
                min_bid = max_bid = None

            # 检查是否有 title 列
            has_title = 'title' in cols
            sample_titles = []
            if has_title:
                cursor.execute(f"SELECT title FROM {table} WHERE title IS NOT NULL LIMIT 5")
                sample_titles = [row[0] for row in cursor.fetchall() if row[0]]

            table_num = re.search(r'\d+', table)
            if table_num:
                num = int(table_num.group())
                table_info[num] = {
                    'table': table,
                    'count': count,
                    'has_bid': 'bid' in cols,
                    'min_bid': min_bid,
                    'max_bid': max_bid,
                    'has_title': has_title,
                    'sample_titles': sample_titles
                }
        except Exception:
            continue

    conn.close()

    print(f"  分析了 {len(table_info)} 个 wx 表")
    return table_info


def analyze_filename_patterns(files: List[dict]) -> dict:
    """分析文件名模式"""
    patterns = defaultdict(int)
    ext_stats = defaultdict(int)
    sample_files = defaultdict(list)

    for f in files:
        name = f['name']
        ext = f['ext']
        ext_stats[ext] += 1

        # 去除扩展名
        base_name = name.rsplit('.', 1)[0] if '.' in name else name

        # 分类
        if re.match(r'^\d+', base_name):
            pattern = '数字开头'
            match = re.match(r'^(\d+)', base_name)
            if match:
                num = match.group(1)
                sample_files[f'bid_{num}'].append(f)
        elif re.match(r'^wx\d+', base_name, re.IGNORECASE):
            pattern = 'wx前缀'
            match = re.search(r'wx(\d+)', base_name, re.IGNORECASE)
            if match:
                num = match.group(1)
                sample_files[f'wx_{num}'].append(f)
        elif re.match(r'^[a-zA-Z]', base_name):
            pattern = '字母开头'
        elif re.match(r'^[一-龥]', base_name):
            pattern = '中文开头'
            # 提取可能的书籍名
            sample_files[f'中文_{base_name[:5]}'].append(f)
        else:
            pattern = '其他'

        patterns[pattern] += 1

    return {
        'patterns': dict(patterns),
        'extensions': dict(ext_stats),
        'samples': dict(sample_files)
    }


async def main():
    """主函数"""
    print("=" * 70)
    print("📚 古籍映射分析")
    print("=" * 70)
    print(f"时间: {datetime.now()}")
    print()

    # 1. 分析本地数据库
    db_info = analyze_local_db()
    print()

    # 2. 扫描 openlist 文件
    print("📁 扫描 openlist 文件...")
    async with aiohttp.ClientSession() as session:
        all_files = []
        total_stats = {'dirs': 0, 'files': 0, 'errors': 0}

        for base_path in SCAN_PATHS:
            print(f"  扫描: {base_path}")
            files = await scan_files_recursive(
                session, base_path, max_depth=6, stats=total_stats
            )
            print(f"    找到 {len(files)} 个文件")
            all_files.extend(files)

        print(f"\n  扫描统计:")
        print(f"    总目录: {total_stats['dirs']}")
        print(f"    总文件: {total_stats['files']}")
        print(f"    错误: {total_stats['errors']}")

    print()

    # 3. 分析文件模式
    print("🔬 分析文件名模式...")
    analysis = analyze_filename_patterns(all_files)

    print("\n  按模式分类:")
    for pattern, count in sorted(analysis['patterns'].items(), key=lambda x: -x[1]):
        print(f"    {pattern}: {count:,}")

    print("\n  按扩展名分类 (前10):")
    for ext, count in sorted(analysis['extensions'].items(), key=lambda x: -x[1])[:10]:
        print(f"    .{ext or '(无)'}: {count:,}")

    # 4. 分析潜在匹配
    print("\n🔗 潜在匹配分析:")

    # 统计数字开头的文件
    numeric_files = {}
    for key, files in analysis['samples'].items():
        if key.startswith('bid_'):
            bid = key[4:]
            numeric_files[bid] = files

    print(f"  数字开头的文件: {len(numeric_files)} 组")
    if numeric_files:
        print("\n  示例 (数字开头的文件):")
        for bid, files in sorted(numeric_files.items(), key=lambda x: x[0])[:10]:
            print(f"    bid={bid}: {len(files)} 个文件")
            for f in files[:2]:
                print(f"      - {f['name']}")

    # 统计 wx 前缀的文件
    wx_files = {}
    for key, files in analysis['samples'].items():
        if key.startswith('wx_'):
            wx_num = key[3:]
            wx_files[wx_num] = files

    print(f"\n  wx 前缀的文件: {len(wx_files)} 组")
    if wx_files:
        print("\n  示例 (wx 前缀的文件):")
        for wx_num, files in sorted(wx_files.items(), key=lambda x: x[0])[:10]:
            print(f"    wx{wx_num}: {len(files)} 个文件")
            for f in files[:2]:
                print(f"      - {f['name']}")

    # 5. 数据库与文件对比
    print("\n📊 数据库与文件对比:")

    if db_info:
        print("\n  数据库表范围 vs 文件中的 bid:")

        for num in sorted(db_info.keys())[:15]:
            info = db_info[num]
            bid_str = f"{info['min_bid']}-{info['max_bid']}" if info['min_bid'] else "N/A"

            # 查找匹配的文件
            matching_files = 0
            if numeric_files:
                for bid_str_key, files in numeric_files.items():
                    bid_int = int(bid_str_key)
                    if info['min_bid'] and info['max_bid']:
                        if info['min_bid'] <= bid_int <= info['max_bid']:
                            matching_files += len(files)

            print(f"    wx{num:>6}: {info['count']:>6} 条记录, bid范围 {bid_str:>15}, 匹配文件 {matching_files}")

    # 6. 输出报告
    print("\n" + "=" * 70)
    print("📋 映射建议:")
    print("=" * 70)

    if numeric_files:
        print("\n✅ 可以通过文件名数字前缀直接映射:")
        print(f"   共 {len(numeric_files)} 组文件可映射到数据库")

    if wx_files:
        print("\n✅ 可以通过 wx 前缀直接映射:")
        print(f"   共 {len(wx_files)} 组文件可映射到对应 wx 表")

    remaining = len(all_files) - len(numeric_files) - sum(len(f) for f in wx_files.values())
    if remaining > 0:
        print(f"\n⚠️  还有 {remaining} 个中文文件名需要模糊匹配:")
        print("   建议: 使用文本相似度算法匹配数据库中的标题")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
