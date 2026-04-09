#!/usr/bin/env python3
"""
数据库写操作检查Hook
检查数据库破坏性操作是否已获批准
"""
import os
import sys

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from approval_token import ApprovalToken
except ImportError:
    # 如果导入失败，使用内嵌版本
    import json
    from datetime import datetime

    class ApprovalToken:
        TOKEN_FILE = "/tmp/claude_approval.json"

        @classmethod
        def validate(cls, operation: str):
            if not os.path.exists(cls.TOKEN_FILE):
                return False, "❌ 未找到批准文件"

            try:
                with open(cls.TOKEN_FILE) as f:
                    token = json.load(f)

                if token.get("operation") != operation:
                    return False, "❌ 令牌类型不匹配"

                if not token.get("approved", False):
                    return False, "❌ 令牌未批准"

                expires_at = datetime.fromisoformat(token["expires_at"])
                if datetime.now() > expires_at:
                    return False, "❌ 令牌已过期"

                return True, "✅ 批准有效"

            except Exception as e:
                return False, f"❌ 令牌验证失败: {e}"


def print_header():
    """打印Hook头部信息"""
    print("\n" + "=" * 70)
    print("🔒 数据库写操作检查Hook")
    print("=" * 70 + "\n")


def print_help():
    """打印帮助信息"""
    print("\n💡 如何获得批准:")
    print("1. 使用 AskUserQuestion 向用户说明操作方案和风险")
    print("2. 获得用户批准后，运行以下命令创建批准令牌:")
    print(
        "   python3 /home/ai/zhineng-knowledge-system/scripts/hooks/claude_code/approval_token.py create --operation db_write"
    )
    print("")
    print("   或使用 Python 代码:")
    print("   from scripts.hooks.claude_code.approval_token import create_approval_token")
    print('   create_approval_token("db_write")')
    print("")
    print("3. 然后重新执行您的操作")
    print("")
    print("⚠️  注意: 批准令牌默认有效期为30分钟")
    print("=" * 70 + "\n")


def main():
    """主函数"""
    print_header()

    # 检查批准令牌
    approved, message = ApprovalToken.validate("db_write")

    if not approved:
        print("❌ 数据库写操作检查失败\n")
        print(f"原因: {message}\n")
        print("⚠️  数据库写操作需要用户批准！")
        print_help()
        sys.exit(1)

    print(f"{message}")
    print("✅ 数据库写操作已获批准，可以继续执行\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
