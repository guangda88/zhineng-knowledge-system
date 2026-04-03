#!/usr/bin/env python3
"""
古籍扫描文档查询工具

用法:
    python scripts/guji_query.py --book-id 1001    # 查找指定 book_id 的扫描文档
    python scripts/guji_query.py --title "周易"     # 按标题搜索
    python scripts/guji_query.py --stats            # 显示统计信息
"""

import subprocess
import sys
import argparse
from pathlib import Path

POSTGRES_CONTAINER = "dfdd3b278296_zhineng-postgres"


def query_sql(sql: str) -> str:
    """执行 SQL 查询"""
    cmd = [
        "docker", "exec", POSTGRES_CONTAINER,
        "psql", "-U", "zhineng", "-d", "zhineng_kb",
        "-c", sql
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def show_stats():
    """显示统计信息"""
    print("=" * 70)
    print("📊 古籍扫描文档映射统计")
    print("=" * 70)
    print()

    # 总体统计
    output = query_sql("""
        SELECT
            COUNT(*) as total_files,
            COUNT(DISTINCT book_id) as unique_books,
            COUNT(DISTINCT source_table) as source_tables
        FROM guji_scan_mapping
    """)

    print("📈 总体统计:")
    print(output)
    print()

    # 按表统计
    output = query_sql("""
        SELECT
            source_table,
            COUNT(*) as file_count,
            COUNT(DISTINCT book_id) as book_count
        FROM guji_scan_mapping
        GROUP BY source_table
        ORDER BY file_count DESC
    """)

    print("📚 按来源表统计:")
    print(output)
    print()

    # 按类型统计
    output = query_sql("""
        SELECT
            file_type,
            COUNT(*) as count
        FROM guji_scan_mapping
        GROUP BY file_type
        ORDER BY count DESC
    """)

    print("📄 按文件类型统计:")
    print(output)
    print()


def find_by_book_id(book_id: int):
    """查找指定 book_id 的扫描文档"""
    print("=" * 70)
    print(f"🔍 查找 book_id = {book_id} 的扫描文档")
    print("=" * 70)
    print()

    output = query_sql(f"""
        SELECT
            file_name,
            file_path,
            file_type,
            source_table
        FROM guji_scan_mapping
        WHERE book_id = {book_id}
        ORDER BY file_name
    """)

    print(output)

    # 同时查询内容
    content_output = query_sql(f"""
        SELECT
            source_table,
            book_id,
            chapter_id,
            SUBSTRING(body, 1, 100) as preview,
            body_length
        FROM guoxue_content
        WHERE book_id = {book_id}
        LIMIT 5
    """)

    print()
    print("📖 数据库内容预览:")
    print(content_output)


def search_by_title(keyword: str):
    """按标题关键词搜索"""
    print("=" * 70)
    print(f"🔍 搜索标题包含 '{keyword}' 的记录")
    print("=" * 70)
    print()

    # 搜索映射表
    output = query_sql(f"""
        SELECT
            file_name,
            file_path,
            book_id,
            source_table
        FROM guji_scan_mapping
        WHERE file_name ILIKE '%{keyword}%'
        ORDER BY book_id
        LIMIT 20
    """)

    print("📁 找到的扫描文档:")
    print(output)
    print()

    # 搜索内容表
    output = query_sql(f"""
        SELECT
            source_table,
            book_id,
            SUBSTRING(body, 1, 150) as preview
        FROM guoxue_content
        WHERE body ILIKE '%{keyword}%'
        LIMIT 10
    """)

    print("📖 找到的文本内容:")
    print(output)


def show_file_list(limit: int = 50):
    """显示文件列表"""
    print("=" * 70)
    print(f"📄 扫描文档列表 (前 {limit} 个)")
    print("=" * 70)
    print()

    output = query_sql(f"""
        SELECT
            file_name,
            book_id,
            source_table,
            file_type
        FROM guji_scan_mapping
        ORDER BY book_id, file_name
        LIMIT {limit}
    """)

    print(output)


def main():
    parser = argparse.ArgumentParser(description="古籍扫描文档查询工具")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--book-id", type=int, help="查找指定 book_id 的扫描文档")
    parser.add_argument("--title", type=str, help="按标题关键词搜索")
    parser.add_argument("--list", type=int, nargs="?", const=50, help="显示文件列表")
    parser.add_argument("--export", type=str, help="导出映射到文件")

    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.book_id:
        find_by_book_id(args.book_id)
    elif args.title:
        search_by_title(args.title)
    elif args.list is not None:
        show_file_list(args.list)
    elif args.export:
        export_mapping(args.export)
    else:
        show_stats()
        print()
        print("💡 提示:")
        print("  --book-id N    查找指定 book_id 的扫描文档")
        print("  --title KEY    按标题关键词搜索")
        print("  --list [N]     显示文件列表 (默认50个)")
        print("  --export FILE  导出映射到文件")


def export_mapping(filename: str):
    """导出映射到文件"""
    output = query_sql("""
        COPY (
            SELECT
                file_name,
                file_path,
                file_type,
                book_id,
                source_table
            FROM guji_scan_mapping
            ORDER BY source_table, book_id, file_name
        ) TO STDOUT WITH CSV HEADER
    """)

    with open(filename, 'w') as f:
        f.write(output)

    print(f"✅ 导出完成: {filename}")


if __name__ == "__main__":
    main()
