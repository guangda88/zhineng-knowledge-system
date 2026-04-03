#!/usr/bin/env python3
"""
阿里云听悟 AccessKey 测试脚本

运行方式:
    export ALIYUN_ACCESS_KEY_ID="your_access_key_id"
    export ALIYUN_ACCESS_KEY_SECRET="your_access_key_secret"
    python scripts/test_tingwu_access_key.py
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_access_key():
    """测试AccessKey是否可用"""

    print("=" * 60)
    print("阿里云听悟 AccessKey 测试")
    print("=" * 60)

    # 1. 检查环境变量
    print("\n[1/4] 检查环境变量...")
    access_key_id = os.environ.get("ALIYUN_ACCESS_KEY_ID")
    access_key_secret = os.environ.get("ALIYUN_ACCESS_KEY_SECRET")

    if not access_key_id:
        print("❌ 错误: 未设置环境变量 ALIYUN_ACCESS_KEY_ID")
        print("   请运行: export ALIYUN_ACCESS_KEY_ID='your_key_id'")
        return False

    if not access_key_secret:
        print("❌ 错误: 未设置环境变量 ALIYUN_ACCESS_KEY_SECRET")
        print("   请运行: export ALIYUN_ACCESS_KEY_SECRET='your_key_secret'")
        return False

    print(f"✅ AccessKey ID: {access_key_id[:10]}...{access_key_id[-4:]}")
    print(f"✅ AccessKey Secret: {'*' * 8}")

    # 2. 尝试导入SDK
    print("\n[2/4] 检查SDK...")
    try:
        from alibabacloud_core.models import Config
        from alibabacloud_tingwu20230930.client import Client as TingwuClient

        print("✅ SDK已安装")
    except ImportError as e:
        print(f"❌ 错误: SDK未安装")
        print("   请运行: pip install alibabacloud-tingwu20230930")
        return False

    # 3. 创建客户端
    print("\n[3/4] 创建听悟客户端...")
    try:
        config = Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            region_id="cn-hangzhou",  # 听悟服务在杭州区域
        )

        client = TingwuClient(config)
        print("✅ 客户端创建成功")
    except Exception as e:
        print(f"❌ 错误: 客户端创建失败")
        print(f"   详情: {e}")
        return False

    # 4. 测试API调用
    print("\n[4/4] 测试API调用...")
    try:
        # 调用ListTasks API
        response = client.list_tasks(page_size=1)  # 只查询1条，快速测试

        print("✅ API调用成功！")
        print(f"✅ 状态码: {response.status_code}")

        # 显示响应信息
        if hasattr(response, "body") and response.body:
            body = response.body
            if hasattr(body, "account_id"):
                print(f"✅ 账号ID: {body.account_id}")

        print("\n" + "=" * 60)
        print("🎉 AccessKey验证成功！可以开始使用听悟API了")
        print("=" * 60)

        # 提示下一步
        print("\n📌 下一步:")
        print("   1. 运行导入脚本: python scripts/import_from_tingwu.py")
        print("   2. 或调用听悟API获取数据")

        return True

    except Exception as e:
        print(f"❌ 错误: API调用失败")
        print(f"   详情: {e}")

        # 分析错误类型
        error_str = str(e).lower()
        if "invalid" in error_str or "access" in error_str:
            print("\n💡 提示: AccessKey可能无效或已过期")
            print("   请检查:")
            print("   - AccessKey ID是否正确")
            print("   - AccessKey Secret是否正确")
            print("   - 是否已禁用该AccessKey")
        elif "permission" in error_str or "authorized" in error_str:
            print("\n💡 提示: 权限不足")
            print("   请检查:")
            print("   - RAM用户是否有听悟服务权限")
            print("   - 是否已添加 AliyunTingwuFullAccess 策略")

        return False


if __name__ == "__main__":
    success = test_access_key()
    sys.exit(0 if success else 1)
