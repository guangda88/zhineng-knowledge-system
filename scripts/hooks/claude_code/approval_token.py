#!/usr/bin/env python3
"""
批准令牌管理
用于Hooks的批准机制
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Tuple


class ApprovalToken:
    """批准令牌管理"""

    TOKEN_FILE = "/tmp/claude_approval.json"

    @classmethod
    def create(cls, operation: str, duration_minutes: int = 30) -> Dict:
        """
        创建批准令牌

        Args:
            operation: 操作类型 (如 "db_write", "file_delete")
            duration_minutes: 令牌有效期（分钟），默认30分钟

        Returns:
            令牌字典
        """
        token = {
            "operation": operation,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
            "approved": True
        }

        # 确保目录存在
        os.makedirs(os.path.dirname(cls.TOKEN_FILE), exist_ok=True)

        with open(cls.TOKEN_FILE, 'w') as f:
            json.dump(token, f, indent=2)

        return token

    @classmethod
    def validate(cls, operation: str) -> Tuple[bool, str]:
        """
        验证批准令牌

        Args:
            operation: 操作类型

        Returns:
            (是否有效, 消息)
        """
        if not os.path.exists(cls.TOKEN_FILE):
            return False, "❌ 未找到批准文件"

        try:
            with open(cls.TOKEN_FILE) as f:
                token = json.load(f)
        except json.JSONDecodeError:
            return False, "❌ 批准文件格式错误"

        # 检查操作类型
        if token.get("operation") != operation:
            return False, f"❌ 令牌类型不匹配: 需要 '{operation}', 但令牌是 '{token.get('operation')}'"

        # 检查是否批准
        if not token.get("approved", False):
            return False, "❌ 令牌未批准"

        # 检查是否过期
        try:
            expires_at = datetime.fromisoformat(token["expires_at"])
            if datetime.now() > expires_at:
                return False, f"❌ 令牌已过期: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}"
        except (KeyError, ValueError):
            return False, "❌ 令牌过期时间格式错误"

        return True, f"✅ 批准有效 (过期时间: {expires_at.strftime('%Y-%m-%d %H:%M:%S')})"

    @classmethod
    def clear(cls):
        """清除批准令牌"""
        if os.path.exists(cls.TOKEN_FILE):
            os.remove(cls.TOKEN_FILE)

    @classmethod
    def get_token_info(cls) -> Dict:
        """获取令牌信息"""
        if not os.path.exists(cls.TOKEN_FILE):
            return None

        try:
            with open(cls.TOKEN_FILE) as f:
                return json.load(f)
        except:
            return None


# 便捷函数
def create_approval_token(operation: str, duration_minutes: int = 30) -> Dict:
    """创建批准令牌"""
    return ApprovalToken.create(operation, duration_minutes)


def validate_approval_token(operation: str) -> Tuple[bool, str]:
    """验证批准令牌"""
    return ApprovalToken.validate(operation)


def clear_approval_token():
    """清除批准令牌"""
    ApprovalToken.clear()


if __name__ == "__main__":
    # 命令行工具
    import argparse

    parser = argparse.ArgumentParser(description="批准令牌管理工具")
    parser.add_argument("action", choices=["create", "validate", "clear", "info"],
                       help="操作: create=创建, validate=验证, clear=清除, info=查看信息")
    parser.add_argument("--operation", default="db_write",
                       help="操作类型 (默认: db_write)")
    parser.add_argument("--duration", type=int, default=30,
                       help="有效期（分钟，默认: 30）")

    args = parser.parse_args()

    if args.action == "create":
        token = create_approval_token(args.operation, args.duration)
        print(f"✅ 批准令牌已创建")
        print(f"   操作类型: {token['operation']}")
        print(f"   过期时间: {token['expires_at']}")

    elif args.action == "validate":
        valid, message = validate_approval_token(args.operation)
        print(message)
        exit(0 if valid else 1)

    elif args.action == "clear":
        clear_approval_token()
        print("✅ 批准令牌已清除")

    elif args.action == "info":
        token = ApprovalToken.get_token_info()
        if token:
            print("📋 批准令牌信息:")
            print(f"   操作类型: {token.get('operation')}")
            print(f"   创建时间: {token.get('created_at')}")
            print(f"   过期时间: {token.get('expires_at')}")
            print(f"   状态: {'✅ 已批准' if token.get('approved') else '❌ 未批准'}")
        else:
            print("❌ 未找到批准令牌")
