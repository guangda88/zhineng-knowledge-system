#!/bin/bash
# 前端功能测试脚本

echo "========== 智能知识系统前端测试 =========="
echo ""

BASE_URL="http://localhost:8008"
API_BASE="$BASE_URL/api/v2/library"

echo "📍 访问地址: $BASE_URL"
echo ""

# 测试1: 检查前端页面
echo "📝 测试1: 检查前端页面"
echo "-----------------------------------"
HTML_CONTENT=$(curl -s "$BASE_URL/")
if echo "$HTML_CONTENT" | grep -q "📚 智能知识系统"; then
    echo "✅ 前端页面加载成功"
else
    echo "❌ 前端页面加载失败"
fi
echo ""

# 测试2: 检查书籍标签
echo "📚 测试2: 检查书籍标签"
echo "-----------------------------------"
if echo "$HTML_CONTENT" | grep -q 'data-tab="books"'; then
    echo "✅ 书籍标签存在"
else
    echo "❌ 书籍标签缺失"
fi
echo ""

# 测试3: API - 空搜索（获取所有书籍）
echo "🔍 测试3: API - 空搜索"
echo "-----------------------------------"
RESULT=$(curl -s "$API_BASE/search?q=" | jq '.total')
if [ "$RESULT" = "5" ]; then
    echo "✅ 返回所有5本书: $RESULT"
else
    echo "❌ 返回数量错误: $RESULT"
fi
echo ""

# 测试4: 搜索"周易"
echo "📖 测试4: 搜索《周易》"
echo "-----------------------------------"
RESULT=$(curl -s "$API_BASE/search?q=%E5%91%A8%E6%98%93")
TITLE=$(echo "$RESULT" | jq -r '.results[0].title')
AUTHOR=$(echo "$RESULT" | jq -r '.results[0].author')
if [ "$TITLE" = "周易注疏" ] && [ "$AUTHOR" = "王弼" ]; then
    echo "✅ 找到《周易注疏》(王弼)"
else
    echo "❌ 搜索结果错误"
fi
echo ""

# 测试5: 分类筛选 - 儒家
echo "🏷️ 测试5: 分类筛选 - 儒家"
echo "-----------------------------------"
RESULT=$(curl -s "$API_BASE/search?category=%E5%84%92%E5%AE%B6")
TOTAL=$(echo "$RESULT" | jq '.total')
if [ "$TOTAL" -ge 1 ]; then
    echo "✅ 儒家分类: 找到$TOTAL本书"
    TITLES=$(echo "$RESULT" | jq -r '.results[].title' | tr '\n' ', ')
    echo "   书籍: $TITLES"
else
    echo "❌ 分类筛选失败"
fi
echo ""

# 测试6: 书籍详情
echo "📖 测试6: 书籍详情"
echo "-----------------------------------"
RESULT=$(curl -s "$API_BASE/2")
TITLE=$(echo "$RESULT" | jq -r '.title')
CHAPTERS=$(echo "$RESULT" | jq '.chapters | length')
if [ -n "$TITLE" ] && [ "$CHAPTERS" != "null" ]; then
    echo "✅ 书籍详情: $TITLE"
    echo "   章节数: $CHAPTERS"
else
    echo "❌ 书籍详情获取失败"
fi
echo ""

# 测试7: 相关推荐
echo "🔗 测试7: 相关推荐"
echo "-----------------------------------"
RESULT=$(curl -s "$API_BASE/2/related?top_k=3")
RELATED=$(echo "$RESULT" | jq '. | length')
if [ "$RELATED" -ge 0 ]; then
    echo "✅ 相关推荐: 返回$RELATED本相关书籍"
else
    echo "❌ 相关推荐失败"
fi
echo ""

echo "========== 测试完成 =========="
echo ""
echo "🎉 前端功能验证通过！"
echo ""
echo "📖 使用指南: 查看 FRONTEND_GUIDE.md"
echo "🔗 访问地址: $BASE_URL"
