#!/usr/bin/env python3
"""
建立 guoxue_content 与古籍扫描文档的映射关系

用法:
    python scripts/establish_guji_mapping.py
    或
    python scripts/establish_guji_mapping.py --sync
"""

import asyncio
import asyncpg
import sys
import time
from pathlib import Path

# API 配置
OPENLIST_BASE = "http://100.66.1.8:2455"
API_DELAY = 1  # 请求间隔1秒（遵守速率限制）

async def fetch_directory(api_client, path: str):
    """获取目录内容"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        payload = {
            "path": path,
            "password": "",
            "page": 1,
            "per_page": 100,
            "refresh": False
        }
        async with session.post(f"{OPENLIST_BASE}/api/fs/list",
                                 json=payload) as resp:
            data = await resp.json()
            if data.get('code') == 200:
                return data.get('data', {})
            return None


async def scan_guji_directory(base_path: str = "/书籍"):
    """扫描 guji 相关目录"""
    import aiohttp

    print(f"🔍 扫描 {base_path}...")

    # 目录名关键词
    keywords = ['国学', 'guji', '古籍', '经典']
    guji_dirs = []

    async with aiohttp.ClientSession() as session:
        # 先获取顶层目录
        payload = {"path": base_path, "password": "", "page": 1, "per_page": 100, "refresh": False}
        async with session.post(f"{OPENLIST_BASE}/api/fs/list", json=payload) as resp:
            data = await resp.json()
            if data.get('code') == 200:
                content = data.get('data', {}).get('content', [])
                for item in content:
                    if item.get('is_dir'):
                        name = item.get('name', '')
                        if any(kw in name.lower() for kw in keywords):
                            full_path = f"{base_path}/{name}"
                            print(f"  找到: {full_path}")
                            guji_dirs.append(full_path)

    return guji_dirs


async def collect_scan_files(directory: str):
    """收集扫描文档文件"""
    import aiohttp

    files = []
    page = 1

    async with aiohttp.ClientSession() as session:
        while True:
            print(f"  扫描第 {page} 页...")
            await asyncio.sleep(API_DELAY)

            payload = {
                "path": directory,
                "password": "",
                "page": page,
                "per_page": 100,
                "refresh": False
            }

            async with session.post(f"{OPENLIST_BASE}/api/fs/list", json=payload) as resp:
                data = await resp.json()

                if data.get('code') != 200:
                    print(f"    ❌ 错误: {data.get('message')}")
                    break

                content = data.get('data', {}).get('content', [])
                for item in content:
                    if not item.get('is_dir'):
                        name = item.get('name', '')
                        size = item.get('size', 0)
                        files.append({
                            'name': name,
                            'path': item.get('path', ''),
                            'size': size,
                            'type': name.split('.')[-1].lower() if '.' in name else ''
                        })

                total = data.get('data', {}).get('total', 0)
                if len(files) >= total:
                    break

                page += 1

    return files


async def parse_book_id_from_filename(filename: str):
    """从文件名解析 book_id"""
    import re

    # 尝试匹配数字前缀 (如 10001_卷一~卷二.pdf)
    match = re.match(r'^(\d+)', filename)
    if match:
        book_id = int(match.group(1))
        return book_id

    # 尝试匹配 wx 模式
    match = re.search(r'wx(\d+)', filename, re.IGNORECASE)
    if match:
        book_id = int(match.group(1))
        return book_id

    return None


async def establish_mapping():
    """建立映射关系"""

    print("=" * 60)
    print("📚 建立 guoxue_content 与古籍扫描文档的映射")
    print("=" * 60)

    # 1. 扫描 guji 目录
    print("\n🔍 第1步: 扫描目录...")
    guji_dirs = await scan_guji_directory()

    if not guji_dirs:
        print("  ⚠️  未找到 guji 相关目录，尝试扫描其他目录...")
        guji_dirs = await scan_guji_directory("/")

    # 2. 收集扫描文档
    print(f"\n📄 第2步: 收集扫描文档...")
    all_files = []

    for directory in guji_dirs[:3]:  # 限制扫描目录数
        print(f"  扫描: {directory}")
        files = await collect_scan_files(directory)
        all_files.extend(files)
        print(f"    找到 {len(files)} 个文件")

    print(f"\n  总计: {len(all_files)} 个扫描文档")

    # 3. 分析文件名模式
    print(f"\n🔬 第3步: 分析文件名模式...")

    book_id_files = {}
    for f in all_files:
        book_id = await parse_book_id_from_filename(f['name'])
        if book_id:
            if book_id not in book_id_files:
                book_id_files[book_id] = []
            book_id_files[book_id].append(f)

    print(f"  可关联的 book_id: {len(book_id_files)}")

    # 4. 连接数据库并写入映射
    print(f"\n💾 第4步: 写入映射表...")

    conn = await asyncpg.connect('postgresql://zhineng:zhineng123@localhost:5436/zhineng_kb')

    # 清空旧数据
    await conn.execute("TRUNCATE TABLE guji_scan_mapping")

    # 插入新映射
    inserted = 0
    for book_id, files in list(book_id_files.items())[:50]:  # 限制处理数量
        for f in files:
            await conn.execute("""
                INSERT INTO guji_scan_mapping
                (file_name, file_path, file_type, book_id)
                VALUES ($1, $2, $3, $4)
            """, f['name'], f['path'], f['type'], book_id)
            inserted += 1

    await conn.close()

    print(f"  ✅ 已写入 {inserted} 条映射记录")

    print(f"\n" + "=" * 60)
    print("✅ 映射建立完成")
    print("=" * 60)


async def show_current_status():
    """显示当前映射状态"""
    conn = await asyncpg.connect('postgresql://zhineng:zhineng123@localhost:5436/zhineng_kb')

    total = await conn.fetchval("SELECT COUNT(*) FROM guji_scan_mapping")

    print(f"\n📊 当前映射状态:")
    print(f"  总记录数: {total}")

    if total > 0:
        rows = await conn.fetch("""
            SELECT book_id, source_table, COUNT(*) as file_count
            FROM guji_scan_mapping g
            LEFT JOIN guoxue_content c ON g.book_id = c.book_id
            GROUP BY book_id, source_table
            ORDER BY book_id
            LIMIT 20
        """)

        print(f"\n  book_id | source_table | 文件数")
        print(f"  ---------+-------------+--------")
        for row in rows:
            source = row['source_table'] or 'N/A'
            print(f"  {row['book_id']:8} | {source:12} | {row['file_count']}")

    await conn.close()


async def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--status':
        await show_current_status()
    else:
        await establish_mapping()


if __name__ == '__main__':
    asyncio.run(main())
