#!/usr/bin/env python3
"""
Pre-commit hook: 检查115网盘访问速率限制合规性

检查代码中是否有违反115网盘访问速率限制的模式：
- API调用未添加延迟
- 并发数超过限制
- 批量操作未控制速率

用法:
    python scripts/hooks/check_115_rate_limit.py [file...]
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple

# 违规模式定义
VIOLATION_PATTERNS = {
    "no_delay_api_call": {
        "pattern": r"await\s+(api\.|client\.|request\.|http\.).*?(?!\s*sleep\s*\(|\s*asyncio\.sleep\s*\()",
        "description": "API调用未添加延迟",
        "severity": "warning",
    },
    "high_concurrency": {
        "pattern": r"(Semaphore\(|asyncio\.Semaphore\()\s*\(\s*([6-9]|[1-9]\d+))",
        "description": "并发数超过5",
        "severity": "error",
    },
    "fast_loop_calls": {
        "pattern": r"for\s+\w+\s+in\s+.*?:[^}]*?await\s+(api\.|request\.|http\.).*?(?!\s*sleep)",
        "description": "循环中API调用未延迟",
        "severity": "warning",
    },
    "rclone_high_transfers": {
        "pattern": r"--transfers\s*([5-9]|\d{2,})",
        "description": "rclone transfers超过4",
        "severity": "error",
    },
}

# 关键API端点/模块
API_KEYWORDS = [
    "100.66.1.8:2455",
    "/115/",
    "/115/国学大师",
    "openlist",
    "guoxue_content",
    "guji_download",
]


def check_file(file_path: str) -> List[Tuple[int, str, str, str]]:
    """检查单个文件"""
    violations = []

    try:
        content = Path(file_path).read_text(encoding="utf-8")
        lines = content.split("\n")

        # 检查是否包含115相关代码
        has_115_code = any(keyword in content for keyword in API_KEYWORDS)

        if not has_115_code:
            return violations

        # 逐行检查
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # 跳过注释和空行
            if not line_stripped or line_stripped.startswith("#"):
                continue

            # 检查各种违规模式
            for violation_type, config in VIOLATION_PATTERNS.items():
                if re.search(config["pattern"], line, re.IGNORECASE):
                    violations.append(
                        (line_num, file_path, config["description"], config["severity"])
                    )

        # AST检查 - 更精确的检测
        try:
            tree = ast.parse(content)
            checker = RateLimitChecker(file_path)
            checker.visit(tree)
            violations.extend(checker.violations)
        except SyntaxError:
            pass

    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)

    return violations


class RateLimitChecker(ast.NodeVisitor):
    """AST检查器 - 检测速率限制违规"""

    def __init__(self, filename):
        self.filename = filename
        self.violations = []
        self.in_async_for = False
        self.has_sleep_in_loop = False

    def visit_For(self, node):
        """检查for循环中的API调用"""
        old_in_async_for = self.in_async_for
        self.in_async_for = True
        self.has_sleep_in_loop = False

        self.generic_visit(node)

        # 如果在循环中但没sleep，且有API调用
        if self.in_async_for and not self.has_sleep_in_loop:
            # 检查循环体是否有await调用
            for child in ast.walk(node):
                if isinstance(child, ast.Await):
                    self.violations.append(
                        (node.lineno, self.filename, "循环中的API调用可能未添加延迟", "warning")
                    )
                    break

        self.in_async_for = old_in_async_for

    def visit_Call(self, node):
        """检查函数调用"""
        # 检查sleep调用
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("sleep", "usleep"):
                self.has_sleep_in_loop = True

        # 检查asyncio.Semaphore参数
        if isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "Semaphore"
                and node.func.value.attr == "asyncio"
            ):
                if node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant):
                        if arg.value > 5:
                            self.violations.append(
                                (
                                    node.lineno,
                                    self.filename,
                                    f"asyncio.Semaphore({arg.value}) 超过限制(5)",
                                    "error",
                                )
                            )

        self.generic_visit(node)

    def visit_With(self, node):
        """检查with语句中的资源管理"""
        self.generic_visit(node)


def main():
    if len(sys.argv) < 2:
        print("Usage: check_115_rate_limit.py <file>...")
        sys.exit(1)

    all_violations = []

    for file_path in sys.argv[1:]:
        violations = check_file(file_path)
        all_violations.extend(violations)

    if not all_violations:
        print("✅ 115网盘访问速率限制检查通过")
        return 0

    # 按严重程度分类
    errors = [v for v in all_violations if v[3] == "error"]
    warnings = [v for v in all_violations if v[3] == "warning"]

    if errors:
        print("\n❌ 发现错误:")
        for line_num, file_path, desc, _ in errors:
            print(f"   {file_path}:{line_num} - {desc}")

    if warnings:
        print("\n⚠️  警告:")
        for line_num, file_path, desc, _ in warnings:
            print(f"   {file_path}:{line_num} - {desc}")

    print(f"\n总计: {len(errors)} 错误, {len(warnings)} 警告")

    # 有错误则返回失败
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
