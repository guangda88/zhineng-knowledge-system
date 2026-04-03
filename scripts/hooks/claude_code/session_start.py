#!/usr/bin/env python3
"""
会话开始时提醒Hook
在每次Claude Code会话开始时提醒阅读规则
"""
import os
import sys


def print_header():
    """打印头部信息"""
    print("\n" + "=" * 70)
    print("📋 智能知识系统 - 开发规则提醒")
    print("=" * 70 + "\n")


def print_reminder():
    """打印规则提醒"""
    print("⚠️  在执行任何操作前，请确保:\n")

    checklist_items = [
        ("已阅读 CLAUDE.md", "了解AI开发工作流程"),
        ("已阅读 DEVELOPMENT_RULES.md", "了解项目开发规则"),
        ("已完成开发前检查清单", "确认需求、原则、影响"),
        ("涉及数据库写操作时已获批准", "防止数据丢失"),
        ("涉及文件删除时已生成预览", "防止误删重要文件"),
        ("理解当前系统状态", "是否有紧急问题需要优先处理"),
    ]

    for i, (item, description) in enumerate(checklist_items, 1):
        print(f"{i}. ✅ {item}")
        print(f"   → {description}")
        print("")

    print("🔒 关键资源保护:")
    print("   - data.db (310MB) - 教材数据库")
    print("   - textbooks.db - 教材元数据")
    print("   - PostgreSQL volumes - 生产数据")
    print("")

    print("🚫 禁止事项:")
    print("   - 未经批准的数据库写操作")
    print("   - 未经确认的文件删除")
    print("   - 忽视紧急问题")
    print("   - 在main分支直接开发")
    print("")

    print("📖 详细规则请参阅:")
    print("   - CLAUDE.md")
    print("   - DEVELOPMENT_RULES.md")
    print("   - HOOKS_IMPLEMENTATION_GUIDE.md")
    print("")

    print("=" * 70 + "\n")


def main():
    """主函数"""
    print_header()
    print_reminder()
    sys.exit(0)


if __name__ == "__main__":
    main()
