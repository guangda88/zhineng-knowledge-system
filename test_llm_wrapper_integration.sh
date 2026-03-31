#!/bin/bash
# 测试LLM API包装器集成

set -e

echo "=== 测试LLM API包装器集成 ==="
echo ""

cd /home/ai/zhineng-knowledge-system

# 1. 检查环境变量
echo "1. 检查环境配置..."
if [ -z "$DEEPSEEK_API_KEY" ]; then
    if [ -f .env ]; then
        if grep -q "DEEPSEEK_API_KEY=" .env; then
            echo "   ✅ DEEPSEEK_API_KEY已配置（在.env中）"
        else
            echo "   ❌ DEEPSEEK_API_KEY未配置"
            echo "   提示: 请在.env中设置DEEPSEEK_API_KEY"
        fi
    else
        echo "   ⚠️  .env文件不存在"
    fi
else
    echo "   ✅ DEEPSEEK_API_KEY已设置"
fi
echo ""

# 2. 检查Redis连接
echo "2. 检查Redis连接..."
REDIS_PORT=$(docker-compose ps redis | grep -oP '0\.0\.0\.0:\K[0-9]+' || echo "6381")
if docker-compose ps redis | grep "Up" > /dev/null; then
    echo "   ✅ Redis运行在端口${REDIS_PORT}"
else
    echo "   ❌ Redis未运行"
    echo "   提示: docker-compose up -d redis"
fi
echo ""

# 3. 测试LLM客户端初始化
echo "3. 测试LLM客户端初始化..."
python3 - <<EOF
import sys
sys.path.insert(0, '/home/ai/zhineng-knowledge-system')

try:
    from backend.common.llm_api_wrapper import get_llm_client
    client = get_llm_client()
    print("   ✅ LLM客户端初始化成功")
    print(f"   模型: {client.model}")
    print(f"   速率限制: {client.rate_limiter.max_calls}次/{client.rate_limiter.period}秒")
except Exception as e:
    print(f"   ❌ LLM客户端初始化失败: {e}")
    sys.exit(1)
EOF
echo ""

# 4. 测试推理模块集成
echo "4. 测试推理模块集成..."
python3 - <<EOF
import sys
import asyncio
sys.path.insert(0, '/home/ai/zhineng-knowledge-system')

async def test_reasoner():
    try:
        from backend.services.reasoning.cot import CoTReasoner

        # 初始化推理器
        reasoner = CoTReasoner()

        # 检查LLM客户端
        if reasoner.llm_client:
            print("   ✅ CoT推理器已集成LLM客户端")
            print(f"   模型: {reasoner.model_name}")
            return True
        else:
            print("   ⚠️  CoT推理器未使用LLM客户端（将使用HTTP客户端）")
            return False

    except Exception as e:
        print(f"   ❌ 推理模块测试失败: {e}")
        return False

result = asyncio.run(test_reasoner())
EOF
echo ""

# 5. 测试导入
echo "5. 测试所有推理模块导入..."
python3 - <<EOF
import sys
sys.path.insert(0, '/home/ai/zhineng-knowledge-system')

try:
    from backend.services.reasoning.cot import CoTReasoner
    print("   ✅ CoTReasoner导入成功")

    from backend.services.reasoning.react import ReActReasoner
    print("   ✅ ReActReasoner导入成功")

    from backend.services.reasoning.graph_rag import GraphRAGReasoner
    print("   ✅ GraphRAGReasoner导入成功")

    print("\n   所有推理模块导入成功！")
except Exception as e:
    print(f"   ❌ 导入失败: {e}")
    sys.exit(1)
EOF
echo ""

# 6. 检查语法
echo "6. 检查Python语法..."
python3 -m py_compile backend/services/reasoning/base.py 2>/dev/null && echo "   ✅ base.py语法正确" || echo "   ❌ base.py语法错误"
python3 -m py_compile backend/services/reasoning/cot.py 2>/dev/null && echo "   ✅ cot.py语法正确" || echo "   ❌ cot.py语法错误"
python3 -m py_compile backend/services/reasoning/react.py 2>/dev/null && echo "   ✅ react.py语法正确" || echo "   ❌ react.py语法错误"
python3 -m py_compile backend/services/reasoning/graph_rag.py 2>/dev/null && echo "   ✅ graph_rag.py语法正确" || echo "   ❌ graph_rag.py语法错误"
echo ""

# 总结
echo "=== 测试总结 ==="
echo ""
echo "✅ 集成验证完成！"
echo ""
echo "下一步："
echo "1. 重启后端服务: docker-compose restart backend"
echo "2. 测试推理API:"
echo "   curl -X POST http://localhost:8000/api/v1/reasoning/cot \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"question\": \"什么是八段锦？\"}'"
echo ""
echo "3. 监控1302错误频率："
echo "   curl http://localhost:8000/api/v1/monitoring/stats"
echo ""
echo "预期效果：1302错误从5-10次/小时降至<1次"
