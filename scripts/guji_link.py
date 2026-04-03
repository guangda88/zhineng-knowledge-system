#!/usr/bin/env python3
"""
古籍扫描文档与文本内容映射 - 简化版

直接查询 SQLite 数据库，建立映射索引
"""

import json
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

# 配置
SQLITE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"
POSTGRES_CONTAINER = "dfdd3b278296_zhineng-postgres"


def extract_book_key(filename: str) -> str:
    """从文件名提取书籍关键词"""
    name = filename.rsplit(".", 1)[0] if "." in filename else filename

    # 去除数字前缀
    name = re.sub(r"^\d+", "", name)

    # 提取核心书名（去除卷号、版本说明等）
    patterns_to_remove = [
        r"[一二三四五六七八九十百千万上下卷部種編]+[、\s]*$",
        r"卷[一二三四五六七八九十百千万]+",
        r"[正义疏注]*[一二三四五六七八九十百千万]*$",
        r"\s*[宋元明清明][刊刻校本]*本.*$",
        r"[（(].*?[）)]",
        r"\s*[左海文集本]*$",
        r"\s*[嘉業堂藏宋刊本]*$",
        r"\s*[觀古堂藏明翻宋岳氏相台本]*$",
        r"\s*[明徐氏刊仿宋本]*$",
        r"\s*[宋本]*$",
        r"\s*[玉田蔣氏藏宋刊巾箱本]*$",
        r"\s*[汉上易传]*$",
    ]

    for pattern in patterns_to_remove:
        name = re.sub(pattern, "", name)

    return name.strip(" ._-、（）")


def search_book_in_sqlite(book_name: str, conn: sqlite3.Connection) -> List[dict]:
    """在 SQLite 中搜索书籍内容"""
    cursor = conn.cursor()

    # 先尝试精确匹配
    cursor.execute(
        "SELECT id, bid, substr(body, 1, 200) as preview FROM wx200 WHERE body LIKE ? LIMIT 5",
        (f"%{book_name}%",),
    )

    results = []
    for row in cursor.fetchall():
        results.append(
            {"source_table": "wx200", "source_id": row[0], "bid": row[1], "preview": row[2]}
        )

    # 如果没找到，尝试在 wx201 搜索
    if not results:
        try:
            cursor.execute(
                "SELECT id, bid, substr(body, 1, 200) as preview FROM wx201 WHERE body LIKE ? LIMIT 5",
                (f"%{book_name}%",),
            )

            for row in cursor.fetchall():
                results.append(
                    {"source_table": "wx201", "source_id": row[0], "bid": row[1], "preview": row[2]}
                )
        except Exception:
            pass

    return results


def main():
    """主函数"""
    print("=" * 70)
    print("🔗 古籍扫描文档与文本内容映射")
    print("=" * 70)
    print()

    # 1. 连接 SQLite
    if not SQLITE_DB.exists():
        print(f"❌ 数据库不存在: {SQLITE_DB}")
        return

    conn = sqlite3.connect(str(SQLITE_DB))
    print(f"✅ 连接 SQLite: {SQLITE_DB}")
    print()

    # 2. 获取扫描文档列表
    print("📁 读取扫描文档列表...")
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
            "SELECT file_name, book_id FROM guji_scan_mapping ORDER BY book_id",
        ],
        capture_output=True,
        text=True,
    )

    scan_files = []
    for line in result.stdout.strip().split("\n"):
        if line and "|" in line and not line.startswith("-"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                try:
                    filename = parts[0]
                    book_id = int(parts[1])
                    scan_files.append((filename, book_id))
                except ValueError:
                    continue

    print(f"  共 {len(scan_files)} 个扫描文档")
    print()

    # 3. 建立映射
    print("🔍 建立映射关系...")

    mapping_results = {}
    matched_count = 0
    unmatched = []

    # 按书名分组
    book_groups = {}
    for filename, book_id in scan_files:
        key = extract_book_key(filename)
        if key not in book_groups:
            book_groups[key] = []
        book_groups[key].append((filename, book_id))

    print(f"  提取到 {len(book_groups)} 个不同的书名")
    print()

    # 搜索每个书名
    for book_name, files in sorted(book_groups.items())[:50]:  # 限制处理数量
        results = search_book_in_sqlite(book_name, conn)

        if results:
            matched_count += 1
            sample_filename = files[0][0]
            print(f"  ✓ {book_name} → {len(results)} 条内容")
            print(f"    示例文件: {sample_filename}")
            print(f"    内容预览: {results[0]['preview'][:60]}...")
            print()

            mapping_results[book_name] = {
                "files": [f[0] for f in files],
                "content_sources": results,
            }
        else:
            unmatched.append((book_name, files[0][0]))

    conn.close()

    # 4. 输出统计
    print("=" * 70)
    print("📊 映射统计")
    print("=" * 70)
    print(f"  处理书名数: {len(book_groups)}")
    print(f"  成功匹配: {matched_count}")
    print(f"  未匹配: {len(unmatched)}")
    print()

    if unmatched:
        print("未匹配的书名 (前20个):")
        for book_name, sample_file in unmatched[:20]:
            print(f"  - {book_name} ({sample_file})")

    # 5. 保存映射结果
    output_file = Path(__file__).parent.parent / "data" / "guji_mapping.json"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(mapping_results, f, ensure_ascii=False, indent=2)

    print()
    print(f"✅ 映射结果已保存: {output_file}")

    # 6. 生成 SQL 导入脚本
    sql_file = Path(__file__).parent.parent / "data" / "import_mapping.sql"
    with open(sql_file, "w", encoding="utf-8") as f:
        f.write("-- 古籍扫描文档与文本内容映射 SQL\n")
        f.write("-- 自动生成\n\n")

        for book_name, data in mapping_results.items():
            for content in data["content_sources"]:
                safe_preview = content["preview"].replace("'", "''").replace("\n", "\\n")[:100]
                f.write(f"-- {book_name}\n")
                f.write(
                    f"INSERT INTO guji_content_mapping (book_name, source_table, source_id, content_preview)\n"
                )
                f.write(
                    f"VALUES ('{book_name}', '{content['source_table']}', {content['source_id']}, '{safe_preview}');\n\n"
                )

    print(f"✅ SQL 脚本已生成: {sql_file}")


if __name__ == "__main__":
    main()
