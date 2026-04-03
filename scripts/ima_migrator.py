"""
Ima知识库数据导出工具
从SQLite数据库提取气功、中医、儒家相关内容
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

DB_PATH = "/home/ai/zhineng-knowledge-system/data/data.db"
OUTPUT_DIR = Path("/home/ai/zhineng-knowledge-system/data/ima_export")


def extract_knowledge(db_path: str, patterns: Dict[str, List[str]]) -> Dict[str, List[Dict]]:
    """
    从数据库提取知识内容

    Args:
        db_path: 数据库路径
        patterns: 分类匹配模式 {"category": ["pattern1", "pattern2"]}

    Returns:
        按分类组织的知识数据
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    result = {category: [] for category in patterns.keys()}

    for category, keywords in patterns.items():
        print(f"\n提取 {category} 类知识...")

        # 构建查询条件
        conditions = []
        params = []
        for kw in keywords:
            conditions.append("(parent LIKE ? OR name LIKE ?)")
            params.extend([f"%{kw}%", f"%{kw}%"])

        where_clause = " OR ".join(conditions)

        query = f"""
            SELECT parent, name, is_dir, size
            FROM x_search_nodes
            WHERE {where_clause}
            AND is_dir = 0
            ORDER BY parent, name
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()

        for parent, name, is_dir, size in rows:
            result[category].append({"path": f"{parent}/{name}", "name": name, "size": size})

        print(f"  找到 {len(result[category])} 个文件")

    conn.close()
    return result


def main():
    """主函数"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 定义分类匹配模式
    patterns = {
        "气功": ["气功", "八段锦", "五禽戏", "六字诀", "易筋经"],
        "中医": ["中医", "伤寒", "黄帝内经", "本草", "针灸", "经络"],
        "儒家": ["儒家", "论语", "孟子", "大学", "中庸"],
        "太极": ["太极", "太极拳", "杨氏", "陈氏", "孙氏"],
    }

    # 提取数据
    knowledge = extract_knowledge(DB_PATH, patterns)

    # 保存结果
    for category, items in knowledge.items():
        if items:
            output_file = OUTPUT_DIR / f"{category}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            print(f"已保存: {output_file} ({len(items)} 条)")

    # 生成统计
    stats = {cat: len(items) for cat, items in knowledge.items()}
    stats_file = OUTPUT_DIR / "stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\n统计信息已保存到: {stats_file}")
    print(f"总计: {sum(stats.values())} 条")


if __name__ == "__main__":
    main()
