#!/usr/bin/env python3
"""
古籍扫描文档映射脚本
建立 guoxue_content 数据与 openlist 扫描文档的映射关系

功能:
1. 扫描 openlist 中的古籍目录
2. 分析数据库中的书籍标题
3. 建立 book_id/bid 与扫描文档路径的映射
"""

import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
import asyncpg

# Openlist API 配置
OPENLIST_BASE = "http://100.66.1.8:2455"
API_DELAY = 0.5  # 请求间隔

# 古籍目录路径
GUJI_PATHS = [
    "/书籍/丛刊/殆知閣古代文獻2.0（旧版）",
    "/书籍/智能气功专业图书馆/2、古籍参考文献",
    "/书籍/丛刊",
]


class GujiMapper:
    """古籍映射器"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.conn: Optional[asyncpg.Connection] = None
        self.file_index: Dict[str, List[Dict]] = {}
        self.title_index: Dict[str, str] = {}

    async def init(self):
        """初始化连接"""
        self.session = aiohttp.ClientSession()
        self.conn = await asyncpg.connect(
            "postgresql://zhineng:zhineng123@localhost:5436/zhineng_kb"
        )

    async def close(self):
        """关闭连接"""
        if self.session:
            await self.session.close()
        if self.conn:
            await self.conn.close()

    async def list_directory(self, path: str, page: int = 1, per_page: int = 200) -> Optional[Dict]:
        """列出目录内容"""
        await asyncio.sleep(API_DELAY)

        payload = {
            "path": path,
            "password": "",
            "page": page,
            "per_page": per_page,
            "refresh": False,
        }

        try:
            async with self.session.post(f"{OPENLIST_BASE}/api/fs/list", json=payload) as resp:
                data = await resp.json()
                if data.get("code") == 200:
                    return data.get("data", {})
                return None
        except Exception as e:
            print(f"  API 请求失败: {e}")
            return None

    async def scan_directory_recursive(
        self, base_path: str, max_depth: int = 5, current_depth: int = 0
    ) -> List[Dict]:
        """递归扫描目录"""
        if current_depth >= max_depth:
            return []

        print(f"  [{'  ' * current_depth}] 扫描: {base_path}")

        result = await self.list_directory(base_path)
        if not result:
            return []

        items = result.get("content", [])
        files = []

        for item in items:
            name = item.get("name", "")
            is_dir = item.get("is_dir", False)
            path = item.get(
                "path", f"{base_path}/{name}" if base_path == "/" else f"{base_path}/{name}"
            )

            if is_dir:
                # 递归扫描子目录
                sub_files = await self.scan_directory_recursive(path, max_depth, current_depth + 1)
                files.extend(sub_files)
            else:
                # 记录文件
                ext = name.split(".")[-1].lower() if "." in name else ""
                files.append({"name": name, "path": path, "ext": ext, "size": item.get("size", 0)})

        return files

    async def build_file_index(self):
        """建立文件索引"""
        print("📁 建立文件索引...")

        for base_path in GUJI_PATHS:
            print(f"\n扫描: {base_path}")
            files = await self.scan_directory_recursive(base_path, max_depth=6)

            print(f"  找到 {len(files)} 个文件")

            for f in files:
                # 提取文件名（不含扩展名）
                name_key = f["name"].rsplit(".", 1)[0] if "." in f["name"] else f["name"]
                self.file_index[name_key] = f

        print(f"\n✅ 文件索引建立完成: {len(self.file_index)} 个文件")

    async def build_title_index(self):
        """建立数据库标题索引"""
        print("\n📚 建立数据库标题索引...")

        # 从 guoxue_content 获取标题
        # 由于 body 内容可能包含标题，我们需要提取
        rows = await self.conn.fetch(
            """
            SELECT DISTINCT source_table, book_id
            FROM guoxue_content
            WHERE source_table LIKE 'wx%'
            LIMIT 50000
        """
        )

        print(f"  从数据库读取 {len(rows)} 条记录...")

        # 从本地 SQLite 获取实际标题
        import sqlite3

        sqlite_db = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"

        if sqlite_db.exists():
            conn = sqlite3.connect(str(sqlite_db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 获取所有 wx 表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wx%'")
            tables = [row[0] for row in cursor.fetchall()]

            print(f"  本地数据库有 {len(tables)} 个 wx 表")

            for table in tables[:50]:  # 限制处理数量
                try:
                    cursor.execute(f"PRAGMA table_info({table})")
                    cols = [col[1] for col in cursor.fetchall()]

                    # 检查是否有 title 列
                    if "title" in cols:
                        cursor.execute(
                            f"SELECT id, title FROM {table} WHERE title IS NOT NULL LIMIT 1000"
                        )
                        for row in cursor.fetchall():
                            title = row[1]
                            if title:
                                # 创建索引键
                                key = self.normalize_title(title)
                                self.title_index[key] = f"{table}:{row[0]}"
                except Exception as e:
                    continue

            conn.close()
            print(f"  ✅ 标题索引建立完成: {len(self.title_index)} 个标题")
        else:
            print(f"  ⚠️  本地数据库不存在: {sqlite_db}")

    def normalize_title(self, title: str) -> str:
        """标准化标题用于匹配"""
        # 移除常见前缀后缀
        title = re.sub(r"^[\d\s、.]+", "", title)
        title = re.sub(r"[\s\s]+$", "", title)
        # 移除括号内容
        title = re.sub(r"[（(].*?[）)]", "", title)
        return title.strip()

    async def establish_mapping(self):
        """建立映射关系"""
        print("\n🔗 建立映射关系...")

        # 清空旧映射
        await self.conn.execute("TRUNCATE TABLE guji_scan_mapping")

        # 尝试匹配
        matched = 0
        for file_key, file_info in self.file_index.items():
            normalized = self.normalize_title(file_key)

            # 在标题索引中查找
            if normalized in self.title_index:
                ref = self.title_index[normalized]
                parts = ref.split(":")

                # 尝试提取 book_id
                source_table = parts[0].replace("wx", "")
                try:
                    book_id = int(parts[1]) if len(parts) > 1 else None

                    if book_id:
                        await self.conn.execute(
                            """
                            INSERT INTO guji_scan_mapping
                            (file_name, file_path, file_type, book_id, source_table)
                            VALUES ($1, $2, $3, $4, $5)
                        """,
                            file_info["name"],
                            file_info["path"],
                            file_info["ext"],
                            book_id,
                            source_table,
                        )

                        matched += 1
                        if matched % 100 == 0:
                            print(f"  已匹配 {matched} 个文件...")
                except ValueError:
                    continue

        print(f"  ✅ 完成: {matched} 个文件已映射")

    async def show_status(self):
        """显示当前状态"""
        print("\n📊 当前状态:")

        total = await self.conn.fetchval("SELECT COUNT(*) FROM guji_scan_mapping")
        print(f"  guji_scan_mapping 记录数: {total}")

        if total > 0:
            rows = await self.conn.fetch(
                """
                SELECT source_table, COUNT(*) as cnt
                FROM guji_scan_mapping
                GROUP BY source_table
                ORDER BY cnt DESC
                LIMIT 10
            """
            )

            print("\n  按来源表统计:")
            for row in rows:
                print(f"    {row['source_table']:15} {row['cnt']:6} 个文件")

            samples = await self.conn.fetch(
                """
                SELECT file_name, book_id, source_table
                FROM guji_scan_mapping
                LIMIT 10
            """
            )

            print("\n  映射示例:")
            for row in samples:
                print(
                    f"    {row['file_name']:40} -> book_id={row['book_id']} ({row['source_table']})"
                )

    async def run(self, mode: str = "map"):
        """运行主流程"""
        await self.init()

        try:
            if mode == "scan":
                await self.build_file_index()
            elif mode == "map":
                await self.build_file_index()
                await self.build_title_index()
                await self.establish_mapping()
            elif mode == "status":
                await self.show_status()
        finally:
            await self.close()


async def main():
    """主函数"""
    mode = sys.argv[1] if len(sys.argv) > 1 else "map"

    print("=" * 60)
    print("📚 古籍扫描文档映射工具")
    print("=" * 60)
    print(f"模式: {mode}")
    print(f"时间: {datetime.now()}")
    print()

    mapper = GujiMapper()
    await mapper.run(mode)

    print("\n" + "=" * 60)
    print("✅ 完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
