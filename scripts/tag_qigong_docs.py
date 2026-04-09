#!/usr/bin/env python3
"""
智能气功资料批量打标CLI工具

功能：
- 批量自动打标
- 覆盖率统计
- 维度验证
- 打标报告生成
"""
import argparse
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.qigong import QigongBatchTagger, QigongPathParser


async def main():
    parser = argparse.ArgumentParser(
        description="智能气功资料批量打标工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 统计覆盖率
  python scripts/tag_qigong_docs.py stats

  # 批量打标（测试模式）
  python scripts/tag_qigong_docs.py tag --dry-run

  # 批量打标（执行模式）
  python scripts/tag_qigong_docs.py tag

  # 验证维度数据
  python scripts/tag_qigong_docs.py validate

  # 解析单个文件路径
  python scripts/tag_qigong_docs.py parse "/大专班/精义/34/285明了调息的目的和作用C.mpg"
        """,
    )

    # 数据库连接
    parser.add_argument(
        "--db-url", default="postgresql://user:password@localhost/dbname", help="PostgreSQL连接URL"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # stats 命令
    subparsers.add_parser("stats", help="显示打标覆盖率统计")

    # tag 命令
    tag_parser = subparsers.add_parser("tag", help="执行批量打标")
    tag_parser.add_argument("--pattern", default="%", help="文件路径匹配模式 (LIKE语法，默认全部)")
    tag_parser.add_argument("--dry-run", action="store_true", help="只测试不实际写入")

    # validate 命令
    subparsers.add_parser("validate", help="验证维度数据")

    # parse 命令
    parse_parser = subparsers.add_parser("parse", help="解析单个文件路径")
    parse_parser.add_argument("path", help="文件路径")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行对应命令
    if args.command == "stats":
        await cmd_stats(args)
    elif args.command == "tag":
        await cmd_tag(args)
    elif args.command == "validate":
        await cmd_validate(args)
    elif args.command == "parse":
        cmd_parse(args)


async def cmd_stats(args):
    """显示统计信息"""
    tagger = QigongBatchTagger(args.db_url)
    try:
        stats = await tagger.get_coverage_stats()

        print("\n" + "=" * 60)
        print("智能气功资料打标覆盖率统计")
        print("=" * 60)

        print(f"\n总文档数: {stats['total']}")
        print(f"已打标: {stats['tagged']} ({stats['coverage_percent']}%)")
        print(f"未打标: {stats['untagged']}")

        print("\n各维度覆盖情况:")
        print("-" * 60)
        for dim, data in stats["dimensions"].items():
            print(f"  {dim:20s}: {data['count']:5d} ({data['coverage_percent']:5.1f}%)")

        print("\n功法类型分布:")
        gongfa_dist = await tagger.get_dimension_distribution("gongfa_method")
        if gongfa_dist:
            for item in gongfa_dist[:10]:
                print(f"  {item['value']:15s}: {item['count']:5d}")

        print("\n教材归属分布:")
        disc_dist = await tagger.get_dimension_distribution("discipline")
        if disc_dist:
            for item in disc_dist:
                print(f"  {item['value']:15s}: {item['count']:5d}")

    finally:
        await tagger.close()


async def cmd_tag(args):
    """执行批量打标"""
    tagger = QigongBatchTagger(args.db_url)
    try:
        print("\n开始批量打标...")
        print(f"模式: {'测试（不写入）' if args.dry_run else '执行'}")
        print(f"路径模式: {args.pattern}")
        print()

        stats = await tagger.tag_by_path_pattern(args.pattern, dry_run=args.dry_run)

        print("\n" + "=" * 60)
        print("批量打标完成")
        print("=" * 60)
        print(f"处理文档数: {stats['total']}")
        print(f"成功打标: {stats['tagged']}")
        print(f"跳过: {stats['skipped']}")
        print(f"错误: {stats['errors']}")
        print(f"耗时: {stats.get('duration_seconds', 0):.1f}秒")

        # 再次统计
        coverage = await tagger.get_coverage_stats()
        print(f"\n当前覆盖率: {coverage['coverage_percent']}%")

    finally:
        await tagger.close()


async def cmd_validate(args):
    """验证维度数据"""
    tagger = QigongBatchTagger(args.db_url)
    try:
        result = await tagger.validate_dimensions()

        print("\n" + "=" * 60)
        print("维度数据验证")
        print("=" * 60)

        print(f"\n使用的维度总数: {result['total_dimensions_used']}")
        print(f"有效维度数: {result['valid_dimensions']}")
        print(f"无效维度数: {len(result['invalid_dimensions'])}")
        print(f"验证状态: {'✓ 通过' if result['is_valid'] else '✗ 失败'}")

        if result["invalid_dimensions"]:
            print("\n无效维度:")
            for dim in result["invalid_dimensions"]:
                print(f"  - {dim}")

    finally:
        await tagger.close()


def cmd_parse(args):
    """解析单个文件路径"""
    print("\n" + "=" * 60)
    print("路径解析测试")
    print("=" * 60)

    result = QigongPathParser.parse(args.path)

    print(f"\n路径: {args.path}")
    print("\n解析结果:")
    dims = result.to_dict()
    for key, value in dims.items():
        if isinstance(value, list):
            print(f"  {key}: {', '.join(value)}")
        else:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
