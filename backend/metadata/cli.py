"""
元数据管理CLI

参考: instructkr/claude-code 的 main.py
"""

from __future__ import annotations

import argparse

from . import (
    get_all_workflows,
    get_completed_workflows,
    load_manifest,
)
from .manifest import find_workflows, generate_status_report


def build_parser() -> argparse.ArgumentParser:
    """构建CLI参数解析器"""
    parser = argparse.ArgumentParser(description="智能知识系统元数据管理")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status命令
    subparsers.add_parser("status", help="显示项目状态摘要")

    # report命令
    subparsers.add_parser("report", help="生成完整的项目状态报告")

    # query命令
    query_parser = subparsers.add_parser("query", help="搜索工作流和任务")
    query_parser.add_argument("query", help="搜索关键词")
    query_parser.add_argument("--limit", type=int, default=20, help="结果数量限制")

    # workflows命令
    workflows_parser = subparsers.add_parser("workflows", help="列出所有工作流")
    workflows_parser.add_argument(
        "--status", choices=["all", "completed", "pending"], default="all", help="按状态过滤"
    )
    workflows_parser.add_argument("--limit", type=int, default=20, help="显示数量")

    return parser


def main(argv: list[str] | None = None) -> int:
    """主函数"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "status":
        manifest = load_manifest()

        completed = len(manifest.get_completed_workflows())
        total = len(manifest.workflows)
        percentage = (completed / total * 100) if total > 0 else 0

        lines = [
            "## 项目状态摘要",
            "",
            f"- **总工作流数**: {total}",
            f"- **已完成**: {completed} ({percentage:.1f}%)",
            f"- **待处理**: {total - completed}",
            "",
            f"- **版本**: {manifest.version}",
            f"- **更新**: {manifest.last_updated}",
            "",
        ]

        print("\\n".join(lines))

    elif args.command == "report":
        report = generate_status_report()
        print(report)

    elif args.command == "query":
        results = find_workflows(args.query)

        print(f"# 查询结果: {args.query}")
        print("")
        print(f"找到 {len(results)} 个工作流")
        print("")

        if results:
            print("## 匹配的工作流")
            print("")
            for workflow in results[: args.limit]:
                status_emoji = "✅" if workflow.status == "completed" else "⏳"
                print(f"- {status_emoji} **{workflow.name}** ({workflow.id})")
                print(f"  - {workflow.description}")
            print("")

    elif args.command == "workflows":
        if args.status == "all":
            workflows = get_all_workflows()
        elif args.status == "completed":
            workflows = get_completed_workflows()
        else:  # pending
            workflows = [w for w in get_all_workflows() if w.status != "completed"]

        print(f"# 工作流列表 (状态: {args.status})")
        print(f"\\n总计: {len(workflows)} 个工作流\\n")

        for workflow in workflows[: args.limit]:
            status_emoji = "✅" if workflow.status == "completed" else "⏳"
            print(f"{status_emoji} **{workflow.name}** ({workflow.id})")
            print(f"  - {workflow.description}")
            print(f"  - 团队: {workflow.team}")
            print(f"  - 任务: {len(workflow.tasks)} 个")
            print("")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
