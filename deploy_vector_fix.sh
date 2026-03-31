#!/bin/bash
# 向量搜索修复 - 快速部署脚本
# 修复 BGE-M3 嵌入服务并重建文档向量

set -e  # 遇到错误立即退出

echo "======================================"
echo "向量搜索修复 - 快速部署"
echo "======================================"
echo ""

# 检查是否在项目根目录
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 步骤 1: 停止服务
echo "🛑 步骤 1/6: 停止当前服务..."
docker-compose down

# 步骤 2: 备份数据（可选）
echo ""
echo "💾 步骤 2/6: 备份数据库..."
read -p "是否备份数据库? (y/n): " backup
if [ "$backup" = "y" ]; then
    backup_file="backup_$(date +%Y%m%d_%H%M%S).sql"
    docker exec zhineng-postgres pg_dump -U zhineng zhineng_kb > "$backup_file"
    echo "✅ 备份完成: $backup_file"
else
    echo "⏭️  跳过备份"
fi

# 步骤 3: 创建模型缓存目录
echo ""
echo "📁 步骤 3/6: 创建模型缓存目录..."
mkdir -p data/embedding_cache
echo "✅ 目录创建完成"

# 步骤 4: 启动服务
echo ""
echo "🚀 步骤 4/6: 启动所有服务（包括新的嵌入服务）..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo ""
echo "📊 服务状态:"
docker-compose ps

# 步骤 5: 等待嵌入服务就绪
echo ""
echo "⏳ 步骤 5/6: 等待嵌入服务加载模型..."
echo "（首次启动需要下载 BGE-M3 模型，约 2-3 GB，可能需要几分钟）"

max_wait=300  # 最多等待 5 分钟
wait_time=0
while [ $wait_time -lt $max_wait ]; do
    if curl -s http://localhost:8001/health | grep -q "healthy"; then
        echo ""
        echo "✅ 嵌入服务已就绪！"
        break
    fi

    # 显示进度
    if [ $((wait_time % 30)) -eq 0 ] && [ $wait_time -gt 0 ]; then
        echo "⏳ 已等待 ${wait_time} 秒..."
    fi

    sleep 5
    wait_time=$((wait_time + 5))
done

if [ $wait_time -ge $max_wait ]; then
    echo ""
    echo "❌ 错误: 嵌入服务启动超时"
    echo "请查看日志: docker-compose logs embedding"
    exit 1
fi

# 显示模型信息
echo ""
echo "📋 模型信息:"
curl -s http://localhost:8001/info | jq .

# 步骤 6: 重建文档向量
echo ""
echo "🔄 步骤 6/6: 重建文档向量..."
read -p "是否现在重建所有文档的向量? (y/n): " rebuild

if [ "$rebuild" = "y" ]; then
    echo "🔄 开始重建..."
    python3 scripts/rebuild_embeddings.py

    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ 向量重建完成！"
    else
        echo ""
        echo "❌ 向量重建失败，请查看错误日志"
        exit 1
    fi
else
    echo "⏭️  跳过向量重建"
    echo ""
    echo "💡 提示: 稍后可以运行以下命令重建向量:"
    echo "   python3 scripts/rebuild_embeddings.py"
fi

# 完成
echo ""
echo "======================================"
echo "✅ 部署完成！"
echo "======================================"
echo ""
echo "📊 服务状态:"
docker-compose ps | grep -E "NAME|embedding|api|postgres|redis"
echo ""
echo "🔗 有用的链接:"
echo "   嵌入服务健康检查: http://localhost:8001/health"
echo "   嵌入服务信息: http://localhost:8001/info"
echo "   API 健康检查: http://localhost:8000/health"
echo ""
echo "📝 查看日志:"
echo "   docker-compose logs -f embedding    # 嵌入服务日志"
echo "   docker-compose logs -f api          # API 服务日志"
echo ""
echo "🧪 测试向量搜索:"
echo '   curl -X POST http://localhost:8000/api/v1/search -H "Content-Type: application/json" -d '"'"'{"query":"气功的呼吸方法","category":"气功","top_k":5}'"'"
echo ""
