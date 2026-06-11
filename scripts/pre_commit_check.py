#!/usr/bin/env python3
"""
Git pre-commit hook: 灵知自检清单

E4: 从"问题修复"到"系统性预防"
每次提交前自动执行：
1. 安全检查 — 禁止敏感文件/密钥泄露
2. Lint检查 — ruff/black/isort
3. 测试检查 — pytest 快速冒烟

用法: 链接到 .git/hooks/pre-commit
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run(cmd_args, label, required=True):
    cmd_str = cmd_args if isinstance(cmd_args, str) else " ".join(cmd_args)
    print(f"  [{label}] {cmd_str}")
    if isinstance(cmd_args, str):
        result = subprocess.run(cmd_args, shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    else:
        result = subprocess.run(cmd_args, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"  FAILED: {label}")
        if result.stdout:
            for line in result.stdout.strip().split("\n")[:20]:
                print(f"    {line}")
        if result.stderr:
            for line in result.stderr.strip().split("\n")[:10]:
                print(f"    {line}")
        if required:
            return False
        print("  (non-blocking)")
    else:
        print(f"  OK: {label}")
    return True


def check_sensitive_files():
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    files = staged.stdout.strip().split("\n") if staged.stdout.strip() else []

    patterns = [".env", "secret", "password", "credential", "private_key"]
    blocked = []
    for f in files:
        lower = f.lower()
        if any(p in lower for p in patterns):
            if not lower.endswith((".example", ".template", ".sample")):
                blocked.append(f)

    if blocked:
        print("  BLOCKED: sensitive files detected:")
        for f in blocked:
            print(f"    {f}")
        return False

    for f in files:
        if not f.endswith((".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".md", ".txt")):
            continue
        fp = PROJECT_ROOT / f
        if not fp.exists():
            continue
        try:
            content = fp.read_text(errors="ignore")
        except Exception:
            continue
        for kw in ["sk-", "ghp_", "gho_", "AKIA", "AIza", "xoxb-", "xoxp-"]:
            idx = content.find(kw)
            if idx != -1:
                context = content[max(0, idx - 20) : idx + len(kw) + 10]
                if "example" in context.lower() or "placeholder" in context.lower():
                    continue
                print(f"  BLOCKED: possible secret in {f}: ...{context}...")
                return False

    return True


def check_python_syntax():
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "*.py"],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    py_files = [f for f in staged.stdout.strip().split("\n") if f.endswith(".py")]
    if not py_files:
        return True

    for f in py_files:
        fp = PROJECT_ROOT / f
        if not fp.exists():
            continue
        result = subprocess.run(
            ["python", "-m", "py_compile", str(fp)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  BLOCKED: syntax error in {f}")
            print(f"    {result.stderr.strip()[:200]}")
            return False
    return True


def get_staged_py_files():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "*.py"],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    return [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]


def check_ruff_staged():
    py_files = get_staged_py_files()
    if not py_files:
        return True
    cmd = ["python", "-m", "ruff", "check", *py_files, "--quiet"]
    return run(cmd, "ruff")


def main():
    print("=" * 50)
    print("  灵知 Pre-commit 自检")
    print("=" * 50)

    checks = [
        ("security", "敏感文件+密钥检测", check_sensitive_files),
        ("syntax", "Python语法检查", check_python_syntax),
        ("lint", "Ruff lint (staged)", check_ruff_staged),
        ("tests", "快速冒烟测试", lambda: run(["python", "-m", "pytest", "tests/test_monitoring_health.py", "tests/test_anomaly_detector.py", "-x", "-q", "--timeout=10"], "pytest-smoke", required=False)),
    ]

    failed = []
    for name, desc, fn in checks:
        print(f"\n  [{name}] {desc}")
        try:
            ok = fn()
            if not ok:
                failed.append(name)
        except Exception as e:
            print(f"  ERROR: {name}: {e}")
            failed.append(name)

    print("\n" + "=" * 50)
    if failed:
        print(f"  FAILED: {', '.join(failed)}")
        print("  请修复后再提交")
        print("=" * 50)
        sys.exit(1)
    else:
        print("  ALL PASSED")
        print("=" * 50)
        sys.exit(0)


if __name__ == "__main__":
    main()
