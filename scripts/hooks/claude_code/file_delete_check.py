#!/usr/bin/env python3
"""
文件删除检查Hook
检查危险的文件删除操作
"""
import sys
import os
import re


def print_header():
    """打印Hook头部信息"""
    print("\n" + "="*70)
    print("🔒 文件删除操作检查Hook")
    print("="*70 + "\n")


def analyze_risk(command: str) -> dict:
    """
    分析删除命令的风险

    Returns:
        dict: {risk_level, risk_score, warnings}
    """
    risk_score = 0
    warnings = []

    # 检查是否递归删除
    if "-rf" in command or "-r" in command:
        risk_score += 5
        warnings.append("⚠️  使用递归删除 (-rf)")

    # 检查是否删除重要目录
    important_patterns = [
        (r"rm\s+-rf\s+data/", "删除 data/ 目录"),
        (r"rm\s+-rf\s+backend/", "删除 backend/ 目录"),
        (r"rm\s+-rf\s+.*\.db", "删除数据库文件"),
        (r"rm\s+-rf\s+\*", "删除所有文件")
    ]

    for pattern, description in important_patterns:
        if re.search(pattern, command):
            risk_score += 8
            warnings.append(f"🚨 {description}")

    # 检查是否强制删除
    if "-f" in command:
        risk_score += 2
        warnings.append("⚠️  使用强制删除 (-f)")

    # 确定风险等级
    if risk_score >= 10:
        risk_level = "CRITICAL"
    elif risk_score >= 7:
        risk_level = "HIGH"
    elif risk_score >= 4:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "warnings": warnings
    }


def print_help():
    """打印帮助信息"""
    print("\n💡 建议的安全做法:")
    print("1. 先列出要删除的文件:")
    print("   ls -la <path>")
    print("")
    print("2. 确认后，逐个删除或使用更安全的命令:")
    print("   rm <单个文件>")
    print("   或")
    print("   find <path> -name '<pattern>' -delete")
    print("")
    print("3. 如果确实需要批量删除，请:")
    print("   a) 使用 AskUserQuestion 向用户确认")
    print("   b) 先生成预览脚本供用户检查")
    print("   c) 用户确认后再执行")
    print("")
    print("4. 对于重要操作，考虑创建备份:")
    print("   cp -r <source> <backup>")
    print("="*70 + "\n")


def main():
    """主函数"""
    # 从环境变量或命令行参数获取命令
    # 这里简化处理，直接检查

    print_header()

    print("⚠️  检测到文件删除操作")
    print("")
    print("🔍 风险评估:")

    # 获取命令（这里简化处理）
    command = os.environ.get("BASH_COMMAND", "")

    # 如果没有获取到命令，打印通用警告
    if not command:
        print("   ⚠️  无法获取具体命令，但检测到删除操作")
        print_help()
        sys.exit(1)

    # 分析风险
    risk_info = analyze_risk(command)

    print(f"   风险等级: {risk_info['risk_level']}")
    print(f"   风险评分: {risk_info['risk_score']}/10")

    if risk_info['warnings']:
        print("\n   警告:")
        for warning in risk_info['warnings']:
            print(f"   {warning}")

    print("")

    # 根据风险等级决定是否阻止
    if risk_info['risk_score'] >= 7:
        print("🚫 高风险操作，已被阻止！")
        print_help()
        sys.exit(1)
    elif risk_info['risk_score'] >= 4:
        print("⚠️  中等风险操作，请谨慎操作")
        print_help()
        # 中等风险不阻止，只是警告
        sys.exit(0)
    else:
        print("✅ 低风险操作，可以继续")
        sys.exit(0)


if __name__ == "__main__":
    main()
