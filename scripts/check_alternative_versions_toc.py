#!/usr/bin/env python3
"""
检查教材7和8的替代版本的目录深度
"""

import sys
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from backend.textbook_processing.deep_toc_parser import DeepTocParser, ParseMethod


def check_toc_depth(text_path: Path) -> int:
    """检查目录深度"""
    print(f"\n检查文件: {text_path.name}")

    if not text_path.exists():
        print(f"  ✗ 文件不存在")
        return 0

    # 读取文本
    encodings = ["utf-8", "gbk", "gb2312", "gb18030"]
    content = None

    for encoding in encodings:
        try:
            with open(text_path, "r", encoding=encoding) as f:
                content = f.read()
            if len(content) > 1000:
                break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if not content:
        print(f"  ✗ 无法读取文本")
        return 0

    # 解析目录
    parser = DeepTocParser()

    # 尝试多种解析方法
    for method in [ParseMethod.HEURISTIC, ParseMethod.REGEX]:
        try:
            result = parser.parse(content, method=method)

            depth = result.max_depth
            items_count = len(result.items)

            print(f"  方法: {method.name}")
            print(f"  目录深度: {depth} 层")
            print(f"  目录项数: {items_count}")

            return depth

        except Exception as e:
            print(f"  方法 {method.name} 失败: {e}")
            continue

    print(f"  ✗ 所有方法都失败")
    return 0


def main():
    """主函数"""
    print("=" * 70)
    print("检查教材7和8的替代版本目录深度")
    print("=" * 70)

    base_dir = Path(__file__).parent.parent / "data" / "textbooks"

    # 教材7的替代版本
    print("\n" + "=" * 70)
    print("教材7: 智能气功科学气功与人类文化")
    print("=" * 70)

    textbook7_versions = [
        base_dir / "txt格式" / "7智能气功科学气功与人类文化2010版.txt",
        base_dir / "txt格式" / "气功与人类文化.txt",
    ]

    results7 = []
    for version_path in textbook7_versions:
        depth = check_toc_depth(version_path)
        results7.append({"path": str(version_path), "depth": depth})

    # 教材8的替代版本
    print("\n" + "=" * 70)
    print("教材8: 中国气功发展简史")
    print("=" * 70)

    textbook8_versions = [
        base_dir / "txt格式" / "8智能气功科学中国气功发展简史2010版(1).txt",
        base_dir / "txt格式" / "气功发展简史.txt",
    ]

    results8 = []
    for version_path in textbook8_versions:
        depth = check_toc_depth(version_path)
        results8.append({"path": str(version_path), "depth": depth})

    # 汇总结果
    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)

    print("\n教材7:")
    for r in results7:
        path = Path(r["path"])
        print(f"  {path.name}: {r['depth']} 层")

    print("\n教材8:")
    for r in results8:
        path = Path(r["path"])
        print(f"  {path.name}: {r['depth']} 层")

    # 推荐
    print("\n" + "=" * 70)
    print("推荐")
    print("=" * 70)

    # 找到深度≥6的版本
    print("\n教材7（目标6层）:")
    best7 = max(results7, key=lambda x: x["depth"])
    if best7["depth"] >= 6:
        print(f"  ✓ 推荐使用: {Path(best7['path']).name} ({best7['depth']}层)")
    else:
        print(f"  ⚠️  所有版本都不足6层，需要AI补充")
        print(f"  最佳版本: {Path(best7['path']).name} ({best7['depth']}层)")

    print("\n教材8（目标6层）:")
    best8 = max(results8, key=lambda x: x["depth"])
    if best8["depth"] >= 6:
        print(f"  ✓ 推荐使用: {Path(best8['path']).name} ({best8['depth']}层)")
    else:
        print(f"  ⚠️  所有版本都不足6层，需要AI补充")
        print(f"  最佳版本: {Path(best8['path']).name} ({best8['depth']}层)")


if __name__ == "__main__":
    main()
