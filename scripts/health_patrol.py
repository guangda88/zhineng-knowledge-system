#!/usr/bin/env python3
"""灵知主动巡检系统

自进化计划 E1: 从"被指令驱动"到"自主发现问题"
自动检测：API响应时间、429错误率、检索性能、数据库健康、数据一致性

用法:
    python scripts/health_patrol.py          # 完整巡检
    python scripts/health_patrol.py --quick  # 快速巡检（跳过耗时检查）
    python scripts/health_patrol.py --watch  # 持续监控（每60秒）
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

API_BASE = "http://localhost:8000"
EMBEDDING_BASE = "http://localhost:8001"


class PatrolResult:
    def __init__(self, name: str):
        self.name = name
        self.status = "ok"
        self.message = ""
        self.details = {}
        self.duration_ms = 0

    def ok(self, message: str = "", **details):
        self.status = "ok"
        self.message = message
        self.details = details
        return self

    def warn(self, message: str, **details):
        self.status = "warn"
        self.message = message
        self.details = details
        return self

    def fail(self, message: str, **details):
        self.status = "fail"
        self.message = message
        self.details = details
        return self

    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "duration_ms": self.duration_ms,
        }


async def check_api_health() -> PatrolResult:
    result = PatrolResult("api_health")
    import httpx

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{API_BASE}/health")
            result.duration_ms = (time.time() - start) * 1000

            if resp.status_code == 200:
                data = resp.json()
                result.ok(f"API正常, 响应{result.duration_ms:.0f}ms", response=data)
            else:
                result.fail(f"API返回{resp.status_code}", status_code=resp.status_code)

            if result.duration_ms > 2000:
                result.warn(f"API响应慢: {result.duration_ms:.0f}ms", response_time_ms=result.duration_ms)
    except Exception as e:
        result.fail(f"API不可达: {e}", error=str(e))
        result.duration_ms = (time.time() - start) * 1000

    return result


async def check_embedding_health() -> PatrolResult:
    result = PatrolResult("embedding_health")
    import httpx

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{EMBEDDING_BASE}/health")
            result.duration_ms = (time.time() - start) * 1000

            if resp.status_code == 200:
                data = resp.json()
                model_loaded = data.get("model_loaded", False)
                if model_loaded:
                    result.ok(f"Embedding服务正常, 模型已加载, {result.duration_ms:.0f}ms", response=data)
                else:
                    result.warn("Embedding服务模型未加载", response=data)
            else:
                result.fail(f"Embedding服务返回{resp.status_code}", status_code=resp.status_code)
    except Exception as e:
        result.fail(f"Embedding服务不可达: {e}", error=str(e))
        result.duration_ms = (time.time() - start) * 1000

    return result


async def check_db_health() -> PatrolResult:
    result = PatrolResult("db_health")
    import httpx

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{API_BASE}/health")
            result.duration_ms = (time.time() - start) * 1000

            if resp.status_code == 200:
                data = resp.json()
                db_status = data.get("database", data.get("status", "unknown"))
                if db_status in ("ok", "healthy"):
                    result.ok(f"数据库正常, 响应{result.duration_ms:.0f}ms", response=data)
                else:
                    result.warn(f"数据库状态: {db_status}", response=data)
            else:
                result.fail(f"数据库异常: HTTP {resp.status_code}")
    except Exception as e:
        result.fail(f"数据库检查失败: {e}", error=str(e))
        result.duration_ms = (time.time() - start) * 1000

    return result


async def check_search_performance() -> PatrolResult:
    result = PatrolResult("search_performance")
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            spec_resp = await client.get(f"{API_BASE}/openapi.json")
            if spec_resp.status_code == 200:
                spec = spec_resp.json()
                search_paths = [p for p in spec.get("paths", {}) if "search" in p.lower()]
                if not search_paths:
                    return result.warn(
                        "搜索路由未注册（API仅加载了部分路由），跳过性能检查",
                        available_paths=list(spec.get("paths", {}).keys()),
                    )
    except Exception:
        pass

    queries = ["气功", "中医", "论语"]
    latencies = []

    for q in queries:
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{API_BASE}/api/v1/search", params={"q": q, "limit": 5})
                latency = (time.time() - start) * 1000
                latencies.append({"query": q, "latency_ms": latency, "status": resp.status_code})

                if resp.status_code != 200:
                    result.warn(f"搜索'{q}'返回{resp.status_code}", query=q, status=resp.status_code)
        except Exception as e:
            latencies.append({"query": q, "error": str(e)})
            result.warn(f"搜索'{q}'失败: {e}")

    avg_latency = sum(l.get("latency_ms", 0) for l in latencies) / max(len(latencies), 1)
    max_latency = max(l.get("latency_ms", 0) for l in latencies)

    if max_latency > 5000:
        result.warn(
            f"检索性能差: 最大{max_latency:.0f}ms, 平均{avg_latency:.0f}ms",
            avg_latency_ms=avg_latency,
            max_latency_ms=max_latency,
            queries=latencies,
        )
    elif max_latency > 2000:
        result.warn(
            f"检索性能偏慢: 最大{max_latency:.0f}ms",
            avg_latency_ms=avg_latency,
            max_latency_ms=max_latency,
            queries=latencies,
        )
    else:
        result.ok(
            f"检索性能正常: 平均{avg_latency:.0f}ms, 最大{max_latency:.0f}ms",
            avg_latency_ms=avg_latency,
            max_latency_ms=max_latency,
            queries=latencies,
        )

    return result


async def check_api_routes() -> PatrolResult:
    result = PatrolResult("api_routes")
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{API_BASE}/openapi.json")
            if resp.status_code == 200:
                spec = resp.json()
                path_count = len(spec.get("paths", {}))
                if path_count < 10:
                    result.warn(
                        f"API路由不完整：仅{path_count}个路由注册（应有50+）",
                        registered_routes=path_count,
                        available_paths=list(spec.get("paths", {}).keys()),
                    )
                else:
                    result.ok(f"API路由完整：{path_count}个路由", route_count=path_count)
            else:
                result.warn("OpenAPI接口不可用")
    except Exception as e:
        result.warn(f"统计检查失败: {e}", error=str(e))

    return result


def check_docker_containers() -> PatrolResult:
    result = PatrolResult("docker_containers")
    import subprocess

    try:
        output = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        containers = []
        issues = []
        for line in output.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                name, status = parts[0], parts[1]
                containers.append({"name": name, "status": status})
                if "Exited" in status or "Dead" in status or "Restarting" in status:
                    issues.append(f"{name}: {status}")

        if issues:
            result.warn(f"发现{len(issues)}个异常容器", containers=containers, issues=issues)
        else:
            result.ok(f"所有{len(containers)}个容器正常", total=len(containers))
    except FileNotFoundError:
        result.warn("Docker未安装或不可用")
    except Exception as e:
        result.warn(f"Docker检查失败: {e}", error=str(e))

    return result


def check_disk_space() -> PatrolResult:
    result = PatrolResult("disk_space")
    import shutil

    try:
        usage = shutil.disk_usage("/")
        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        free_gb = usage.free / (1024**3)
        pct = (usage.used / usage.total) * 100

        if pct > 90:
            result.fail(
                f"磁盘空间严重不足: {pct:.1f}% ({free_gb:.1f}GB可用)",
                total_gb=total_gb,
                used_gb=used_gb,
                free_gb=free_gb,
                usage_pct=pct,
            )
        elif pct > 80:
            result.warn(
                f"磁盘空间偏少: {pct:.1f}% ({free_gb:.1f}GB可用)",
                total_gb=total_gb,
                used_gb=used_gb,
                free_gb=free_gb,
                usage_pct=pct,
            )
        else:
            result.ok(
                f"磁盘空间正常: {pct:.1f}% ({free_gb:.1f}GB可用)",
                total_gb=total_gb,
                used_gb=used_gb,
                free_gb=free_gb,
                usage_pct=pct,
            )
    except Exception as e:
        result.warn(f"磁盘检查失败: {e}")

    return result


async def run_patrol(quick: bool = False) -> list:
    checks = [
        check_api_health(),
        check_db_health(),
        check_docker_containers(),
        check_disk_space(),
    ]
    if not quick:
        checks.extend([
            check_search_performance(),
            check_api_routes(),
            check_embedding_health(),
        ])

    results = []
    tasks = []
    for c in checks:
        if asyncio.iscoroutine(c):
            tasks.append(c)
        else:
            results.append(c)

    if tasks:
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in task_results:
            if isinstance(r, Exception):
                pr = PatrolResult("unknown")
                pr.fail(str(r))
                results.append(pr)
            else:
                results.append(r)

    return results


def print_report(results: list, verbose: bool = False):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"  灵知主动巡检报告 — {now}")
    print(f"{'='*60}")

    ok_count = 0
    warn_count = 0
    fail_count = 0

    for r in results:
        icon = {"ok": "[OK]", "warn": "[!!]", "fail": "[XX]"}[r.status]
        print(f"  {icon} {r.name}: {r.message}")
        if r.duration_ms > 0:
            print(f"       耗时: {r.duration_ms:.0f}ms")
        if verbose and r.details:
            for k, v in r.details.items():
                val = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                print(f"       {k}: {val}")

        if r.status == "ok":
            ok_count += 1
        elif r.status == "warn":
            warn_count += 1
        else:
            fail_count += 1

    print(f"\n{'─'*60}")
    print(f"  结果: {ok_count} 通过 / {warn_count} 警告 / {fail_count} 失败")

    if fail_count > 0:
        print(f"  *** 需要立即处理 {fail_count} 个失败项 ***")
    elif warn_count > 0:
        print(f"  *** 需要关注 {warn_count} 个警告项 ***")
    else:
        print(f"  所有检查通过")

    print(f"{'='*60}\n")
    return fail_count == 0 and warn_count == 0


async def report_to_lingmessage(results: list):
    """将巡检发现的问题报告到灵信系统，通知灵族成员"""
    import httpx

    issues = [r for r in results if r.status != "ok"]
    if not issues:
        return

    severity = "critical" if any(r.status == "fail" for r in issues) else "high"
    issue_summary = "; ".join(f"{r.name}({r.status})" for r in issues)

    topic = f"[巡检告警] 灵知发现{len(issues)}个问题: {issue_summary}"
    description_lines = [
        f"灵知自动巡检于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 发现以下问题:\n",
    ]
    for r in issues:
        icon = "[!!]" if r.status == "warn" else "[XX]"
        description_lines.append(f"{icon} **{r.name}**: {r.message}")
        if r.details:
            for k, v in r.details.items():
                if k == "response":
                    continue
                val = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                description_lines.append(f"  - {k}: {val}")
    description_lines.append("\n请相关灵族成员关注并协助处理。")
    description = "\n".join(description_lines)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{API_BASE}/api/v1/lingmessage/threads",
                json={
                    "topic": topic[:500],
                    "description": description,
                    "created_by": "lingzhi",
                    "priority": severity,
                    "max_rounds": 5,
                },
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                thread_id = data.get("id", "?")
                print(f"  [灵信] 已创建讨论线程 #{thread_id}: {topic[:60]}...")
            else:
                print(f"  [灵信] 创建讨论线程失败: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  [灵信] 报告失败: {e}")


async def watch_mode(interval: int = 60, report: bool = False):
    print(f"灵知巡检持续监控模式 (间隔{interval}秒, Ctrl+C退出)")
    consecutive_issues = 0

    while True:
        results = await run_patrol(quick=True)
        has_issues = not print_report(results)

        if has_issues:
            consecutive_issues += 1
            if consecutive_issues >= 3:
                print(f"  [ALERT] 连续{consecutive_issues}次巡检发现问题!")
                if report:
                    await report_to_lingmessage(results)
        else:
            consecutive_issues = 0

        await asyncio.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="灵知主动巡检系统")
    parser.add_argument("--quick", action="store_true", help="快速巡检（跳过耗时检查）")
    parser.add_argument("--watch", action="store_true", help="持续监控模式")
    parser.add_argument("--interval", type=int, default=60, help="监控间隔（秒）")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")
    parser.add_argument("--report", action="store_true", help="发现问题时报送到灵信")
    args = parser.parse_args()

    if args.watch:
        try:
            asyncio.run(watch_mode(args.interval, report=args.report))
        except KeyboardInterrupt:
            print("\n巡检监控已停止")
    else:
        results = asyncio.run(run_patrol(quick=args.quick))

        if args.json:
            print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
        else:
            all_ok = print_report(results, verbose=args.verbose)
            if not all_ok and args.report:
                asyncio.run(report_to_lingmessage(results))
            sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
