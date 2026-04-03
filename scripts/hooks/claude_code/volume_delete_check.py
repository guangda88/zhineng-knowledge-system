#!/usr/bin/env python3
"""
Docker Volume删除检查Hook
检查Docker Volume删除操作
"""
import subprocess
import sys


def print_header():
    """打印Hook头部信息"""
    print("\n" + "=" * 70)
    print("🔒 Docker Volume删除检查Hook")
    print("=" * 70 + "\n")


def get_volumes_info():
    """获取Volume信息"""
    try:
        result = subprocess.run(
            ["docker", "volume", "ls"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            return result.stdout
        return None
    except:
        return None


def print_warning(volumes_info: str):
    """打印警告信息"""
    print("🚨 危险操作警告！\n")
    print("您正在执行删除Docker Volumes的操作！")
    print("这可能导致所有数据永久丢失！\n")

    if volumes_info:
        print("当前Volumes:")
        print(volumes_info)
        print("")

    print("💡 在继续之前，请确认:")
    print("1. ✅ 您已经备份了所有重要数据")
    print("2. ✅ 您理解这将删除所有Volumes")
    print("3. ✅ 您确实需要执行此操作")
    print("")
    print("⚠️  如果您只是想重启服务，请使用:")
    print("   docker-compose down")
    print("   docker-compose up -d")
    print("")
    print("📦 如果您想清理数据，请先备份:")
    print("   docker volume ls")
    print("   docker volume inspect <volume>")
    print("=" * 70 + "\n")


def main():
    """主函数"""
    print_header()

    # 获取Volume信息
    volumes_info = get_volumes_info()

    print("⚠️  检测到Docker Volume删除操作")
    print("")

    print_warning(volumes_info)

    print("🚫 此操作已被阻止，需要明确确认")
    print("")
    print("💡 如果您确实需要删除Volumes，请:")
    print("1. 先备份所有重要数据")
    print("2. 使用 AskUserQuestion 向用户确认")
    print("3. 然后手动执行（不通过Hook）:")
    print("   docker volume rm <volume_name>")
    print("")

    sys.exit(1)


if __name__ == "__main__":
    main()
