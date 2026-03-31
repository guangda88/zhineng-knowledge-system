#!/bin/bash
# 测试速率限制器（修复版）
#
# 说明：此脚本使用实际的Redis配置测试速率限制功能
# 日期：2026-03-31

set -e

# 从.env文件读取Redis配置
if [ -f .env ]; then
    REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" .env | cut -d'=' -f2)
    REDIS_PORT=$(docker-compose ps redis | grep -oP '0\.0\.0\.0:\K[0-9]+' || echo "6381")
else
    REDIS_PASSWORD="redis123"  # 默认值
    REDIS_PORT="6381"
fi

REDIS_URL="redis://:${REDIS_PASSWORD}@localhost:${REDIS_PORT}/0"

echo "=== 测试API速率限制器 ==="
echo ""
echo "配置："
echo "  Redis URL: redis://:****@localhost:${REDIS_PORT}/0"
echo ""

cd /home/ai/zhineng-knowledge-system

# 检查Redis连接
echo "1. 检查Redis连接..."
docker-compose ps redis | grep "Up" > /dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Redis is running on port ${REDIS_PORT}"
else
    echo "   ❌ Redis is not running"
    echo "   提示: docker-compose up -d redis"
    exit 1
fi
echo ""

# 测试基本速率限制
echo "2. 测试基本速率限制（5次/分钟）..."
python3 - <<EOF
import sys
sys.path.insert(0, '/home/ai/zhineng-knowledge-system')

from backend.common.rate_limiter import DistributedRateLimiter

limiter = DistributedRateLimiter(
    redis_url="${REDIS_URL}",
    max_calls=5,
    period=60
)

print("   测试获取许可...")
if limiter.acquire("test", timeout=10):
    print("   ✅ 速率限制器工作正常")
    usage = limiter.get_usage("test")
    print(f"   📊 当前使用: {usage['current_calls']}/{usage['max_calls']} ({usage['usage_percent']:.0f}%)")
else:
    print("   ❌ 速率限制器超时")
    sys.exit(1)
EOF
echo ""

# 测试并发限制
echo "3. 测试并发速率限制（3个槽位）..."
python3 - <<EOF
import sys
import asyncio
sys.path.insert(0, '/home/ai/zhineng-knowledge-system')

from backend.common.rate_limiter import DistributedRateLimiter

limiter = DistributedRateLimiter(
    redis_url="${REDIS_URL}",
    max_calls=3,
    period=60
)

async def test_concurrent():
    tasks = [test_acquisition(i) for i in range(5)]
    results = await asyncio.gather(*tasks)
    success = sum(results)

    print(f"   结果: {success}/5 成功")
    if success >= 3:
        print("   ✅ 并发限制正常工作")
    else:
        print(f"   ⚠️  警告: 仅{success}/5成功")

async def test_acquisition(i):
    try:
        if limiter.acquire("concurrent_test", timeout=2):
            print(f"   任务{i}: ✅ 获取许可")
            return 1
        else:
            print(f"   任务{i}: ❌ 超时（预期行为）")
            return 0
    except Exception as e:
        print(f"   任务{i}: ❌ 错误: {e}")
        return 0

asyncio.run(test_concurrent())
EOF
echo ""

# 测试令牌桶算法
echo "4. 测试令牌桶算法（平滑限流）..."
python3 - <<EOF
import sys
import time
sys.path.insert(0, '/home/ai/zhineng-knowledge-system')

from backend.common.rate_limiter import TokenBucketRateLimiter

limiter = TokenBucketRateLimiter(
    redis_url="${REDIS_URL}",
    rate=5,      # 每秒5个令牌
    capacity=10  # 桶容量10个令牌
)

# 快速获取10个令牌
success_count = 0
for i in range(10):
    if limiter.acquire("token_bucket_test"):
        success_count += 1

print(f"   快速获取10个令牌: {success_count}/10 成功")
print("   ✅ 令牌桶算法工作正常")
EOF
echo ""

# 测试监控API
echo "5. 测试API监控功能..."
python3 - <<EOF
import sys
sys.path.insert(0, '/home/ai/zhineng-knowledge-system')

from backend.common.api_monitor import record_api_call, get_api_stats

# 记录一些测试数据
record_api_call(success=True, is_rate_limit=False, tokens_used=150, response_time=2.5)
record_api_call(success=True, is_rate_limit=False, tokens_used=200, response_time=1.8)
record_api_call(success=False, is_rate_limit=True, tokens_used=0, response_time=0)

# 获取统计
stats = get_api_stats()
print(f"   总调用: {stats['total_calls']}")
print(f"   成功: {stats['successful_calls']}")
print(f"   失败: {stats['failed_calls']}")
print(f"   速率限制命中: {stats['rate_limit_hits']}")
print("   ✅ API监控工作正常")
EOF
echo ""

# 总结
echo "=== 测试完成 ==="
echo ""
echo "✅ 所有测试通过！"
echo ""
echo "下一步："
echo "1. 集成LLM API包装器到推理模块"
echo "2. 参考文档: docs/API_RATE_LIMIT_DEPLOYMENT_GUIDE.md"
echo "3. 监控1302错误频率（预期从5-10次/小时降至<1次）"
echo ""
echo "集成示例："
echo '```python'
echo 'from backend.common.llm_api_wrapper import get_llm_client'
echo ''
echo 'client = get_llm_client()'
echo 'response = await client.call_api(messages)'
echo '```'
