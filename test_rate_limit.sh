#!/bin/bash
echo "=== 测试API速率限制器 ==="
echo ""
python3 -c "
import sys
sys.path.insert(0, '.')

from backend.common.rate_limiter import DistributedRateLimiter

limiter = DistributedRateLimiter(max_calls=5, period=60)
if limiter.acquire('test', timeout=10):
    print('✅ Rate limiter is working!')
else:
    print('❌ Rate limiter timeout')
"
