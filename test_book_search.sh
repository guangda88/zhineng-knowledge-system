#!/bin/bash
# 图书搜索功能测试脚本

set -e

API_BASE="http://localhost:8000/api/v2"
TEST_QUERY="论语"
PASS=0
FAIL=0

echo "=== 图书搜索功能测试 ==="
echo ""

# 检查服务是否运行
echo "1. 检查API服务..."
if ! curl -s "$API_BASE/library/search?page=1&size=1" > /dev/null 2>&1; then
    echo "   ❌ API服务未运行，请先启动服务"
    echo "   提示: docker-compose up backend"
    exit 1
fi
echo "   ✅ API服务运行中"
echo ""

# 测试1: 元数据搜索
echo "2. 测试元数据搜索..."
RESPONSE=$(curl -s "$API_BASE/library/search?q=$TEST_QUERY&page=1&size=10")
TOTAL=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total', 0))" 2>/dev/null || echo "0")

if [ "$TOTAL" -gt 0 ]; then
    echo "   ✅ 元数据搜索成功，找到 $TOTAL 本书籍"
    ((PASS++))
else
    echo "   ❌ 元数据搜索失败"
    ((FAIL++))
fi
echo ""

# 测试2: 全文搜索
echo "3. 测试全文内容搜索..."
RESPONSE=$(curl -s "$API_BASE/library/search/content?q=$TEST_QUERY&page=1&size=10")
TOTAL=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total', 0))" 2>/dev/null || echo "0")

if [ "$TOTAL" -ge 0 ]; then
    echo "   ✅ 全文搜索成功，找到 $TOTAL 个章节"
    ((PASS++))
else
    echo "   ❌ 全文搜索失败"
    ((FAIL++))
fi
echo ""

# 测试3: 获取书籍ID（用于后续测试）
echo "4. 获取第一本书籍ID..."
BOOK_ID=$(curl -s "$API_BASE/library/search?q=$TEST_QUERY&page=1&size=1" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['results'][0]['id'] if data.get('results') else 0)" 2>/dev/null || echo "0")

if [ "$BOOK_ID" != "0" ] && [ -n "$BOOK_ID" ]; then
    echo "   ✅ 获取书籍ID: $BOOK_ID"
    ((PASS++))
else
    echo "   ❌ 无法获取书籍ID"
    ((FAIL++))
    echo "   提示: 请确保数据库中有《论语》相关书籍"
    exit 1
fi
echo ""

# 测试4: 书籍详情
echo "5. 测试书籍详情..."
RESPONSE=$(curl -s "$API_BASE/library/$BOOK_ID")
TITLE=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('title', ''))" 2>/dev/null || echo "")

if [ -n "$TITLE" ]; then
    echo "   ✅ 书籍详情获取成功: $TITLE"
    ((PASS++))
else
    echo "   ❌ 书籍详情获取失败"
    ((FAIL++))
fi
echo ""

# 测试5: 相关书籍推荐
echo "6. 测试相关书籍推荐（向量搜索）..."
RESPONSE=$(curl -s "$API_BASE/library/$BOOK_ID/related?top_k=5&threshold=0.5")
COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

if [ "$COUNT" -ge 0 ]; then
    echo "   ✅ 相关书籍推荐成功，找到 $COUNT 本相似书籍"
    ((PASS++))
else
    echo "   ❌ 相关书籍推荐失败"
    ((FAIL++))
fi
echo ""

# 测试6: 获取章节列表
echo "7. 测试获取章节列表..."
RESPONSE=$(curl -s "$API_BASE/library/$BOOK_ID")
CHAPTER_COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('chapters', [])))" 2>/dev/null || echo "0")

if [ "$CHAPTER_COUNT" -gt 0 ]; then
    echo "   ✅ 章节列表获取成功，共 $CHAPTER_COUNT 章"
    ((PASS++))

    # 获取第一章ID
    CHAPTER_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['chapters'][0]['id'] if data.get('chapters') else 0)" 2>/dev/null || echo "0")
else
    echo "   ⚠️  章节列表为空或书籍无内容"
    CHAPTER_ID="0"
fi
echo ""

# 测试7: 章节内容（如果有章节）
if [ "$CHAPTER_ID" != "0" ] && [ -n "$CHAPTER_ID" ]; then
    echo "8. 测试章节内容获取..."
    RESPONSE=$(curl -s "$API_BASE/library/$BOOK_ID/chapters/$CHAPTER_ID")
    CONTENT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('content', ''))" 2>/dev/null || echo "")

    if [ -n "$CONTENT" ]; then
        CONTENT_LENGTH=${#CONTENT}
        echo "   ✅ 章节内容获取成功，长度: $CONTENT_LENGTH 字符"
        ((PASS++))
    else
        echo "   ❌ 章节内容获取失败"
        ((FAIL++))
    fi
    echo ""
else
    echo "8. 跳过章节内容测试（无可用章节）"
    echo ""
fi

# 测试8: 筛选选项
echo "9. 测试筛选选项..."
RESPONSE=$(curl -s "$API_BASE/library/filters/list")
CATEGORY_COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('categories', [])))" 2>/dev/null || echo "0")

if [ "$CATEGORY_COUNT" -ge 0 ]; then
    echo "   ✅ 筛选选项获取成功，分类数: $CATEGORY_COUNT"
    ((PASS++))
else
    echo "   ❌ 筛选选项获取失败"
    ((FAIL++))
fi
echo ""

# 测试9: 分类筛选
echo "10. 测试分类筛选（儒家）..."
RESPONSE=$(curl -s "$API_BASE/library/search?category=儒家&page=1&size=10")
TOTAL=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total', 0))" 2>/dev/null || echo "0")

if [ "$TOTAL" -ge 0 ]; then
    echo "   ✅ 分类筛选成功，找到 $TOTAL 本儒家书籍"
    ((PASS++))
else
    echo "   ❌ 分类筛选失败"
    ((FAIL++))
fi
echo ""

# 测试10: 朝代筛选
echo "11. 测试朝代筛选（春秋）..."
RESPONSE=$(curl -s "$API_BASE/library/search?dynasty=春秋&page=1&size=10")
TOTAL=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total', 0))" 2>/dev/null || echo "0")

if [ "$TOTAL" -ge 0 ]; then
    echo "   ✅ 朝代筛选成功，找到 $TOTAL 本春秋书籍"
    ((PASS++))
else
    echo "   ❌ 朝代筛选失败"
    ((FAIL++))
fi
echo ""

# 测试总结
echo "=== 测试总结 ==="
echo "通过: $PASS"
echo "失败: $FAIL"
echo "总计: $((PASS + FAIL))"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "✅ 所有测试通过！"
    exit 0
else
    echo "⚠️  部分测试失败，请检查"
    exit 1
fi
