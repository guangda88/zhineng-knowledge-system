#!/usr/bin/env python3
"""检查导入脚本是否使用 ImportManager 防止并发锁死

用法:
    python scripts/check_import_safety.py
    python scripts/check_import_safety.py scripts/import_guji_data.py
"""

import ast
import sys
from pathlib import Path

# 必须使用 ImportManager 的脚本模式
IMPORT_SCRIPT_PATTERNS = [
    "import_",  # import_*.py
    "_import.py",  # *_import.py
]

# 允许的例外（这些脚本不需要 ImportManager）
ALLOWED_EXCEPTIONS = {
    "import_manager.py",
    "import_guard.py",
    "check_imports.py",
    "check_import_safety.py",
}


def check_import_manager_usage(file_path: Path) -> tuple[bool, str]:
    """检查文件是否正确使用 ImportManager"""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))

        # 检查是否有 ImportManager 的导入
        has_import_manager_import = False
        has_import_guard_import = False
        has_with_import_manager = False
        has_import_guard_call = False

        for node in ast.walk(tree):
            # 检查导入
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "ImportManager" in alias.name or "import_manager" in alias.name:
                        has_import_manager_import = True
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    "ImportManager" in str(node.module) or "import_manager" in str(node.module)
                ):
                    has_import_manager_import = True
                if node.module and "import_guard" in str(node.module):
                    has_import_guard_import = True

            # 检查使用
            if isinstance(node, ast.With):
                for item in node.items:
                    if isinstance(item.context_expr, ast.Call):
                        call = item.context_expr
                        if isinstance(call.func, ast.Name):
                            if call.func.id == "ImportManager":
                                has_with_import_manager = True
                        elif isinstance(call.func, ast.Attribute):
                            if call.func.attr == "ImportManager":
                                has_with_import_manager = True

            # 检查 import_guard 调用
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id == "run_import":
                        has_import_guard_call = True

        # 判断是否安全
        is_safe = (
            has_with_import_manager
            or has_import_guard_call
            or has_import_manager_import
            or has_import_guard_import
        )

        if is_safe:
            return True, "✅ 使用 ImportManager 或 import_guard"
        else:
            return False, "❌ 未使用 ImportManager - 可能导致并发锁死"

    except SyntaxError as e:
        return False, f"⚠️  语法错误: {e}"
    except Exception as e:
        return False, f"⚠️  检查失败: {e}"


def is_import_script(file_path: Path) -> bool:
    """判断是否是导入脚本"""
    filename = file_path.name

    # 检查例外
    if filename in ALLOWED_EXCEPTIONS:
        return False

    # 检查模式
    for pattern in IMPORT_SCRIPT_PATTERNS:
        if pattern.replace("_", "") in filename.lower() or pattern in filename:
            return True

    return False


def check_directory(directory: Path = None) -> dict[str, tuple[bool, str]]:
    """检查目录中的所有导入脚本"""
    if directory is None:
        directory = Path(__file__).parent.parent / "scripts"

    results = {}

    for file_path in directory.rglob("*.py"):
        if is_import_script(file_path):
            is_safe, message = check_import_manager_usage(file_path)
            results[str(file_path.relative_to(directory.parent))] = (is_safe, message)

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="检查导入脚本安全性")
    parser.add_argument("files", nargs="*", help="要检查的文件")
    parser.add_argument("--dir", help="检查目录")
    parser.add_argument("--strict", action="store_true", help="严格模式 - 不安全则返回非0")

    args = parser.parse_args()

    if args.files:
        # 检查指定文件
        results = {}
        for file_path in args.files:
            path = Path(file_path)
            if path.exists():
                is_safe, message = check_import_manager_usage(path)
                results[file_path] = (is_safe, message)
    elif args.dir:
        # 检查目录
        results = check_directory(Path(args.dir))
    else:
        # 检查默认目录
        results = check_directory()

    # 输出结果
    has_unsafe = False
    print("\n🔍 导入脚本安全检查:")
    print("=" * 60)

    if not results:
        print("  未找到需要检查的导入脚本")
        return 0

    for file_path, (is_safe, message) in sorted(results.items()):
        status_icon = "✅" if is_safe else "❌"
        print(f"  {status_icon} {file_path}")
        print(f"     {message}")

        if not is_safe:
            has_unsafe = True
            print("     建议: 使用 'from backend.services.import_manager import ImportManager'")

    if has_unsafe:
        print("\n⚠️  发现不安全的导入脚本!")
        print("   请使用 ImportManager 防止并发锁死")
        print("   参考: docs/DATABASE_LOCK_PREVENTION.md")
        return 1 if args.strict else 0
    else:
        print("\n✅ 所有导入脚本安全检查通过")
        return 0


if __name__ == "__main__":
    sys.exit(main())
