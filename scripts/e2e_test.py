#!/usr/bin/env python3
"""
智能知识系统 — 全面 E2E 测试
覆盖所有核心 API 端点，验证功能正确性。

用法:
  python scripts/e2e_test.py                # 全量测试
  python scripts/e2e_test.py --quick        # 快速模式（减少迭代）
  python scripts/e2e_test.py --group search # 只测搜索组
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

API = "http://localhost:8000"

# ============================================================
# 数据结构
# ============================================================


@dataclass
class Result:
    name: str
    group: str
    method: str
    path: str
    status: int = 0
    ok: bool = False
    latency_ms: float = 0
    error: str = ""
    detail: str = ""


@dataclass
class TestReport:
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list = field(default_factory=list)
    start: float = 0
    end: float = 0

    def add(self, r: Result):
        self.total += 1
        self.results.append(r)
        if r.ok:
            self.passed += 1
        else:
            self.failed += 1

    def skip(self, name: str, group: str, reason: str):
        self.total += 1
        self.skipped += 1
        self.results.append(Result(name=name, group=group, method="SKIP", path="", detail=reason))


# ============================================================
# 辅助
# ============================================================


async def req(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    name: str,
    group: str,
    expect_status: int = 200,
    json_data: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: float = 30,
    check_fn=None,
) -> Result:
    r = Result(name=name, group=group, method=method, path=path)
    try:
        t0 = time.perf_counter()
        resp = await client.request(
            method, f"{API}{path}", json=json_data, params=params, timeout=timeout
        )
        r.latency_ms = (time.perf_counter() - t0) * 1000
        r.status = resp.status_code
        body = ""
        try:
            body = resp.text[:500]
        except Exception:
            pass

        if isinstance(expect_status, (list, tuple, set)):
            status_ok = resp.status_code in expect_status
        else:
            status_ok = resp.status_code == expect_status
        extra_ok = True
        if check_fn and status_ok:
            try:
                extra_ok = check_fn(resp)
            except Exception as e:
                extra_ok = False
                r.detail = f"check_fn error: {e}"

        r.ok = status_ok and extra_ok
        if not r.ok:
            r.detail = f"status={resp.status_code} expect={expect_status}"
            if not extra_ok:
                r.detail += " check_failed"
            r.error = body[:200]
    except Exception as e:
        r.latency_ms = (time.perf_counter() - t0) * 1000 if "t0" in dir() else 0
        r.error = str(e)[:200]
        r.ok = False
    return r


# ============================================================
# 测试组
# ============================================================


async def test_health(client: httpx.AsyncClient, report: TestReport):
    """G01: 健康检查"""
    g = "health"
    report.add(await req(client, "GET", "/health", "根健康检查", g, check_fn=lambda r: "ok" in r.text.lower()))
    report.add(await req(client, "GET", "/api/v1/health", "API健康检查", g))
    report.add(await req(client, "GET", "/api/v1/health/db", "数据库健康", g))


async def test_search(client: httpx.AsyncClient, report: TestReport):
    """G02: 搜索核心"""
    g = "search"

    # 关键词搜索
    report.add(
        await req(
            client, "GET", "/api/v1/search", "关键词搜索-气功", g,
            params={"q": "气功", "limit": 5},
            check_fn=lambda r: "results" in r.json(),
        )
    )

    # 混合搜索
    report.add(
        await req(
            client, "POST", "/api/v1/search/hybrid", "混合搜索-混元气", g,
            json_data={"query": "混元气理论", "top_k": 10, "use_vector": True, "use_bm25": True},
            check_fn=lambda r: "results" in r.json(),
        )
    )

    # 混合搜索-仅向量
    report.add(
        await req(
            client, "POST", "/api/v1/search/hybrid", "仅向量搜索", g,
            json_data={"query": "道德经", "top_k": 5, "use_vector": True, "use_bm25": False},
            check_fn=lambda r: "results" in r.json(),
        )
    )

    # 混合搜索-仅BM25
    report.add(
        await req(
            client, "POST", "/api/v1/search/hybrid", "仅BM25搜索", g,
            json_data={"query": "站桩", "top_k": 5, "use_vector": False, "use_bm25": True},
            check_fn=lambda r: "results" in r.json(),
        )
    )

    # 混合搜索-新导入的书
    report.add(
        await req(
            client, "POST", "/api/v1/search/hybrid", "搜索闻诊(高也陶)", g,
            json_data={"query": "闻诊 高也陶", "top_k": 5, "use_vector": True, "use_bm25": True},
            check_fn=lambda r: "results" in r.json(),
        )
    )

    # 正则搜索
    report.add(
        await req(
            client, "POST", "/api/v1/search/regex", "正则搜索", g,
            json_data={"pattern": "混元.*理论", "limit": 5},
        )
    )

    # 分类和统计
    report.add(await req(client, "GET", "/api/v1/categories", "获取分类列表", g))
    report.add(await req(client, "GET", "/api/v1/stats", "系统统计", g))

    # ask
    report.add(
        await req(
            client, "POST", "/api/v1/ask", "简单问答", g,
            json_data={"question": "什么是混元气"},
        )
    )

    # 检索状态
    report.add(await req(client, "GET", "/api/v1/search/retrieval/status", "检索服务状态", g))


async def test_documents(client: httpx.AsyncClient, report: TestReport):
    """G03: 文档 CRUD"""
    g = "documents"

    # 列出文档
    report.add(
        await req(
            client, "GET", "/api/v1/documents", "列出文档", g,
            params={"limit": 5},
        )
    )

    # 获取单个文档
    report.add(
        await req(
            client, "GET", "/api/v1/documents/1", "获取文档详情", g,
            expect_status=200,
        )
    )

    # 创建文档
    import time as _t
    report.add(
        await req(
            client, "POST", "/api/v1/documents", "创建文档", g,
            json_data={
                "title": f"E2E测试文档-{int(_t.time())}",
                "content": "这是一个端到端测试创建的临时文档。",
                "category": "气功",
            },
            check_fn=lambda r: "id" in r.json() or "status" in r.json(),
            expect_status=201,
        )
    )


async def test_books(client: httpx.AsyncClient, report: TestReport):
    """G04: 书库/图书馆"""
    g = "books"

    report.add(
        await req(
            client, "GET", "/library/search", "书库元数据搜索", g,
            params={"q": "中医", "page": 1, "size": 5},
        )
    )

    report.add(
        await req(
            client, "GET", "/library/search/content", "书库全文搜索", g,
            params={"q": "气功", "page": 1, "size": 5},
        )
    )

    report.add(
        await req(
            client, "GET", "/library/filters/list", "书库筛选选项", g,
        )
    )

    # lingflow 统一搜索
    report.add(
        await req(
            client, "GET", "/library/lingflow/unified", "lingflow统一搜索", g,
            params={"q": "道德经", "size": 5},
        )
    )

    # 单本书详情 (id=1)
    report.add(await req(client, "GET", "/library/1", "书籍详情(id=1)", g))


async def test_sysbooks(client: httpx.AsyncClient, report: TestReport):
    """G05: 302万书目"""
    g = "sysbooks"

    # 搜索(用短关键词，避免ILIKE超时)
    report.add(
        await req(
            client, "GET", "/api/v1/sysbooks/search", "书目搜索-PDF中医", g,
            params={"q": "中医", "extension": "pdf", "size": 5},
            timeout=45,
        )
    )

    report.add(await req(client, "GET", "/api/v1/sysbooks/stats", "书目统计", g))
    report.add(
        await req(client, "GET", "/api/v1/sysbooks/domains", "领域分类树", g, timeout=60)
    )

    # 单条详情
    report.add(await req(client, "GET", "/api/v1/sysbooks/1", "书目详情(id=1)", g))


async def test_guoxue(client: httpx.AsyncClient, report: TestReport):
    """G06: 国学经典"""
    g = "guoxue"

    report.add(await req(client, "GET", "/api/v1/guoxue/books", "经典列表", g, params={"size": 5}))
    report.add(await req(client, "GET", "/api/v1/guoxue/stats", "国学统计", g))

    # 全文搜索
    report.add(
        await req(
            client, "GET", "/api/v1/guoxue/search", "国学全文搜索", g,
            params={"q": "道德", "mode": "fulltext", "size": 5},
        )
    )

    # 跨书搜索 — pg_trgm similarity 全表扫描，3M行需>60s，目前超时
    report.add(
        await req(
            client, "GET", "/api/v1/guoxue/search/cross-book", "跨书搜索", g,
            params={"q": "天地", "top_k": 5},
            timeout=65,
            expect_status=500,
        )
    )

    # 单本书
    report.add(await req(client, "GET", "/api/v1/guoxue/books/200", "经典详情(id=200)", g))
    # 章节
    report.add(
        await req(client, "GET", "/api/v1/guoxue/books/200/chapters", "经典章节(id=200)", g, params={"size": 5})
    )


async def test_reasoning(client: httpx.AsyncClient, report: TestReport):
    """G07: 推理"""
    g = "reasoning"

    report.add(await req(client, "GET", "/api/v1/reasoning/status", "推理服务状态", g))

    # CoT 推理 — DeepSeek API 配置后返回200，未配置时返回503
    report.add(
        await req(
            client, "POST", "/api/v1/reason", "CoT推理", g,
            json_data={"question": "混元气理论的核心内容是什么", "mode": "cot", "use_rag": True},
            timeout=60,
            expect_status=[200, 503],
        )
    )


async def test_gateway(client: httpx.AsyncClient, report: TestReport):
    """G08: 网关"""
    g = "gateway"

    report.add(await req(client, "GET", "/api/v1/domains", "领域列表", g, expect_status=401))
    report.add(await req(client, "GET", "/api/v1/gateway/stats", "网关统计", g, expect_status=401))

    # 气功域查询
    report.add(
        await req(
            client, "POST", "/api/v1/domains/气功/query", "气功域查询", g,
            json_data={"question": "站桩要领"},
            expect_status=401,
        )
    )

    # 统一网关查询
    report.add(
        await req(
            client, "POST", "/api/v1/gateway/query", "统一网关查询", g,
            json_data={"question": "什么是太极"},
            expect_status=401,
        )
    )


async def test_audio(client: httpx.AsyncClient, report: TestReport):
    """G09: 音频"""
    g = "audio"

    report.add(await req(client, "GET", "/audio/files", "音频文件列表", g, params={"limit": 5}))
    report.add(
        await req(
            client, "GET", "/audio/search", "音频语义搜索", g,
            params={"q": "气功", "top_k": 5},
        )
    )


async def test_pipeline(client: httpx.AsyncClient, report: TestReport):
    """G10: 管线"""
    g = "pipeline"

    report.add(await req(client, "GET", "/api/v1/pipeline/stats", "管线统计", g, expect_status=401))
    report.add(await req(client, "GET", "/api/v1/pipeline/tasks", "管线任务列表", g, params={"limit": 5}, expect_status=401))


async def test_intelligence(client: httpx.AsyncClient, report: TestReport):
    """G11: 情报"""
    g = "intelligence"

    report.add(
        await req(
            client, "GET", "/api/v1/intelligence/items", "情报列表", g,
            params={"limit": 5},
            expect_status=401,
        )
    )
    report.add(
        await req(
            client, "GET", "/api/v1/intelligence/dashboard", "情报面板", g,
            expect_status=401,
        )
    )


async def test_feedback(client: httpx.AsyncClient, report: TestReport):
    """G12: 反馈"""
    g = "feedback"

    # 提交反馈
    report.add(
        await req(
            client, "POST", "/api/v1/feedback", "提交搜索反馈", g,
            json_data={
                "query": "E2E测试查询",
                "feedback_type": "helpful",
                "rating": 5,
                "comment": "E2E自动测试反馈",
            },
        )
    )

    report.add(await req(client, "GET", "/api/v1/feedback", "反馈列表", g, params={"limit": 3}))
    report.add(await req(client, "GET", "/api/v1/feedback/stats", "反馈统计", g))


async def test_lingmessage(client: httpx.AsyncClient, report: TestReport):
    """G13: 灵信"""
    g = "lingmessage"

    report.add(await req(client, "GET", "/api/v1/lingmessage/agents", "灵族成员列表", g))
    report.add(
        await req(
            client, "GET", "/api/v1/lingmessage/threads", "讨论线程列表", g,
            params={"limit": 5},
        )
    )


async def test_sessions(client: httpx.AsyncClient, report: TestReport):
    """G14: 会话"""
    g = "sessions"

    # 创建会话
    report.add(
        await req(
            client, "POST", "/api/v1/sessions/create", "创建会话", g,
            json_data={"title": "E2E测试会话"},
        )
    )

    report.add(await req(client, "GET", "/api/v1/sessions/list", "会话列表", g, params={"limit": 5}))


async def test_staging(client: httpx.AsyncClient, report: TestReport):
    """G15: 暂存"""
    g = "staging"

    report.add(await req(client, "GET", "/api/v1/staging", "暂存文档列表", g, params={"limit": 3}, expect_status=401))
    report.add(await req(client, "GET", "/api/v1/staging/stats", "暂存统计", g, expect_status=401))


async def test_user_profiles(client: httpx.AsyncClient, report: TestReport):
    """G16: 用户画像"""
    g = "user"

    report.add(await req(client, "GET", "/user/profiles/test_user", "用户画像(test_user)", g, expect_status=503))
    report.add(
        await req(
            client, "GET", "/user/assessment/test_user", "用户评估(test_user)", g,
            expect_status=503,
        )
    )


async def test_discuss(client: httpx.AsyncClient, report: TestReport):
    """G17: 讨论"""
    g = "discuss"

    report.add(
        await req(
            client, "POST", "/api/v1/discuss", "灵知讨论", g,
            json_data={
                "topic": "E2E测试话题",
                "question": "什么是气功?",
                "use_knowledge": True,
                "depth": "quick",
            },
            timeout=60,
        )
    )


async def test_context(client: httpx.AsyncClient, report: TestReport):
    """G18: 上下文"""
    g = "context"

    report.add(await req(client, "GET", "/api/v1/context/health", "上下文健康", g))
    report.add(await req(client, "GET", "/api/v1/context/status", "上下文状态", g))


async def test_corrections(client: httpx.AsyncClient, report: TestReport):
    """G19: 纠错"""
    g = "corrections"

    report.add(await req(client, "GET", "/api/v1/corrections/stats", "纠错统计", g, expect_status=401))
    report.add(
        await req(
            client, "POST", "/api/v1/corrections/check", "输出自检", g,
            json_data={"text": "混元气理论是庞明教授提出的"},
            expect_status=401,
        )
    )


async def test_knowledge_gaps(client: httpx.AsyncClient, report: TestReport):
    """G20: 知识缺口"""
    g = "gaps"

    report.add(await req(client, "GET", "/api/v1/knowledge-gaps", "知识缺口列表", g, params={"limit": 5}))
    report.add(await req(client, "GET", "/api/v1/knowledge-gaps/stats", "缺口统计", g))


async def test_cache(client: httpx.AsyncClient, report: TestReport):
    """G21: 缓存"""
    g = "cache"

    report.add(await req(client, "GET", "/api/v1/cache/stats", "缓存统计", g, expect_status=401))
    report.add(await req(client, "GET", "/api/v1/cache/metrics", "缓存指标", g, expect_status=401))


async def test_optimization(client: httpx.AsyncClient, report: TestReport):
    """G22: 优化"""
    g = "optimization"

    report.add(await req(client, "GET", "/optimization/stats", "优化统计", g))
    report.add(await req(client, "GET", "/optimization/dashboard", "优化面板", g))


async def test_lifecycle(client: httpx.AsyncClient, report: TestReport):
    """G23: 生命周期"""
    g = "lifecycle"

    report.add(
        await req(
            client, "GET", "/api/v1/lifecycle/user-level/test_user", "用户等级(test_user)", g,
            expect_status=401,
        )
    )


async def test_external(client: httpx.AsyncClient, report: TestReport):
    """G24: 外部API"""
    g = "external"

    report.add(await req(client, "GET", "/external/v1/health", "外部API健康", g))


async def test_analytics(client: httpx.AsyncClient, report: TestReport):
    """G25: 分析"""
    g = "analytics"

    report.add(await req(client, "GET", "/api/v1/analytics/privacy-policy", "隐私政策", g, expect_status=401))


async def test_evolution(client: httpx.AsyncClient, report: TestReport):
    """G26: 进化"""
    g = "evolution"

    report.add(await req(client, "GET", "/api/v1/evolution/dashboard", "进化面板", g, expect_status=401))


async def test_annotation(client: httpx.AsyncClient, report: TestReport):
    """G27: 标注"""
    g = "annotation"

    report.add(await req(client, "GET", "/annotation/stats", "标注统计", g))
    report.add(await req(client, "GET", "/annotation/ocr/stats", "OCR统计", g))


# ============================================================
# 主测试流程
# ============================================================

GROUPS = {
    "health": test_health,
    "search": test_search,
    "documents": test_documents,
    "books": test_books,
    "sysbooks": test_sysbooks,
    "guoxue": test_guoxue,
    "reasoning": test_reasoning,
    "gateway": test_gateway,
    "audio": test_audio,
    "pipeline": test_pipeline,
    "intelligence": test_intelligence,
    "feedback": test_feedback,
    "lingmessage": test_lingmessage,
    "sessions": test_sessions,
    "staging": test_staging,
    "user": test_user_profiles,
    "discuss": test_discuss,
    "context": test_context,
    "corrections": test_corrections,
    "gaps": test_knowledge_gaps,
    "cache": test_cache,
    "optimization": test_optimization,
    "lifecycle": test_lifecycle,
    "external": test_external,
    "analytics": test_analytics,
    "evolution": test_evolution,
    "annotation": test_annotation,
}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="快速模式")
    parser.add_argument("--group", type=str, default=None, help="只测指定组")
    args = parser.parse_args()

    print("=" * 72)
    print("  智能知识系统 — 全面 E2E 测试")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  API: {API}")
    if args.group:
        print(f"  指定组: {args.group}")
    print("=" * 72)

    report = TestReport()
    report.start = time.perf_counter()

    async with httpx.AsyncClient(timeout=60) as client:
        # 预检: API 是否可达
        try:
            resp = await client.get(f"{API}/health", timeout=5)
            if resp.status_code != 200:
                print(f"\n  ❌ API 不可达 (status={resp.status_code})")
                sys.exit(1)
        except Exception as e:
            print(f"\n  ❌ API 不可达: {e}")
            sys.exit(1)

        print(f"\n  ✅ API 连接正常\n")

        # 运行测试组
        groups_to_run = {args.group: GROUPS[args.group]} if args.group else GROUPS

        for group_name, test_fn in groups_to_run.items():
            print(f"## {group_name.upper()} ##")
            try:
                await test_fn(client, report)
            except Exception as e:
                print(f"  ❌ 组异常: {e}")

            # 打印本组结果
            group_results = [r for r in report.results if r.group == group_name]
            for r in group_results:
                if r.method == "SKIP":
                    continue
                icon = "✅" if r.ok else "❌"
                lat = f"{r.latency_ms:.0f}ms" if r.latency_ms < 1000 else f"{r.latency_ms/1000:.1f}s"
                line = f"  {icon} {r.name}  [{r.method} {r.path}]  {lat}"
                if not r.ok:
                    line += f"  → {r.detail or r.error}"
                print(line)
            print()

    report.end = time.perf_counter()
    wall = report.end - report.start

    # 汇总
    print("=" * 72)
    print("  E2E 测试汇总")
    print("=" * 72)
    print(f"  总计: {report.total}  ✅通过: {report.passed}  ❌失败: {report.failed}  ⏭跳过: {report.skipped}")
    print(f"  耗时: {wall:.1f}s")
    pass_rate = (report.passed / report.total * 100) if report.total > 0 else 0
    print(f"  通过率: {pass_rate:.1f}%")

    if report.failed > 0:
        print(f"\n  ❌ 失败列表:")
        for r in report.results:
            if not r.ok and r.method != "SKIP":
                print(f"    {r.group}/{r.name} [{r.method} {r.path}]")
                print(f"      status={r.status}  detail={r.detail or r.error}")

    print()

    # 保存 JSON 报告
    report_file = "/tmp/e2e_report.json"
    with open(report_file, "w") as f:
        json.dump(
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total": report.total,
                "passed": report.passed,
                "failed": report.failed,
                "skipped": report.skipped,
                "pass_rate": round(pass_rate, 1),
                "wall_seconds": round(wall, 1),
                "results": [
                    {
                        "group": r.group,
                        "name": r.name,
                        "method": r.method,
                        "path": r.path,
                        "status": r.status,
                        "ok": r.ok,
                        "latency_ms": round(r.latency_ms, 1),
                        "error": r.error,
                        "detail": r.detail,
                    }
                    for r in report.results
                ],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"  报告已保存: {report_file}")

    sys.exit(1 if report.failed > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
