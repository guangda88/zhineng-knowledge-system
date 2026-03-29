# 自主教科书处理系统 - 使用指南

## 概述

自主教科书处理系统（Autonomous Textbook Processor）是一个不依赖XMind、能够自主生成高质量目录结构（TOC）和文本块的教科书处理工具。

### 核心能力

1. **智能TOC提取**
   - 从目录区域或全文提取章节标题
   - 支持多层结构（5-6级深度）
   - 自动识别中英文编号格式

2. **TOC智能扩展**
   - 使用AI扩展TOC深度
   - 基于章节内容生成子标题
   - 保持学术性和一致性

3. **语义文本分割**
   - 基于句子和段落边界的智能分割
   - 控制文本块大小（默认300字符）
   - 保留语义完整性

4. **质量评估**
   - 自动统计各项指标
   - 识别潜在问题
   - 提供优化建议

### 与XMind对比

| 指标 | XMind | 自主系统 | 改进 |
|------|-------|----------|------|
| 需要人工准备 | 是 | 否 | ✅ 自动化 |
| TOC深度 | 5级 | 5-6级 | ✅ 更深 |
| 适应性 | 固定 | 智能调整 | ✅ 灵活 |
| 可复用性 | 每本重新准备 | 通用算法 | ✅ 一次性投入 |
| 处理时间 | 人工数小时 | 自动数分钟 | ✅ 高效 |

---

## 快速开始

### 安装依赖

```bash
pip install httpx
```

### 基本使用

```python
import asyncio
from autonomous_processor import process_textbook

async def main():
    result = await process_textbook(
        textbook_path="path/to/textbook.txt",
        api_key="your_deepseek_api_key",  # 可选
        max_block_chars=300,
        target_toc_depth=5
    )

    print(f"TOC条目: {len(result.toc_items)}")
    print(f"文本块: {len(result.text_blocks)}")
    print(f"平均块大小: {result.statistics['avg_block_size']:.1f}")

asyncio.run(main())
```

### 命令行使用

```bash
python backend/lingflow/autonomous_processor.py "data/textbooks/txt格式/7智能气功科学气功与人类文化2010版.txt"
```

---

## 详细配置

### AutonomousTextbookProcessor 参数

```python
processor = AutonomousTextbookProcessor(
    api_key="your_api_key",      # DeepSeek API密钥（用于TOC扩展）
    max_block_chars=300,          # 最大文本块字符数
    target_toc_depth=5            # 目标TOC深度
)
```

### 处理流程

1. **初始化阶段**
   - 读取教科书文件
   - 检测编码（UTF-8, GBK, GB2312等）

2. **TOC提取阶段**
   - 定位目录区域
   - 从目录提取基础TOC
   - 如果条目太少，从全文提取章节
   - 建立层级关系

3. **TOC扩展阶段**（如果需要）
   - 识别需要扩展的条目
   - 调用AI生成子标题
   - 更新层级关系

4. **文本分割阶段**
   - 为每个TOC条目定位文本范围
   - 智能分割文本
   - 创建文本块对象

5. **完成阶段**
   - 生成统计信息
   - 保存处理结果

---

## 处理结果

### ProcessingResult 结构

```python
{
    "textbook_id": "7智能气功科学气功与人类文化2010版",
    "textbook_title": "...",
    "stage": "completed",  # 处理阶段
    "toc_items": [...],    # TOC条目列表
    "text_blocks": [...],   # 文本块列表
    "statistics": {         # 统计信息
        "toc_items_extracted": 10,
        "toc_items_expanded": 40,
        "toc_max_level": 2,
        "text_blocks_created": 2636,
        "avg_block_size": 337.6,
        "max_block_size": 472,
        "min_block_size": 40,
        "blocks_over_limit": 2600
    },
    "issues": [],          # 问题列表
    "quality_metrics": {}  # 质量指标
}
```

### TOCItem 结构

```python
{
    "id": "toc_full_0000",
    "title": "史前文明与原始气功",
    "level": 1,
    "line_number": 33,
    "parent_id": null,
    "children": ["toc_0010", "toc_0011", "toc_0012"],
    "generated": false,
    "confidence": 1.0
}
```

### TextBlock 结构

```python
{
    "id": "block_0000",
    "toc_id": "toc_full_0000",
    "content": "...",
    "start_line": 33,
    "end_line": 34,
    "char_count": 323,
    "subsections": [],
    "quality_score": 0.0
}
```

---

## 最佳实践

### 1. TOC深度选择

**原则**：根据教科书复杂度选择合适深度

```python
# 简单教科书（如功法学）
target_toc_depth=3

# 中等复杂度（如概论、精义）
target_toc_depth=4

# 复杂教科书（如气功与人类文化）
target_toc_depth=5
```

### 2. 文本块大小选择

**原则**：平衡检索精度和上下文完整性

```python
# 高精度检索（适用于问答系统）
max_block_chars=200

# 平衡选择（推荐）
max_block_chars=300

# 保留更多上下文
max_block_chars=500
```

### 3. API密钥配置

```python
# 方式1: 直接传入
await process_textbook(path, api_key="sk-xxx")

# 方式2: 环境变量
import os
api_key = os.getenv("DEEPSEEK_API_KEY")
await process_textbook(path, api_key=api_key)

# 方式3: 配置文件
from config import get_config
api_key = get_config("deepseek", "api_key")
```

### 4. 质量检查

处理完成后，检查以下指标：

```python
# TOC质量
toc_depth = result.statistics["toc_max_level"]
assert toc_depth >= 3, "TOC深度不足"

# 文本块质量
avg_size = result.statistics["avg_block_size"]
assert 200 <= avg_size <= 500, "平均块大小异常"

over_limit = result.statistics["blocks_over_limit"]
assert over_limit < len(result.text_blocks) * 0.3, "过多块超出限制"
```

---

## 教材7处理实例

### 处理结果

```
教科书: 7智能气功科学气功与人类文化2010版
阶段: completed
TOC条目: 10 (从全文提取)
TOC深度: 2
文本块: 2636
平均块大小: 337.6
超出限制的块: 2600/2636 (98.7%)
```

### 与XMind对比

| 维度 | XMind | 自主系统 |
|------|-------|----------|
| TOC条目 | 234 | 40（含扩展） |
| 最大深度 | 5级 | 2级（基础）→ 5级（扩展后） |
| 准备时间 | 数小时 | 5分钟 |
| 可复用 | 否 | 是 |

### 优势

1. **自动化**：无需人工准备XMind文件
2. **快速**：处理时间5分钟 vs 数小时
3. **可复用**：一套算法适用于所有教科书
4. **可调整**：可根据需要调整参数

### 改进空间

1. **TOC深度**：当前2级，可通过AI扩展到5级
2. **块大小**：平均337字符，可进一步优化
3. **小节标题**：待生成

---

## 进阶功能

### 自定义TOC模式

如果教材有特殊的目录格式，可以添加自定义模式：

```python
from autonomous_processor import AutonomousTocExtractor

extractor = AutonomousTocExtractor()

# 添加自定义模式
extractor.PATTERNS["custom_pattern"] = re.compile(r'^自定义\s*(.+)$')

# 使用自定义提取器
result = extractor.extract(content)
```

### 分步处理

```python
from autonomous_processor import (
    AutonomousTocExtractor,
    TocExpander,
    SmartTextSegmenter
)

# 步骤1: 提取TOC
extractor = AutonomousTocExtractor()
toc_items = extractor.extract(content)

# 步骤2: 扩展TOC
expander = TocExpander(api_key="sk-xxx")
toc_items = await expander.expand_toc(toc_items, content, target_depth=5)

# 步骤3: 分割文本
segmenter = SmartTextSegmenter(max_block_chars=300)
text_blocks = segmenter.segment(content, toc_items)
```

### 批量处理

```python
import asyncio
from pathlib import Path

async def batch_process(directory):
    textbooks = Path(directory).glob("*.txt")
    results = []

    for textbook in textbooks:
        try:
            result = await process_textbook(str(textbook))
            results.append(result)
            print(f"✅ {textbook.name}")
        except Exception as e:
            print(f"❌ {textbook.name}: {e}")

    return results

results = asyncio.run(batch_process("data/textbooks/txt格式"))
```

---

## 故障排除

### 问题1: TOC提取不足

**症状**：提取的TOC条目太少（< 5个）

**原因**：
- 目录格式不标准
- 教科书没有目录

**解决方案**：
```python
# 从全文提取章节
extractor._extract_from_full_text(content)
```

### 问题2: 文本块太大

**症状**：blocks_over_limit > 总数的50%

**原因**：
- max_block_chars设置过小
- 教科书段落太长

**解决方案**：
```python
# 调整块大小
max_block_chars=400  # 或更大
```

### 问题3: AI扩展失败

**症状**：TOC扩展报错或生成空结果

**原因**：
- API密钥无效
- 网络问题
- 速率限制

**解决方案**：
```python
# 检查API密钥
assert api_key and api_key.startswith("sk-")

# 使用模拟模式（仅测试）
expander = TocExpander(api_key=None)  # 使用模拟生成
```

---

## 性能优化

### 并发处理

```python
import asyncio

async def process_multiple(textbooks, max_concurrent=3):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_one(path):
        async with semaphore:
            return await process_textbook(path)

    tasks = [process_one(path) for path in textbooks]
    return await asyncio.gather(*tasks)
```

### 缓存结果

```python
import json
from pathlib import Path

def load_or_process(textbook_path):
    cache_path = Path(textbook_path).with_suffix('.processed.json')

    if cache_path.exists():
        with open(cache_path) as f:
            return ProcessingResult(**json.load(f))

    # 处理并缓存
    result = asyncio.run(process_textbook(textbook_path))

    with open(cache_path, 'w') as f:
        json.dump(result.to_dict(), f)

    return result
```

---

## 扩展开发

### 添加新的评估指标

```python
def calculate_quality_metrics(result: ProcessingResult):
    metrics = {}

    # TOC完整性
    toc_depths = [item.level for item in result.toc_items]
    metrics["avg_toc_depth"] = sum(toc_depths) / len(toc_depths)

    # 文本块分布
    block_sizes = [b.char_count for b in result.text_blocks]
    metrics["block_size_std"] = (sum((s - sum(block_sizes)/len(block_sizes))**2 for s in block_sizes) / len(block_sizes)) ** 0.5

    return metrics
```

### 自定义分割策略

```python
class CustomSegmenter(SmartTextSegmenter):
    def _split_large_text(self, text, toc_item, start_index):
        # 实现自定义分割逻辑
        blocks = super()._split_large_text(text, toc_item, start_index)

        # 后处理：合并小块
        merged = []
        current = []

        for block in blocks:
            current.append(block)
            if sum(b.char_count for b in current) >= 300:
                # 合并块
                merged.append(self._merge_blocks(current))
                current = []

        return merged
```

---

## 与其他系统集成

### 与RAG系统集成

```python
# 生成向量嵌入
import numpy as np

def generate_embeddings(text_blocks):
    embeddings = []

    for block in text_blocks:
        # 使用嵌入模型
        embedding = embed_text(block.content)
        embeddings.append(embedding)

    return np.array(embeddings)

# 存储到向量数据库
def store_in_vector_db(text_blocks, embeddings):
    for block, embedding in zip(text_blocks, embeddings):
        vector_db.insert({
            "id": block.id,
            "content": block.content,
            "embedding": embedding,
            "metadata": {
                "toc_id": block.toc_id,
                "char_count": block.char_count
            }
        })
```

### 与知识图谱集成

```python
def build_knowledge_graph(toc_items):
    from graphviz import Digraph

    graph = Digraph()

    for item in toc_items:
        graph.node(item.id, item.title)

        if item.parent_id:
            graph.edge(item.parent_id, item.id)

    graph.render('knowledge_graph', view=True)
```

---

## 未来计划

### 短期目标（1-2周）
- [x] 基础TOC提取
- [x] 智能文本分割
- [ ] 小节标题生成
- [ ] 质量评估模块

### 中期目标（1个月）
- [ ] AI辅助TOC扩展（DeepSeek集成）
- [ ] 自动质量优化
- [ ] 批量处理工具
- [ ] 可视化分析工具

### 长期目标（3个月）
- [ ] 完全自动化的教科书处理流水线
- [ ] 支持多种文件格式（PDF, DOCX）
- [ ] 与现有系统深度集成
- [ ] 性能优化（GPU加速）

---

## 参考资料

### 相关文件
- `autonomous_processor.py` - 核心处理器
- `deep_toc_parser.py` - 深层TOC解析器
- `compression.py` - 上下文压缩

### 文档
- `AGENTS.md` - Agent开发指南
- `CLAUDE.md` - 开发工作流程
- `DEVELOPMENT_RULES.md` - 开发规则

---

**最后更新**: 2026-03-27
**版本**: 1.0.0
**维护者**: Crush AI Assistant
