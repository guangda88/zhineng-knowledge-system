# 文字处理工程流 - 快速开始指南

**5分钟上手文字处理工程流**

---

## 🎯 概述

文字处理工程流（团队A）提供完整的文本处理、向量检索和RAG问答能力。

### 核心功能

1. **文本处理** - 智能分块、编码检测、元数据提取
2. **向量嵌入** - 本地BGE模型 + CLIProxyAI远程API
3. **混合检索** - 向量检索 + 全文检索 + RRF融合
4. **RAG问答** - 检索增强生成，支持多轮对话
5. **文本标注** - 6种标注类型，支持协作和导出

---

## 🚀 快速开始

### 步骤1: 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 启动数据库
docker-compose up -d postgres

# 初始化数据库
python scripts/init_db.py
```

### 步骤2: 文本处理

```python
from backend.services.text_processor import EnhancedTextProcessor

# 创建处理器
processor = EnhancedTextProcessor(
    max_chunk_size=300,
    overlap=50
)

# 处理文本文件
chunks, metadata = await processor.process_file(
    "data/textbooks/智能气功基础.txt"
)

print(f"处理完成: {len(chunks)} 个块")
print(f"标题: {metadata.title}")
```

### 步骤3: 向量化

```python
from backend.services.enhanced_vector_service import TextVectorizer

# 创建向量化器
vectorizer = TextVectorizer(
    preferred_provider="local"  # 使用本地BGE模型
)

# 向量化文本块
vectors, stats = await vectorizer.vectorize_text_blocks(
    [chunk.content for chunk in chunks]
)

print(f"向量化完成: {len(vectors)} 个向量")
print(f"平均质量: {stats['avg_quality']:.2f}")
```

### 步骤4: 检索

```python
from backend.services.hybrid_retrieval import HybridRetrievalService

# 创建检索服务
retrieval_service = HybridRetrievalService(
    db_pool=db_pool,
    enable_cache=True
)

# 混合检索
result = await retrieval_service.search(
    query="什么是混元灵通？",
    method="hybrid",
    top_k=5
)

print(f"找到 {len(result.results)} 个结果")
for r in result.results:
    print(f"- {r.title}: {r.score:.2f}")
```

### 步骤5: RAG问答

```python
from backend.services.rag_pipeline import RAGPipeline

# 创建RAG管道
rag_pipeline = RAGPipeline(
    db_pool=db_pool,
    retrieval_service=retrieval_service
)

# 问答
answer = await rag_pipeline.query(
    question="什么是混元灵通？",
    retrieval_method="hybrid"
)

print(f"答案: {answer.answer}")
print(f"质量: {answer.quality}")
print(f"引用: {len(answer.citations)} 个")
```

---

## 📖 完整示例

### 示例1: 端到端文本处理

```python
import asyncio
from pathlib import Path

async def process_textbook(file_path: str):
    """完整的教材处理流程"""

    # 1. 文本处理
    processor = EnhancedTextProcessor()
    chunks, metadata = await processor.process_file(file_path)

    print(f"✅ 文本处理: {len(chunks)} 个块")
    print(f"   标题: {metadata.title}")

    # 2. 向量化
    vectorizer = TextVectorizer()
    vectors, stats = await vectorizer.vectorize_text_blocks(
        [c.content for c in chunks]
    )

    print(f"✅ 向量化: {len(vectors)} 个向量")
    print(f"   平均质量: {stats['avg_quality']:.2f}")

    # 3. 存储到数据库（伪代码）
    # for chunk, vector in zip(chunks, vectors):
    #     await save_to_db(chunk, vector)

    return chunks, vectors

# 运行
chunks, vectors = asyncio.run(
    process_textbook("data/textbooks/智能气功基础.txt")
)
```

### 示例2: 智能问答系统

```python
import asyncio

async def qa_system():
    """智能问答系统"""

    # 创建RAG管道
    rag = RAGPipeline(db_pool=db_pool)

    # 第一轮
    answer1 = await rag.query("什么是混元灵通？")
    print(f"Q1: {answer1.query}")
    print(f"A1: {answer1.answer}\n")

    # 第二轮（使用上下文）
    answer2 = await rag.query("它有什么特点？")
    print(f"Q2: {answer2.query}")
    print(f"A2: {answer2.answer}\n")

    # 第三轮
    answer3 = await rag.query("如何练习？")
    print(f"Q3: {answer3.query}")
    print(f"A3: {answer3.answer}")

    # 查看对话历史
    history = rag.get_conversation_summary()
    print(f"\n对话轮数: {len(history)}")

# 运行
asyncio.run(qa_system())
```

### 示例3: 文本标注

```python
from backend.services.text_annotation_service import TextAnnotationService

# 创建标注服务
annotation_service = TextAnnotationService(db_session)

# 创建标注
annotation = annotation_service.create_annotation(
    text_block_id=1,
    annotation_type="keyword",
    content="混元灵通",
    start_pos=0,
    end_pos=4,
    importance="high",
    created_by="user1"
)

print(f"创建标注: {annotation.id}")

# 添加评论
comment = annotation_service.add_comment(
    annotation_id=annotation.id,
    content="这是核心概念",
    author="user2"
)

# 导出标注
json_content, mime_type = annotation_service.export_annotations(
    format="json",
    text_block_id=1
)

# 保存到文件
with open("annotations.json", "w") as f:
    f.write(json_content)
```

---

## 🔧 配置优化

### 向量嵌入提供商选择

```python
from backend.services.enhanced_vector_service import EmbeddingProvider

# 场景1: 优先本地模型（快速、免费）
vectorizer = TextVectorizer(
    preferred_provider=EmbeddingProvider.LOCAL
)

# 场景2: 混合模式（短文本用远程，长文本用本地）
vectorizer = TextVectorizer(
    preferred_provider=EmbeddingProvider.HYBRID
)

# 场景3: 优先质量（使用远程API）
vectorizer = TextVectorizer(
    preferred_provider=EmbeddingProvider.REMOTE,
    remote_api_key="your_api_key"
)
```

### 检索策略选择

```python
# 场景1: 纯向量检索（语义相似）
result = await retrieval_service.search(
    query="混元灵通理论",
    method="vector",
    top_k=10
)

# 场景2: 纯全文检索（精确匹配）
result = await retrieval_service.search(
    query="混元灵通",
    method="fulltext",
    top_k=10
)

# 场景3: 混合检索（推荐）
result = await retrieval_service.search(
    query="混元灵通理论是什么",
    method="hybrid",
    top_k=10
)
```

---

## 📊 性能基准

### 文本处理性能

| 操作 | 输入大小 | 处理时间 | 吞吐量 |
|------|---------|---------|--------|
| 文本分块 | 10万字 | 1秒 | 10万字/秒 |
| 向量嵌入 | 100个文本 | 5秒 | 20个/秒 |
| 混合检索 | 1万文档 | 0.5秒 | 2000次/秒 |
| RAG问答 | 5个上下文 | 2秒 | 0.5次/秒 |

### 优化建议

1. **批量处理**: 使用`embed_batch()`提高吞吐量
2. **启用缓存**: 检索服务启用缓存减少重复查询
3. **异步并发**: 使用`asyncio.gather()`并行处理

---

## ⚠️ 常见问题

### Q1: 向量嵌入太慢

**解决方案**:
```python
# 1. 使用批量处理
vectors, stats = await vectorizer.vectorize_text_blocks(
    texts,
    batch_size=64  # 增加批大小
)

# 2. 使用本地模型而非远程API
vectorizer = TextVectorizer(preferred_provider="local")
```

### Q2: 检索结果不准确

**解决方案**:
```python
# 1. 使用混合检索而非单一方法
result = await retrieval_service.search(
    query,
    method="hybrid"  # 而非 "vector" 或 "fulltext"
)

# 2. 调整top_k和阈值
result = await retrieval_service.search(
    query,
    top_k=20,  # 增加候选数量
    threshold=0.3  # 降低阈值
)
```

### Q3: RAG答案质量低

**解决方案**:
```python
# 1. 增加上下文
answer = await rag.query(
    question,
    top_k=10,  # 增加检索数量
    max_context_length=3000  # 增加上下文长度
)

# 2. 检查答案质量
if answer.quality in ["low", "failed"]:
    # 重新查询或使用不同方法
    answer = await rag.query(
        question,
        retrieval_method="vector"  # 尝试不同的检索方法
    )
```

---

## 📚 相关文档

- [完整API文档](TEXT_PROCESSING_API.md)
- [双工程流开发计划](DUAL_WORKFLOW_TEXT_AUDIO_PLAN.md)
- [CLIProxyAI集成指南](CLIProxyAPI_INTEGRATION_GUIDE.md)

---

## 🎓 进阶话题

### 自定义分块策略

```python
class CustomChunker(SemanticChunker):
    """自定义分块器"""

    def chunk(self, text: str, metadata=None):
        # 实现自定义分块逻辑
        # 例如：按章节分块
        chapters = re.split(r'第.*章', text)
        # ...
        return chunks
```

### 自定义检索融合算法

```python
class CustomFusion(ResultFusion):
    """自定义融合算法"""

    @staticmethod
    def custom_fusion(vector_results, fulltext_results):
        # 实现自定义融合逻辑
        # 例如：加权组合
        # ...
        return fused_results
```

---

**版本**: v1.0.0

**最后更新**: 2026-04-01

**众智混元，万法灵通** ⚡🚀
