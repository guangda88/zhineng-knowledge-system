#!/usr/bin/env python3
"""LingMinOpt自动优化状态监控"""
import json
import subprocess
from datetime import datetime
from pathlib import Path


def show_optimization_status():
    """显示优化状态"""

    print("\n" + "=" * 70)
    print("📊 LingMinOpt自动优化状态监控")
    print("=" * 70)
    print()

    # 1. 检查服务状态
    print("1️⃣  服务状态")
    print("-" * 70)

    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )

        service_process = None
        for line in result.stdout.split('\n'):
            if 'auto_optimization_service' in line and 'grep' not in line:
                service_process = line
                break

        if service_process:
            parts = service_process.split()
            pid = parts[1]
            cpu = parts[2]
            mem = parts[3]
            print(f"  ✅ 服务运行中")
            print(f"  📌 PID: {pid}")
            print(f"  💻 CPU: {cpu}%")
            print(f"  🧠 内存: {mem}")
            print(f"  ⏰ 启动时间: {parts[8]} {parts[9]}")
        else:
            print("  ❌ 服务未运行")

    except Exception as e:
        print(f"  ❌ 无法检查服务状态: {e}")

    print()

    # 2. 查看优化计划
    print("2️⃣ 优化计划")
    print("-" * 70)

    plan_file = Path("config/lingminopt_plan.json")
    if plan_file.exists():
        with open(plan_file, 'r') as f:
            plan_data = json.load(f)

        print(f"  生成时间: {plan_data['generated_at']}")
        print(f"  预计时长: {plan_data['plan']['estimated_duration']}")
        print(f"  预期影响: {plan_data['plan']['expected_impact']}")
        print(f"  阶段数: {len(plan_data['plan']['phases'])}")

        print()
        print("  优化机会:")

        for i, opp in enumerate(plan_data['opportunities'], 1):
            print(f"  {i}. [{opp['priority'].upper()}] {opp['title']}")
            print(f"     当前: {opp['current_value']} → 目标: {opp['target_value']}")
            print(f"     预期改进: {opp['expected_improvement']}, 工作量: {opp['effort']}")
            print()

    else:
        print("  ⚠️  优化计划文件不存在")

    print()

    # 3. 查看最近日志
    print("3️⃣ 最近日志")
    print("-" * 70)

    log_file = Path("/tmp/lingminopt_auto.log")
    if log_file.exists():
        # 获取最后30行
        result = subprocess.run(
            ["tail", "-30", str(log_file)],
            capture_output=True,
            text=True
        )

        print("  📋 最近30行日志:")
        print()

        for line in result.stdout.split('\n'):
            if line.strip():
                print(f"  {line}")

    else:
        print("  ⚠️  日志文件不存在")

    print()

    # 4. 显示控制命令
    print("4️⃣ 控制命令")
    print("-" * 70)

    print(f"  查看实时日志:")
    print(f"    tail -f /tmp/lingminopt_auto.log")
    print()
    print(f"  停止服务:")
    pid = subprocess.run(
        ["pgrep", "-f", "auto_optimization_service"],
        capture_output=True,
        text=True
    ).stdout.strip()

    if pid:
        print(f"    kill {pid}")
    else:
        print(f"    kill $(pgrep -f 'auto_optimization_service' | awk '{{print $1}}')")
    print()
    print(f"  重启服务:")
    print(f"    nohup python scripts/auto_optimization_service.py --interval 60 > /tmp/lingminopt_auto.log 2>&1 &")
    print()

    print("=" * 70)
    print()


def show_realtime_dashboard():
    """显示实时仪表板"""
    import time

    try:
        count = 0
        while count < 10:  # 显示10次后退出
            count += 1

            # 清屏
            print("\033[2J\033[H", end="")

            # 显示标题
            print("\n" + "=" * 70)
            print(f"📊 LingMinOpt实时仪表板 - {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 70)
            print()

            # 显示服务状态
            print("🔄 服务状态:")
            result = subprocess.run(
                ["pgrep", "-f", "auto_optimization_service"],
                capture_output=True,
                text=True
            )

            if result.stdout.strip():
                print("  ✅ 运行中")
            else:
                print("  ❌ 未运行")
            print()

            # 显示最近日志
            print("📋 最近日志:")
            log_result = subprocess.run(
                ["tail", "-10", "/tmp/lingminopt_auto.log"],
                capture_output=True,
                text=True
            )

            for line in log_result.stdout.split('\n'):
                if line.strip():
                    print(f"  {line}")

            print()
            print("⏳ 10秒后更新... (按 Ctrl+C 停止)")
            print("=" * 70)

            time.sleep(10)

    except KeyboardInterrupt:
        print("\n\n👋 仪表板已停止")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="LingMinOpt状态监控",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 显示当前状态
  python scripts/show_optimization_status.py

  # 显示实时仪表板
  python scripts/show_optimization_status.py --watch
        """
    )

    parser.add_argument(
        "--watch",
        "-w",
        action="store_true",
        help="实时监控模式（每10秒更新）"
    )

    args = parser.parse_args()

    if args.watch:
        show_realtime_dashboard()
    else:
        show_optimization_status()


if __name__ == "__main__":
    main()
