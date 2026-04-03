#!/usr/bin/env python3
"""
阿里云听愚 API 调用测试脚本（临时）

⚠️ 安全警告:
- 此脚本仅用于临时测试
- 不要将AccessKey保存到文件中
- 测试完成后立即轮换AccessKey

使用方式:
    export ALIYUN_ACCESS_KEY_ID="your_access_key_id"
    export ALIYUN_ACCESS_KEY_SECRET="your_access_key_secret"
    python scripts/test_tingwu_api.py
"""

import os
import sys


def test_tingwu_api():
    """测试听愚API调用"""

    # 从环境变量读取（不要硬编码！）
    access_key_id = os.environ.get("ALIYUN_ACCESS_KEY_ID")
    access_key_secret = os.environ.get("ALIYUN_ACCESS_KEY_SECRET")

    if not access_key_id or not access_key_secret:
        print("❌ 错误: 请先设置环境变量")
        print("\n请运行:")
        print("export ALIYUN_ACCESS_KEY_ID='your_access_key_id'")
        print("export ALIYUN_ACCESS_KEY_SECRET='your_access_key_secret'")
        return False

    print("⚠️  安全提醒:")
    print("  - 此脚本使用临时环境变量")
    print("  - AccessKey不会保存到文件")
    print("  - 终端关闭后自动清除")
    print()

    try:
        from alibabacloud_core.models import Config
        from alibabacloud_tingwu20230930.client import Client as TingwuClient

        print(f"📡 连接到阿里云听愚...")
        print(f"   AccessKey ID: {access_key_id[:15]}...{access_key_id[-4:]}")
        print(f"   区域: cn-hangzhou")
        print()

        # 创建客户端
        config = Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            region_id="cn-hangzhou",
        )

        client = TingwuClient(config)
        print("✅ 客户端创建成功")

        # 测试API: 获取文件夹265086的任务列表
        print()
        print(f"📂 获取文件夹 265086 的任务...")

        response = client.list_tasks(folder_id="265086", page_size=20, page_number=1)

        print(f"✅ API调用成功!")
        print(f"   状态码: {response.status_code}")

        # 解析响应
        if hasattr(response, "body") and response.body:
            body = response.body
            print(f"   账号ID: {body.account_id}")

            # 显示任务列表
            if hasattr(body, "data") and body.data:
                tasks = body.data
                print(f"   找到 {len(tasks)} 个任务:")
                print()

                for i, task in enumerate(tasks, 1):
                    print(f"   [{i}] {task.task_name}")
                    print(f"       ID: {task.task_id}")
                    print(f"       状态: {task.status}")
                    if hasattr(task, "create_time"):
                        print(f"       创建时间: {task.create_time}")
                    print()

        print("=" * 60)
        print("🎉 API测试成功!")
        print()
        print("📌 下一步:")
        print("   1. 确认可以访问您的听愚数据")
        print("   2. 使用导入脚本导入数据到灵知系统")
        print("   3. 完成后轮换AccessKey")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"❌ API调用失败: {e}")
        print()
        print("💡 可能的原因:")
        print("   1. AccessKey ID或Secret错误")
        print("   2. AccessKey已禁用或过期")
        print("   3. 没有听愚服务权限")
        print("   4. 网络连接问题")
        print()
        print("📖 查看完整文档:")
        print("   docs/AliYun_AccessKey_Creation_Guide.md")

        return False


if __name__ == "__main__":
    success = test_tingwu_api()
    sys.exit(0 if success else 1)
