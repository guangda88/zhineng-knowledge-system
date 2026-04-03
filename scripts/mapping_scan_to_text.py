#!/usr/bin/env python3
"""
古籍扫描文档与文本内容映射脚本

原理:
1. 从扫描文档文件名提取书名（如 "周易一" → "周易"）
2. 在数据库中搜索匹配的书名
3. 建立 guji_scan_mapping 与 guji_documents 的关联
"""

import re
import sqlite3
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# 配置
POSTGRES_CONTAINER = "dfdd3b278296_zhineng-postgres"
SQLITE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"

# 书名映射表（扫描文档文件名 → 数据库书名）
BOOK_NAME_MAPPING = {
    # 经部
    "周易": ["周易", "易經", "易"],
    "尚书": ["尚書", "書", "书经", "尚书正义"],
    "毛诗": ["毛詩", "詩經", "诗经", "诗"],
    "周礼": ["周禮", "禮", "周礼"],
    "仪礼": ["儀禮", "仪礼", "仪礼疏"],
    "礼记": ["禮記", "礼记"],
    "春秋": ["春秋", "春秋经传"],
    "论语": ["論語", "论语"],
    "孟子": ["孟子"],
    "孝经": ["孝經"],
    "尔雅": ["爾雅", "尔雅"],
    "仪礼疏": ["儀禮", "仪礼"],
    # 史部
    "史记": ["史記"],
    "汉书": ["漢書", "前漢書"],
    "后汉书": ["後漢書"],
    "三国志": ["三國志"],
    "晋书": ["晉書"],
    "宋书": ["宋書"],
    "齐书": ["齊書", "南齊書"],
    "梁书": ["梁書"],
    "陈书": ["陳書"],
    "魏书": ["魏書"],
    "北齐书": ["北齊書"],
    "周书": ["周書"],
    "隋书": ["隋書"],
    "旧唐书": ["舊唐書", "旧唐书"],
    "新唐书": ["新唐書"],
    "旧五代史": ["舊五代史"],
    "新五代史": ["新五代史"],
    "宋史": ["宋史"],
    "辽史": ["遼史", "辽史"],
    "金史": ["金史"],
    "元史": ["元史"],
    "明史": ["明史"],
    "资治通鉴": ["資治通鑑", "资治通鉴", "通鉴"],
    "通志": ["通志"],
    "文献通考": ["文獻通考"],
    # 子部
    "老子": ["老子", "道德經"],
    "庄子": ["莊子"],
    "荀子": ["荀子"],
    "韩非子": ["韓非子"],
    "墨子": ["墨子"],
    "管子": ["管子"],
    "孙子": ["孫子", "孫子兵法"],
    "列子": ["列子"],
    "淮南子": ["淮南子"],
    "吕氏春秋": ["呂氏春秋"],
    "楚辞": ["楚辭"],
    "说苑": ["說苑"],
    "新序": ["新序"],
    "法言": ["法言"],
    "论衡": ["論衡"],
    "颜氏家训": ["顔氏家訓"],
    # 集部
    "文选": ["文選", "昭明文選"],
    "李太白集": ["李太白", "李白"],
    "杜工部集": ["杜工部", "杜甫"],
    "苏东坡集": ["蘇東坡", "蘇軾"],
    "稼轩词": ["稼軒詞", "辛弃疾"],
    "放翁词": ["放翁詞", "陆游"],
    "漱玉词": ["漱玉詞", "李清照"],
    # 其他常见
    "北溪字义": ["北溪字義", "北溪"],
    "四书章句集注": ["四書章句集注", "四书"],
    "朱子语类": ["朱子語類"],
}


def extract_book_name(filename: str) -> str:
    """从文件名提取书名"""
    # 去除扩展名
    name = filename.rsplit(".", 1)[0] if "." in filename else filename

    # 去除数字前缀
    name = re.sub(r"^\d+", "", name)

    # 特殊处理：去除 "正義"、"疏"、"注" 等版本标识
    name = re.sub(r"[正义疏注]+[一二三四五六七八九十百千万]*$", "", name)

    # 去除卷号标识（如 "一", "二", "上", "下", "卷一" 等）
    name = re.sub(r"[一二三四五六七八九十百千万上下卷部種編]+$[、\s]*", "", name)
    name = re.sub(r"卷[一二三四五六七八九十百千万]+", "", name)

    # 去除版本说明（如 "宋刊本", "明刻本" 等）
    name = re.sub(r"\s*[宋元明清明][刊刻校本]*本.*$", "", name)

    # 去除括号内容
    name = re.sub(r"[（(].*?[）)]", "", name)

    # 去除特殊字符
    name = name.strip(" ._-、（）")

    return name


def normalize_book_name(name: str) -> str:
    """标准化书名用于匹配"""
    # 繁简转换（这里只处理常见情况）
    name = name.replace("周易", "周易")
    name = name.replace("尚書", "尚书")
    name = name.replace("毛詩", "毛诗")
    name = name.replace("周禮", "周礼")
    name = name.replace("儀禮", "仪礼")
    name = name.replace("禮記", "礼记")
    name = name.replace("論語", "论语")
    name = name.replace("孟子", "孟子")

    return name


def find_content_in_sqlite(book_name: str, conn: sqlite3.Connection) -> List[Tuple[int, int, str]]:
    """在 SQLite 数据库中查找书名对应的内容"""
    variants = []

    # 从映射表获取变体
    for base, variant_list in BOOK_NAME_MAPPING.items():
        if book_name in variant_list or book_name == base:
            variants = [base] + variant_list
            break

    if not variants:
        variants = [book_name]

    results = []

    for variant in variants:
        # 在 wx200 表中搜索
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, bid, substr(body, 1, 100) as preview FROM wx200 WHERE body LIKE ? LIMIT 5",
            (f"%{variant}%",),
        )

        for row in cursor.fetchall():
            results.append((row[0], row[1], row[2]))

        # 如果找到了就停止
        if results:
            break

    return results


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


def main():
    """主函数"""
    print("=" * 70)
    print("🔗 古籍扫描文档与文本内容映射")
    print("=" * 70)
    print()

    # 1. 获取当前扫描文档映射
    print("📁 读取扫描文档映射...")

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
            "SELECT file_name, book_id, file_path FROM guji_scan_mapping ORDER BY book_id",
        ],
        capture_output=True,
        text=True,
    )

    scan_files = []
    for line in result.stdout.strip().split("\n"):
        if line and "|" in line and not line.startswith("-"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                filename = parts[0]
                try:
                    book_id = int(parts[1])
                    scan_files.append((filename, book_id))
                except ValueError:
                    continue

    print(f"  读取到 {len(scan_files)} 个扫描文档")
    print()

    # 2. 连接 SQLite 数据库
    print("📖 连接文本数据库...")
    if not SQLITE_DB.exists():
        print(f"  ❌ 数据库不存在: {SQLITE_DB}")
        return

    conn = sqlite3.connect(str(SQLITE_DB))
    conn.row_factory = sqlite3.Row
    print(f"  ✅ 已连接: {SQLITE_DB}")
    print()

    # 3. 提取书名并查找内容
    print("🔍 匹配扫描文档与文本内容...")

    # 创建新的映射表
    exec_sql(
        """
        CREATE TABLE IF NOT EXISTS guji_content_mapping (
            id SERIAL PRIMARY KEY,
            scan_file_name VARCHAR(255),
            scan_book_id INTEGER,
            content_book_name VARCHAR(100),
            content_source_id INTEGER,
            content_source_table VARCHAR(50),
            content_preview TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """
    )

    # 清空旧映射
    exec_sql("TRUNCATE TABLE guji_content_mapping")

    # 统计
    matched = 0
    unmatched_books = defaultdict(list)

    for filename, scan_book_id in scan_files:
        # 提取书名
        raw_name = extract_book_name(filename)
        book_name = normalize_book_name(raw_name)

        # 查找内容
        contents = find_content_in_sqlite(book_name, conn)

        if contents:
            for source_id, bid, preview in contents[:3]:  # 最多3条
                safe_preview = preview.replace("'", "''")[:200]

                exec_sql(
                    f"""
                    INSERT INTO guji_content_mapping
                    (scan_file_name, scan_book_id, content_book_name,
                     content_source_id, content_source_table, content_preview)
                    VALUES ('{filename}', {scan_book_id}, '{book_name}',
                            {source_id}, 'wx200', '{safe_preview}')
                """
                )

                matched += 1

                print(f"  ✓ {filename} → {book_name} (wx200:{source_id})")
        else:
            unmatched_books[book_name].append(filename)

    conn.close()

    print()
    print("=" * 70)
    print("📊 映射统计")
    print("=" * 70)

    # 统计
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
            "SELECT COUNT(*) FROM guji_content_mapping",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        total = result.stdout.strip()
        print(f"  成功映射: {total} 条")

    if unmatched_books:
        print(f"\n  未匹配的书名 ({len(unmatched_books)} 个):")
        for book_name, files in list(unmatched_books.items())[:10]:
            print(f"    - {book_name}: {files[0]}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
