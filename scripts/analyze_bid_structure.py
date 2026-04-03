#!/usr/bin/env python3
"""
分析 bid 值与书名的关系
"""

import sqlite3
import re
from pathlib import Path
from collections import defaultdict
import json

SQLITE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"

def extract_book_title(content: str) -> str:
    """从内容中提取书名"""
    # 查找书名模式（通常在开头）
    lines = content.split('\n')[:5]  # 只看前5行

    for line in lines:
        line = line.strip()
        if not line or line.startswith('　　'):
            continue

        # 常见书名模式
        if '史記' in line or '史记' in line:
            return "史记"
        elif '漢書' in line or '汉书' in line:
            return "汉书"
        elif '後漢書' in line or '后汉书' in line:
            return "后汉书"
        elif '三國志' in line or '三国志' in line:
            return "三国志"
        elif '晉書' in line or '晋书' in line:
            return "晋书"
        elif '宋書' in line or '宋书' in line:
            return "宋书"
        elif '南齊書' in line or '南齐书' in line:
            return "南齐书"
        elif '梁書' in line or '梁书' in line:
            return "梁书"
        elif '陳書' in line or '陈书' in line:
            return "陈书"
        elif '魏書' in line or '魏书' in line:
            return "魏书"
        elif '北齊書' in line or '北齐书' in line:
            return "北齐书"
        elif '周書' in line or '周书' in line:
            return "周书"
        elif '隋書' in line or '隋书' in line:
            return "隋书"
        elif '舊唐書' in line or '旧唐书' in line:
            return "旧唐书"
        elif '新唐書' in line or '新唐书' in line:
            return "新唐书"
        elif '舊五代史' in line or '旧五代史' in line:
            return "旧五代史"
        elif '新五代史' in line or '新五代史' in line:
            return "新五代史"
        elif '宋史' in line:
            return "宋史"
        elif '遼史' in line or '辽史' in line:
            return "辽史"
        elif '金史' in line:
            return "金史"
        elif '元史' in line:
            return "元史"
        elif '明史' in line:
            return "明史"

    # 默认返回前20个字符
    return content[:20].strip()


def analyze_wx201():
    """分析 wx201 表的 bid 结构"""
    conn = sqlite3.connect(str(SQLITE_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取每个 bid 的第一条记录
    cursor.execute("""
        SELECT bid, id, substr(body, 1, 150) as content_preview
        FROM wx201
        WHERE id IN (
            SELECT MIN(id) FROM wx201 GROUP BY bid
        )
        ORDER BY bid
        LIMIT 50
    """)

    print("=" * 70)
    print("📚 wx201 表 bid 值与书籍对应关系 (前50个)")
    print("=" * 70)
    print()

    bid_to_book = {}
    for row in cursor.fetchall():
        bid = row['bid']
        content = row['content_preview']

        # 提取书名
        book_name = extract_book_title(content)

        # 尝试从内容中识别关键词
        keywords = []
        if '史記' in content: keywords.append('史记')
        if '漢書' in content: keywords.append('汉书')
        if '後漢書' in content: keywords.append('后汉书')
        if '三國志' in content: keywords.append('三国志')
        if '高祖' in content: keywords.append('高祖')
        if '光武' in content: keywords.append('光武帝')
        if '武帝' in content: keywords.append('武帝')

        bid_to_book[bid] = {
            'book_name': book_name if book_name else '未知',
            'keywords': keywords,
            'preview': content[:50].replace('\n', ' ')
        }

        print(f"bid={bid:4d} | {book_name if book_name else '未知':10} | 关键词: {', '.join(keywords) if keywords else '-'}")
        print(f"         预览: {content[:50].replace(chr(10), ' ')}...")
        print()

    conn.close()

    return bid_to_book


def main():
    """主函数"""
    bid_to_book = analyze_wx201()

    # 保存结果
    output_file = Path(__file__).parent.parent / "data" / "bid_book_mapping.json"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(bid_to_book, f, ensure_ascii=False, indent=2)

    print(f"✅ 映射结果已保存: {output_file}")


if __name__ == "__main__":
    main()
