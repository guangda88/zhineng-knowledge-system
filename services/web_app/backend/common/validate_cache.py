# -*- coding: utf-8 -*-
"""
Redis 缓存层验证脚本
Cache Layer Validation Script

全面验证缓存层的功能和特性
"""

import asyncio
import sys
import os
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


class CacheValidator:
    """缓存验证器"""

    def __init__(self):
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": [],
        }
        self.backend_type = "memory"  # 默认使用内存缓存

    def _pass(self, test_name: str, details: str = ""):
        """记录测试通过"""
        self.results["passed"].append({"test": test_name, "details": details})
        print(f"  [PASS] {test_name}")
        if details:
            print(f"         {details}")

    def _fail(self, test_name: str, error: str):
        """记录测试失败"""
        self.results["failed"].append({"test": test_name, "error": error})
        print(f"  [FAIL] {test_name}: {error}")

    def _warn(self, test_name: str, message: str):
        """记录警告"""
        self.results["warnings"].append({"test": test_name, "message": message})
        print(f"  [WARN] {test_name}: {message}")

    async def check_redis_connection(self) -> bool:
        """检查 Redis 连接"""
        print("\n=== 1. Redis 连接检查 ===")
        test_name = "Redis 连接测试"

        try:
            import redis

            client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                password=os.getenv("REDIS_PASSWORD"),
                db=int(os.getenv("REDIS_DB", "0")),
                decode_responses=True,
                socket_timeout=2,
            )
            client.ping()
            self._pass(test_name, "Redis 服务正常运行")
            return True
        except Exception as e:
            self._fail(test_name, f"Redis 未运行或未安装: {str(e)}")
            self.backend_type = "memory"
            return False

    async def check_cache_manager_basic(self):
        """检查缓存管理器基本功能"""
        from .cache_manager import CacheManager

        print("\n=== 2. 缓存管理器基本功能 ===")

        # 测试基本读写
        print("\n2.1 基本读写操作")
        cache = CacheManager(backend="memory")

        await cache.set("test:key", {"value": "test_data"})
        value = await cache.get("test:key")
        if value == {"value": "test_data"}:
            self._pass("基本读写", "数据写入和读取正常")
        else:
            self._fail("基本读写", f"期望 {{'value': 'test_data'}}，实际 {value}")

        # 测试删除操作
        await cache.delete("test:key")
        value = await cache.get("test:key")
        if value is None:
            self._pass("删除操作", "数据删除后无法读取")
        else:
            self._fail("删除操作", "删除后仍能读取数据")

        await cache.close()

    async def check_ttl_strategy(self):
        """检查 TTL 策略"""
        from .cache_manager import CacheManager

        print("\n=== 3. TTL 策略验证 ===")

        cache = CacheManager(backend="memory")

        # 测试短期 TTL
        print("\n3.1 短期 TTL (2秒)")
        await cache.set("ttl:short", "short_ttl", ttl=2)
        value = await cache.get("ttl:short")
        if value == "short_ttl":
            self._pass("短期 TTL 设置", "2秒内数据可读")
        else:
            self._fail("短期 TTL 设置", "TTL 设置后立即读取失败")

        # 等待过期
        await asyncio.sleep(2.1)
        value = await cache.get("ttl:short")
        if value is None:
            self._pass("TTL 过期", "2秒后数据自动过期")
        else:
            self._fail("TTL 过期", "TTL 过期后数据仍可读")

        # 测试长期 TTL
        print("\n3.2 长期 TTL 配置")
        from .cache_manager import CacheTTL

        ttl_values = {
            "USER_INFO": CacheTTL.USER_INFO,
            "DOCUMENT_INFO": CacheTTL.DOCUMENT_INFO,
            "SEARCH_RESULT": CacheTTL.SEARCH_RESULT,
            "SESSION": CacheTTL.SESSION,
        }
        for name, ttl in ttl_values.items():
            if ttl > 0:
                self._pass(f"TTL 配置 - {name}", f"{ttl}秒")

        await cache.close()

    async def check_lru_strategy(self):
        """检查 LRU 策略"""
        from .cache_manager import MemoryCacheBackend

        print("\n=== 4. LRU 驱逐策略验证 ===")

        # 创建一个小容量缓存
        backend = MemoryCacheBackend(maxsize=5, default_ttl=3600)

        # 写入超过容量的数据
        print("\n4.1 写入 10 个键到容量为 5 的缓存")
        for i in range(10):
            await backend.set(f"lru:key{i}", f"value{i}")

        stats = backend.get_stats()
        print(f"     容量: {stats.maxsize}, 当前大小: {stats.size}")

        if stats.size <= stats.maxsize:
            self._pass("LRU 容量限制", f"缓存大小保持在 {stats.maxsize} 以内")
        else:
            self._fail("LRU 容量限制", f"缓存大小 {stats.size} 超过最大值 {stats.maxsize}")

        # 验证最早的键被驱逐
        value = await backend.get("lru:key0")
        if value is None:
            self._pass("LRU 驱逐", "最早的键已被驱逐")
        else:
            self._warn("LRU 驱逐", "最早的键仍在缓存中（可能未达到驱逐条件）")

        # 验证最新的键存在
        value = await backend.get("lru:key9")
        if value is not None:
            self._pass("LRU 保留", "最新的键被保留")
        else:
            self._fail("LRU 保留", "最新的键被意外驱逐")

        await backend.close()

    async def check_cache_penetration_protection(self):
        """检查缓存穿透保护"""
        from .cache_manager import CacheManager

        print("\n=== 5. 缓存穿透保护验证 ===")

        cache = CacheManager(backend="memory")

        print("\n5.1 读取不存在的键")
        value = await cache.get("nonexistent:key")
        if value is None:
            self._pass("空键处理", "不存在的键返回 None")
        else:
            self._fail("空键处理", f"期望 None，实际 {value}")

        print("\n5.2 批量不存在的键")
        none_count = 0
        for i in range(100):
            value = await cache.get(f"nonexistent:key{i}")
            if value is None:
                none_count += 1
        if none_count == 100:
            self._pass("批量空键处理", "100 个不存在的键都返回 None")
        else:
            self._fail("批量空键处理", f"有 {100 - none_count} 个键返回了非空值")

        # 检查缓存未命中时统计是否正确
        stats = cache.get_stats()
        if stats.get("default", {}).get("misses", 0) > 0:
            self._pass("未命中统计", "缓存未命中计数器工作正常")
        else:
            self._warn("未命中统计", "未命中计数器未更新")

        await cache.close()

    async def check_cache_services(self):
        """检查缓存服务"""
        from .cache_manager import CacheManager
        from .cache_service import (
            UserCacheService,
            DocumentCacheService,
            SearchCacheService,
            HotwordCacheService,
        )

        print("\n=== 6. 缓存服务验证 ===")

        cache = CacheManager(backend="memory")

        # 测试用户缓存服务
        print("\n6.1 用户缓存服务")
        user_service = UserCacheService(cache_manager=cache)
        user_data = {
            "id": 1,
            "username": "test_user",
            "email": "test@example.com",
            "password_hash": "should_be_removed",  # 应该被移除
        }
        await user_service.set_user_info(1, user_data)
        cached_user = await user_service.get_user_info(1)

        if "password_hash" not in cached_user:
            self._pass("用户数据脱敏", "密码哈希已从缓存中移除")
        else:
            self._fail("用户数据脱敏", "密码哈希未被移除")

        # 测试文档缓存服务
        print("\n6.2 文档缓存服务")
        doc_service = DocumentCacheService(cache_manager=cache)
        doc_data = {
            "id": 100,
            "title": "测试文档",
            "domain": "tcm",
        }
        await doc_service.set_document_info(100, doc_data)
        cached_doc = await doc_service.get_document_info(100)

        if cached_doc == doc_data:
            self._pass("文档缓存服务", "文档数据缓存正常")
        else:
            self._fail("文档缓存服务", "缓存数据不匹配")

        # 测试搜索缓存服务
        print("\n6.3 搜索缓存服务")
        search_service = SearchCacheService(cache_manager=cache)
        search_result = {
            "query": "中医治疗",
            "results": [{"id": 1, "content": "测试内容"}],
            "total": 1,
        }
        await search_service.set_search_result("中医治疗", search_result, "hybrid", ["tcm"])
        cached_search = await search_service.get_search_result("中医治疗", "hybrid", ["tcm"])

        if cached_search == search_result:
            self._pass("搜索缓存服务", "搜索结果缓存正常")
        else:
            self._fail("搜索缓存服务", "缓存数据不匹配")

        # 测试热词缓存服务
        print("\n6.4 热词缓存服务")
        hotword_service = HotwordCacheService(cache_manager=cache)
        hotwords = [
            {"word": "中药", "pinyin": "zhongyao", "category": "药材"},
            {"word": "方剂", "pinyin": "fangji", "category": "处方"},
        ]
        await hotword_service.set_hotwords("tcm", hotwords)
        cached_hotwords = await hotword_service.get_hotwords("tcm")

        if cached_hotwords == hotwords:
            self._pass("热词缓存服务", "热词数据缓存正常")
        else:
            self._fail("热词缓存服务", "缓存数据不匹配")

        # 测试缓存失效
        print("\n6.5 缓存失效功能")
        await user_service.invalidate_user(1)
        invalidated_user = await user_service.get_user_info(1)
        if invalidated_user is None:
            self._pass("用户缓存失效", "用户相关缓存已清除")
        else:
            self._fail("用户缓存失效", "用户缓存未清除")

        await doc_service.invalidate_document(100)
        invalidated_doc = await doc_service.get_document_info(100)
        if invalidated_doc is None:
            self._pass("文档缓存失效", "文档相关缓存已清除")
        else:
            self._fail("文档缓存失效", "文档缓存未清除")

        await cache.close()

    async def check_cache_decorator(self):
        """检查缓存装饰器"""
        from .cache_manager import CacheManager, cached
        from services.common import cache_manager as cm

        print("\n=== 7. 缓存装饰器验证 ===")

        cache = CacheManager(backend="memory")
        cm.set_cache_manager(cache)

        call_count = {"value": 0}

        @cached(ttl=60, namespace="test")
        async def expensive_function(x: int, y: int) -> int:
            """模拟耗时函数"""
            call_count["value"] += 1
            await asyncio.sleep(0.01)  # 模拟耗时操作
            return x + y

        print("\n7.1 第一次调用（应执行函数）")
        start = time.time()
        result1 = await expensive_function(1, 2)
        elapsed1 = time.time() - start
        print(f"     结果: {result1}, 耗时: {elapsed1:.4f}s, 调用次数: {call_count['value']}")

        print("\n7.2 第二次调用（应从缓存获取）")
        start = time.time()
        result2 = await expensive_function(1, 2)
        elapsed2 = time.time() - start
        print(f"     结果: {result2}, 耗时: {elapsed2:.4f}s, 调用次数: {call_count['value']}")

        if call_count["value"] == 1:
            self._pass("装饰器缓存命中", "第二次调用未执行函数")
        else:
            self._fail("装饰器缓存命中", f"函数被调用了 {call_count['value']} 次")

        if elapsed2 < elapsed1:
            self._pass(
                "装饰器性能提升",
                f"缓存调用 ({elapsed2:.4f}s) 比直接调用 ({elapsed1:.4f}s) 快",
            )
        else:
            self._warn("装饰器性能提升", f"时间差异不明显: {elapsed1:.4f}s vs {elapsed2:.4f}s")

        # 测试不同参数
        print("\n7.3 不同参数调用")
        result3 = await expensive_function(2, 3)
        print(f"     结果: {result3}, 调用次数: {call_count['value']}")

        if call_count["value"] == 2 and result3 == 5:
            self._pass("装饰器参数区分", "不同参数正确触发缓存失效")
        else:
            self._fail("装饰器参数区分", "参数区分不正确")

        await cache.close()

    async def check_rate_limiting(self):
        """检查速率限制功能"""
        from .cache_manager import CacheManager

        print("\n=== 8. 速率限制验证 ===")

        cache = CacheManager(backend="memory")

        print("\n8.1 速率限制 (10次/60秒)")
        identifier = "test_user_rate_limit"
        endpoint = "search"
        limit = 10
        window = 60

        allowed_count = 0
        denied_count = 0

        for i in range(15):
            allowed, remaining = await cache.check_rate_limit(
                identifier, endpoint, limit=limit, window=window
            )
            status = "允许" if allowed else "拒绝"
            print(f"     请求 {i+1}: {status}, 剩余={remaining}")
            if allowed:
                allowed_count += 1
            else:
                denied_count += 1

        if allowed_count == limit and denied_count == 5:
            self._pass("速率限制", f"前 {limit} 次允许，后续请求被拒绝")
        else:
            self._fail(
                "速率限制",
                f"允许 {allowed_count} 次，拒绝 {denied_count} 次（预期: 允许 {limit} 次）",
            )

        await cache.close()

    async def check_pattern_deletion(self):
        """检查模式删除功能"""
        from .cache_manager import CacheManager

        print("\n=== 9. 模式删除验证 ===")

        cache = CacheManager(backend="memory")

        print("\n9.1 设置测试键")
        test_keys = [
            "user:info:1",
            "user:info:2",
            "user:roles:1",
            "doc:info:100",
            "doc:info:200",
        ]
        for key in test_keys:
            await cache.set(key, f"value_{key}")
            print(f"     设置: {key}")

        print("\n9.2 删除用户相关键 (user:*)")
        count = await cache.delete_pattern("user:*")
        print(f"     删除了 {count} 个键")

        if count >= 2:
            self._pass("模式删除 - 用户键", f"删除了 {count} 个用户相关键")
        else:
            self._fail("模式删除 - 用户键", f"只删除了 {count} 个键")

        # 验证文档键未被删除
        doc_value = await cache.get("doc:info:100")
        if doc_value is not None:
            self._pass("模式删除 - 文档键保留", "非匹配模式的键未被删除")
        else:
            self._fail("模式删除 - 文档键保留", "文档键被意外删除")

        await cache.close()

    async def check_namespace_isolation(self):
        """检查命名空间隔离"""
        from .cache_manager import CacheManager

        print("\n=== 10. 命名空间隔离验证 ===")

        cache = CacheManager(backend="memory")

        print("\n10.1 在不同命名空间设置相同键")
        await cache.set("same:key", "value_user", namespace="user")
        await cache.set("same:key", "value_document", namespace="document")

        user_value = await cache.get("same:key", namespace="user")
        doc_value = await cache.get("same:key", namespace="document")

        print(f"     user 命名空间: {user_value}")
        print(f"     document 命名空间: {doc_value}")

        if user_value == "value_user" and doc_value == "value_document":
            self._pass("命名空间隔离", "不同命名空间的值互不影响")
        else:
            self._fail("命名空间隔离", "命名空间隔离失败")

        print("\n10.2 删除单个命名空间")
        await cache.delete("same:key", namespace="user")
        user_value_after = await cache.get("same:key", namespace="user")
        doc_value_after = await cache.get("same:key", namespace="document")

        if user_value_after is None and doc_value_after == "value_document":
            self._pass("命名空间独立删除", "只删除了指定命名空间的键")
        else:
            self._fail("命名空间独立删除", "删除操作影响了其他命名空间")

        await cache.close()

    async def check_cache_statistics(self):
        """检查缓存统计功能"""
        from .cache_manager import CacheManager

        print("\n=== 11. 缓存统计验证 ===")

        cache = CacheManager(backend="memory")

        print("\n11.1 生成缓存活动")
        # 命中
        await cache.set("stats:hit", "value")
        await cache.get("stats:hit")
        await cache.get("stats:hit")

        # 未命中
        await cache.get("stats:miss1")
        await cache.get("stats:miss2")

        print("\n11.2 获取统计信息")
        stats = cache.get_stats()
        print(f"     统计: {stats}")

        if "default" in stats:
            default_stats = stats["default"]
            hits = default_stats.get("hits", 0)
            misses = default_stats.get("misses", 0)

            if hits > 0 and misses > 0:
                self._pass("缓存统计", f"命中: {hits}, 未命中: {misses}")
            else:
                self._fail("缓存统计", "统计计数器未更新")
        else:
            self._fail("缓存统计", "无法获取默认命名空间统计")

        await cache.close()

    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("Redis 缓存层全面验证")
        print("=" * 60)

        # 首先检查 Redis 连接
        await self.check_redis_connection()

        # 运行所有测试
        await self.check_cache_manager_basic()
        await self.check_ttl_strategy()
        await self.check_lru_strategy()
        await self.check_cache_penetration_protection()
        await self.check_cache_services()
        await self.check_cache_decorator()
        await self.check_rate_limiting()
        await self.check_pattern_deletion()
        await self.check_namespace_isolation()
        await self.check_cache_statistics()

        # 打印总结
        self._print_summary()

        # 返回测试结果
        return len(self.results["failed"]) == 0

    def _print_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)

        passed = len(self.results["passed"])
        failed = len(self.results["failed"])
        warnings = len(self.results["warnings"])
        total = passed + failed

        print(f"\n通过: {passed}/{total}")
        print(f"失败: {failed}/{total}")
        print(f"警告: {warnings}")

        if failed > 0:
            print("\n失败的测试:")
            for item in self.results["failed"]:
                print(f"  - {item['test']}: {item['error']}")

        if warnings > 0:
            print("\n警告:")
            for item in self.results["warnings"]:
                print(f"  - {item['test']}: {item['message']}")

        print("\n" + "=" * 60)

        if failed == 0:
            print("所有测试通过!")
        else:
            print(f"有 {failed} 个测试失败，请检查")

        print("=" * 60)


async def main():
    """主函数"""
    validator = CacheValidator()
    success = await validator.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
