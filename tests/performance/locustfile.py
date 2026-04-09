"""
智能知识系统 - 性能测试脚本

使用 Locust 进行负载测试和性能基准测试

性能目标:
- P50 响应时间 < 200ms
- P95 响应时间 < 1s
- P99 响应时间 < 2s
- 支持 100 并发用户

运行方式:
    locust -f tests/performance/locustfile.py --host=http://localhost:8000

无头模式:
    locust -f tests/performance/locustfile.py --headless \
           --host=http://localhost:8000 \
           --users=100 \
           --spawn-rate=10 \
           --run-time=2m \
           --html=report.html
"""

import os
import random
import time
from datetime import datetime

from locust import HttpUser, between, constant, events, task

# ========== 配置 ==========

# 测试目标配置
TARGET_HOST = os.getenv("TARGET_HOST", "http://localhost:8000")
TARGET_USERS = int(os.getenv("TARGET_USERS", "100"))
SPAWN_RATE = int(os.getenv("SPAWN_RATE", "10"))
RUN_TIME = os.getenv("RUN_TIME", "2m")

# 性能阈值 (毫秒)
PERFORMANCE_TARGETS = {
    "p50": 200,  # 中位数响应时间
    "p95": 1000,  # 95分位响应时间
    "p99": 2000,  # 99分位响应时间
}

# ========== 测试数据 ==========

# 搜索查询样本
SEARCH_QUERIES = [
    "气功",
    "八段锦",
    "中医",
    "针灸",
    "儒家",
    "论语",
    "养生",
    "太极",
    "经络",
    "阴阳",
]

# 问题样本
QUESTIONS = [
    "什么是气功？",
    "八段锦有什么好处？",
    "中医的基本理论是什么？",
    "针灸如何治疗疾病？",
    "孔子的核心思想是什么？",
    "如何练习太极拳？",
    "经络系统是如何工作的？",
    "阴阳五行学说的内容是什么？",
]

# 分类样本
CATEGORIES = ["气功", "中医", "儒家"]


class KnowledgeAPIUser(HttpUser):
    """
    智能知识系统 API 用户行为模拟

    模拟真实用户的使用场景：
    1. 浏览文档列表 (权重: 2)
    2. 搜索关键词 (权重: 4)
    3. 智能问答 (权重: 3)
    4. 混合检索 (权重: 2)
    """

    # 等待时间: 用户操作间隔 1-3 秒
    wait_time = between(1, 3)

    def on_start(self):
        """用户启动时的初始化操作"""
        # 设置请求超时
        self.client.timeout = 30

        # 记录会话开始时间
        self.start_time = time.time()

    @task(weight=2)
    def list_documents(self) -> None:
        """
        获取文档列表

        端点: GET /api/v1/documents
        """
        params = {
            "limit": random.choice([10, 20, 50]),
            "offset": random.choice([0, 10, 20]),
        }

        # 随机添加分类筛选
        if random.random() > 0.7:
            params["category"] = random.choice(CATEGORIES)

        with self.client.get(
            "/api/v1/documents",
            params=params,
            name="GET /api/v1/documents",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "documents" in data:
                    response.success()
                else:
                    response.failure("Invalid response format")
            elif response.status_code == 404:
                response.success()  # 空结果也是正常的
            else:
                response.failure(f"Status: {response.status_code}")

    @task(weight=4)
    def search_documents(self) -> None:
        """
        关键词搜索

        端点: GET /api/v1/search?q=测试
        """
        query = random.choice(SEARCH_QUERIES)

        params = {
            "q": query,
            "limit": random.choice([10, 20, 50]),
        }

        # 随机添加分类筛选
        if random.random() > 0.7:
            params["category"] = random.choice(CATEGORIES)

        with self.client.get(
            "/api/v1/search",
            params=params,
            name="GET /api/v1/search",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "results" in data or "total" in data:
                    response.success()
                else:
                    response.failure("Invalid response format")
            elif response.status_code == 404:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")

    @task(weight=3)
    def ask_question(self) -> None:
        """
        智能问答

        端点: POST /api/v1/ask
        """
        payload = {
            "question": random.choice(QUESTIONS),
            "session_id": f"perf_test_{int(time.time())}_{random.randint(1000, 9999)}",
        }

        # 随机添加分类
        if random.random() > 0.7:
            payload["category"] = random.choice(CATEGORIES)

        with self.client.post(
            "/api/v1/ask",
            json=payload,
            name="POST /api/v1/ask",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "answer" in data and "sources" in data:
                    response.success()
                else:
                    response.failure("Invalid response format")
            elif response.status_code == 429:
                # 速率限制是预期内的行为
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")

    @task(weight=2)
    def hybrid_search(self) -> None:
        """
        混合检索

        端点: POST /api/v1/search/hybrid
        """
        query = random.choice(SEARCH_QUERIES)

        payload = {
            "query": query,
            "top_k": random.choice([5, 10, 20]),
            "use_vector": True,
            "use_bm25": True,
        }

        # 随机添加分类筛选
        if random.random() > 0.7:
            payload["category"] = random.choice(CATEGORIES)

        with self.client.post(
            "/api/v1/search/hybrid",
            json=payload,
            name="POST /api/v1/search/hybrid",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "results" in data and "total" in data:
                    response.success()
                else:
                    response.failure("Invalid response format")
            elif response.status_code == 503:
                # 服务暂时不可用（可能是资源限制）
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")

    @task(weight=1)
    def health_check(self) -> None:
        """
        健康检查

        端点: GET /health
        """
        with self.client.get(
            "/health",
            name="GET /health",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")


class ReadHeavyUser(KnowledgeAPIUser):
    """
    读密集型用户

    主要执行读取操作，模拟浏览和搜索行为
    """

    @task(weight=8)
    def list_documents(self) -> None:
        """重写文档列表权重"""
        super().list_documents()

    @task(weight=10)
    def search_documents(self) -> None:
        """重写搜索权重"""
        super().search_documents()

    @task(weight=1)
    def ask_question(self) -> None:
        """降低问答权重"""
        super().ask_question()

    @task(weight=1)
    def hybrid_search(self) -> None:
        """降低混合检索权重"""
        super().hybrid_search()


class WriteHeavyUser(KnowledgeAPIUser):
    """
    写密集型用户

    主要执行复杂查询操作，模拟高级用户行为
    """

    @task(weight=1)
    def list_documents(self) -> None:
        """降低文档列表权重"""
        super().list_documents()

    @task(weight=2)
    def search_documents(self) -> None:
        """降低搜索权重"""
        super().search_documents()

    @task(weight=5)
    def ask_question(self) -> None:
        """提高问答权重"""
        super().ask_question()

    @task(weight=5)
    def hybrid_search(self) -> None:
        """提高混合检索权重"""
        super().hybrid_search()


# ========== 性能监控和报告 ==========


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时的回调"""
    print("\n" + "=" * 60)
    print("性能测试开始")
    print("=" * 60)
    print(f"目标主机: {TARGET_HOST}")
    print(f"目标用户数: {TARGET_USERS}")
    print(f"生成速率: {SPAWN_RATE} users/second")
    print(f"运行时长: {RUN_TIME}")
    print(f"开始时间: {datetime.now().isoformat()}")
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时的回调"""
    print("\n" + "=" * 60)
    print("性能测试完成")
    print("=" * 60)
    print(f"结束时间: {datetime.now().isoformat()}")

    # 输出性能统计
    if environment.stats.total.fail_ratio > 0:
        print(f"\n警告: 失败率为 {environment.stats.total.fail_ratio:.2%}")

    # 检查是否达到性能目标
    for endpoint, stats in environment.stats.entries.items():
        if stats.response_times:
            p50 = stats.percentile(50)
            p95 = stats.percentile(95)
            p99 = stats.percentile(99)

            print(f"\n端点: {endpoint}")
            print(f"  请求数: {stats.num_requests}")
            print(f"  失败率: {stats.fail_ratio:.2%}")
            print(f"  P50: {p50:.0f}ms (目标: <{PERFORMANCE_TARGETS['p50']}ms)")
            print(f"  P95: {p95:.0f}ms (目标: <{PERFORMANCE_TARGETS['p95']}ms)")
            print(f"  P99: {p99:.0f}ms (目标: <{PERFORMANCE_TARGETS['p99']}ms)")

            # 检查是否达标
            issues = []
            if p50 > PERFORMANCE_TARGETS["p50"]:
                issues.append(f"P50 超标 ({p50:.0f}ms > {PERFORMANCE_TARGETS['p50']}ms)")
            if p95 > PERFORMANCE_TARGETS["p95"]:
                issues.append(f"P95 超标 ({p95:.0f}ms > {PERFORMANCE_TARGETS['p95']}ms)")
            if p99 > PERFORMANCE_TARGETS["p99"]:
                issues.append(f"P99 超标 ({p99:.0f}ms > {PERFORMANCE_TARGETS['p99']}ms)")

            if issues:
                print(f"  ⚠️ 性能问题: {'; '.join(issues)}")
            else:
                print("  ✅ 性能达标")

    print("=" * 60 + "\n")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """请求完成时的回调 - 用于实时监控"""
    # 可以在这里添加自定义日志或告警逻辑
    pass


# ========== 单独的端点测试类 ==========


class SearchEndpointTest(HttpUser):
    """
    搜索端点专项测试

    用于单独测试搜索性能
    """

    wait_time = constant(0.5)  # 固定间隔，高频测试

    @task
    def search_only(self) -> None:
        """仅测试搜索"""
        query = random.choice(SEARCH_QUERIES)
        self.client.get(
            f"/api/v1/search?q={query}&limit=20",
            name="Search Load Test",
        )


class AskEndpointTest(HttpUser):
    """
    问答端点专项测试

    用于单独测试问答性能
    """

    wait_time = constant(1)

    @task
    def ask_only(self) -> None:
        """仅测试问答"""
        payload = {"question": random.choice(QUESTIONS)}
        self.client.post(
            "/api/v1/ask",
            json=payload,
            name="Ask Load Test",
        )


class HybridSearchEndpointTest(HttpUser):
    """
    混合检索端点专项测试

    用于单独测试混合检索性能
    """

    wait_time = constant(1)

    @task
    def hybrid_only(self) -> None:
        """仅测试混合检索"""
        payload = {
            "query": random.choice(SEARCH_QUERIES),
            "top_k": 10,
            "use_vector": True,
            "use_bm25": True,
        }
        self.client.post(
            "/api/v1/search/hybrid",
            json=payload,
            name="Hybrid Search Load Test",
        )


class DocumentsEndpointTest(HttpUser):
    """
    文档端点专项测试

    用于单独测试文档列表性能
    """

    wait_time = constant(0.3)

    @task
    def list_only(self) -> None:
        """仅测试文档列表"""
        self.client.get(
            "/api/v1/documents?limit=20",
            name="Documents Load Test",
        )
