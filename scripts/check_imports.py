#!/usr/bin/env python3
"""检查Python文件的导入路径是否符合规范

用法:
    python scripts/check_imports.py backend/api/v1/analytics.py
    python scripts/check_imports.py --all backend/
"""
import ast
import sys
from pathlib import Path
from typing import Any, Dict, List


def check_imports(file_path: str) -> List[Dict[str, Any]]:
    """检查单个文件的导入路径

    Args:
        file_path: Python文件路径

    Returns:
        问题列表，每个问题包含line, module, message
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        return [{"line": 0, "module": "N/A", "message": f"文件不存在: {file_path}"}]

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [{"line": e.lineno or 0, "module": "N/A", "message": f"语法错误: {e.msg}"}]

    issues = []

    # backend内部模块列表
    backend_modules = (
        "api.",
        "services.",
        "models.",
        "core.",
        "auth.",
        "middleware.",
        "cache.",
        "domains.",
        "gateway.",
        "monitoring.",
        "common.",
        "config.",
        "utils.",
    )

    for node in ast.walk(tree):
        # 检查 import 语句
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                # 检查是否是backend内部的模块
                if module.startswith(backend_modules):
                    if not module.startswith("backend."):
                        issues.append(
                            {
                                "line": node.lineno,
                                "module": module,
                                "message": f'应该使用 "from backend.{module} import xxx"',
                            }
                        )

        # 检查 from ... import 语句
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            if module and module.startswith(backend_modules):
                if not module.startswith("backend."):
                    issues.append(
                        {
                            "line": node.lineno,
                            "module": module,
                            "message": f'应该使用 "from backend.{module} import xxx"',
                        }
                    )

    return issues


def check_directory(directory: str) -> Dict[str, List[Dict[str, Any]]]:
    """检查目录下所有Python文件

    Args:
        directory: 目录路径

    Returns:
        {file_path: issues_list}
    """
    results = {}
    path = Path(directory)

    for py_file in path.rglob("*.py"):
        # 跳过__pycache__和虚拟环境
        if "__pycache__" in str(py_file) or "venv" in str(py_file):
            continue

        file_path = str(py_file)
        issues = check_imports(file_path)

        if issues:
            results[file_path] = issues

    return results


def print_results(results: Dict[str, List[Dict[str, Any]]]):
    """打印检查结果"""
    total_files = len(results)
    total_issues = sum(len(issues) for issues in results.values())

    if total_issues == 0:
        print("✅ 所有文件的导入路径都符合规范！")
        return

    print(f"❌ 发现 {total_files} 个文件存在导入路径问题，共 {total_issues} 个问题：\n")

    for file_path, issues in results.items():
        print(f"📄 {file_path}:")
        for issue in issues:
            print(f"  Line {issue['line']}: {issue['module']}")
            print(f"    {issue['message']}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python scripts/check_imports.py <file.py>")
        print("  python scripts/check_imports.py --all <directory>")
        sys.exit(1)

    if sys.argv[1] == "--all":
        if len(sys.argv) < 3:
            print("错误: --all 需要指定目录")
            sys.exit(1)

        directory = sys.argv[2]
        results = check_directory(directory)
        print_results(results)
        sys.exit(1 if results else 0)

    else:
        file_path = sys.argv[1]
        issues = check_imports(file_path)

        if issues:
            print(f"❌ {file_path}: 发现 {len(issues)} 个导入路径问题\n")
            for issue in issues:
                print(f"  Line {issue['line']}: {issue['module']}")
                print(f"    {issue['message']}")
            sys.exit(1)
        else:
            print(f"✅ {file_path}: 导入路径符合规范")
            sys.exit(0)
