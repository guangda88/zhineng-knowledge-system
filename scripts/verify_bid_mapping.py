#!/usr/bin/env python3
"""
抽查验证 bid 值与目录结构的映射关系
验证 20% 的数据
"""

import asyncio
import json
import random
import sqlite3
from pathlib import Path

import aiohttp

SQLITE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"
OPENLIST_BASE = "http://100.66.1.8:2455"


async def check_115_directory(session, bid: int) -> dict:
    """检查 115 目录中是否存在对应的 bid 目录"""
    paths_to_try = [
        f"/115/国学大师/guji/{bid}",
        f"/115/guji/{bid}",
        f"/115/{bid}",
        f"/115/国学大师/{bid}",
    ]

    for path in paths_to_try:
        try:
            payload = {"path": path, "password": "", "page": 1, "per_page": 10}

            async with session.post(
                f"{OPENLIST_BASE}/api/fs/list", json=payload, timeout=5
            ) as resp:
                data = await resp.json()
                if data.get("code") == 200:
                    content = data.get("data", {}).get("content", [])
                    return {
                        "bid": bid,
                        "found": True,
                        "path": path,
                        "items": len(content),
                        "sample_items": [c.get("name", "") for c in content[:5]],
                    }
        except Exception:
            continue

    return {"bid": bid, "found": False, "path": None, "items": 0, "sample_items": []}


def get_bid_sample_from_db():
    """从数据库获取 bid 样本信息"""
    conn = sqlite3.connect(str(SQLITE_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取所有唯一的 bid 值
    cursor.execute(
        """
        SELECT DISTINCT bid, COUNT(*) as record_count
        FROM wx201
        GROUP BY bid
        ORDER BY bid
    """
    )

    all_bids = [(row["bid"], row["record_count"]) for row in cursor.fetchall()]

    # 随机选择 20% 的 bid 值
    sample_size = max(20, int(len(all_bids) * 0.2))
    sampled_bids = random.sample(all_bids, min(sample_size, len(all_bids)))

    # 获取每个 bid 的内容预览
    bid_info = {}
    for bid, count in sampled_bids:
        cursor.execute(
            """
            SELECT id, substr(body, 1, 200) as preview
            FROM wx201
            WHERE bid = ?
            ORDER BY id
            LIMIT 1
        """,
            (bid,),
        )

        row = cursor.fetchone()
        if row:
            # 提取书名
            preview = row["preview"]
            book_name = extract_book_name_from_preview(preview)

            bid_info[bid] = {
                "record_count": count,
                "first_id": row["id"],
                "preview": preview,
                "book_name": book_name,
            }

    conn.close()
    return bid_info


def extract_book_name_from_preview(preview: str) -> str:
    """从预览中提取书名"""
    # 常见的书名模式
    patterns = [
        (r"史記者", "史记"),
        (r"史記集解", "史记集解"),
        (r"漢書", "汉书"),
        (r"後漢書", "后汉书"),
        (r"三國志", "三国志"),
        (r"晉書", "晋书"),
        (r"宋書", "宋书"),
        (r"南齊書", "南齐书"),
        (r"梁書", "梁书"),
        (r"陳書", "陈书"),
        (r"魏書", "魏书"),
        (r"北齊書", "北齐书"),
        (r"周書", "周书"),
        (r"隋書", "隋书"),
        (r"舊唐書", "旧唐书"),
        (r"新唐書", "新唐书"),
        (r"舊五代史", "旧五代史"),
        (r"新五代史", "新五代史"),
        (r"宋史", "宋史"),
        (r"遼史", "辽史"),
        (r"金史", "金史"),
        (r"元史", "元史"),
        (r"明史", "明史"),
    ]

    preview_clean = preview[:100].replace("\n", " ").replace("\r", "")

    for pattern, name in patterns:
        import re

        if re.search(pattern, preview_clean):
            return name

    # 尝试提取第一个有意义的词
    import re

    match = re.search(r"[\u4e00-\u9fa5]{2,6}", preview_clean)
    if match:
        return match.group(0)

    return "未知"


async def main():
    """主函数"""
    print("=" * 70)
    print("🔍 抽查验证 bid 值与目录映射关系 (20% 数据)")
    print("=" * 70)
    print()

    # 1. 从数据库获取样本
    print("📚 从数据库获取 bid 样本...")
    bid_info = get_bid_sample_from_db()
    sampled_bids = sorted(bid_info.keys())

    print(f"  总共 {len(sampled_bids)} 个 bid 值待验证")
    print(f"  bid 范围: {min(sampled_bids)} - {max(sampled_bids)}")
    print()

    # 2. 显示样本信息
    print("📋 样本信息:")
    for bid in sampled_bids[:10]:
        info = bid_info[bid]
        print(f"  bid={bid:4d} | {info['book_name']:15} | {info['record_count']:4} 条记录")
        print(f"         预览: {info['preview'][:60].replace(chr(10), ' ')}...")
    print()

    # 3. 检查 115 目录
    print("🔍 检查 115 存储中的对应目录...")
    async with aiohttp.ClientSession() as session:
        results = []
        for i, bid in enumerate(sampled_bids):
            result = await check_115_directory(session, bid)
            results.append(result)

            if result["found"]:
                print(f"  ✓ bid={bid:4d} → 找到: {result['path']} ({result['items']} 项)")
            else:
                print(f"  ✗ bid={bid:4d} → 未找到对应目录")

            if (i + 1) % 10 == 0:
                print()

    # 4. 统计结果
    found_count = sum(1 for r in results if r["found"])
    not_found_count = len(results) - found_count

    print()
    print("=" * 70)
    print("📊 验证结果统计")
    print("=" * 70)
    print(f"  样本总数: {len(results)}")
    print(f"  找到对应: {found_count} ({found_count/len(results)*100:.1f}%)")
    print(f"  未找到: {not_found_count} ({not_found_count/len(results)*100:.1f}%)")
    print()

    # 5. 详细展示找到的目录
    if found_count > 0:
        print("✅ 已验证的映射:")
        for r in results:
            if r["found"]:
                info = bid_info.get(r["bid"], {})
                print(f"  /115/国学大师/guji/{r['bid']}/")
                print(f"    数据库: {info.get('book_name', '未知')}")
                print(f"    记录数: {info.get('record_count', 0)}")
                print(f"    目录内容: {r['sample_items'][:5]}")
                print()

    # 6. 保存结果
    output = {
        "total_sampled": len(results),
        "found": found_count,
        "not_found": not_found_count,
        "match_rate": found_count / len(results) if results else 0,
        "results": results,
        "bid_info": bid_info,
    }

    output_file = Path(__file__).parent.parent / "data" / "bid_verification.json"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 验证结果已保存: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
