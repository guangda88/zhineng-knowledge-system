# Embedding模型选型方案

> 灵知(lingzhi) — 2026-06-11
> 当前模型: bge-small-zh (512维), κ=0.820(Top-1)/0.932(Top-3)

## 候选模型

| 模型 | 维度 | 参数量 | 中文能力 | GPU需求 | 推理速度 | 本地路径 |
|------|------|--------|---------|---------|---------|---------|
| bge-small-zh | 512 | 33M | 强 | 低(GTX1660Ti可) | ~1000q/s | /data/models/bge-small-zh |
| bge-large-zh-v1.5 | 1024 | 326M | 更强 | 中(~2GB VRAM) | ~300q/s | 待下载 |
| bge-m3 | 1024 | 568M | 多语言+跨语言 | 高(~3GB VRAM) | ~200q/s | 待下载 |

## 评估方法

### Step 1: 下载候选模型

```bash
# bge-large-zh-v1.5
python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-large-zh-v1.5')
model.save('/data/models/bge-large-zh-v1.5')
"

# bge-m3
python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-m3')
model.save('/data/models/bge-m3')
"
```

### Step 2: 生成候选embedding

对50题评估集的query + top-10结果的chunk_id，分别用3个模型生成embedding。
不重新embed全库（1.75M chunks太大），只对比query→候选的排序质量。

```python
# 伪代码
for model_name in ['bge-small-zh', 'bge-large-zh-v1.5', 'bge-m3']:
    model = SentenceTransformer(model_path)
    for query in EVAL_QUERIES:
        q_emb = model.encode(query['query'])
        # 对top-10结果重新计算similarity
        # 比较排序变化
```

### Step 3: 对比指标

| 指标 | 说明 | 权重 |
|------|------|------|
| κ (Top-1) | 主要指标 | 40% |
| κ (Top-3) | 召回质量 | 30% |
| 困难题命中率 | 跨域/模糊查询 | 15% |
| 推理延迟 | 用户体验 | 10% |
| 显存占用 | 部署成本 | 5% |

### Step 4: 决策矩阵

| 场景 | 推荐 |
|------|------|
| κ提升>5% + 延迟<2x | 升级模型 + 全库re-embed |
| κ提升<5% | 保持bge-small-zh + 优化检索策略 |
| bge-m3跨语言优势显著 | 仅query端用m3，doc端保持small-zh（双塔） |

## 全库Re-embed方案（如果决定升级）

1. **分批处理**: 1.75M chunks / batch_size=64 ≈ 27K批次
2. **GPU加速**: 宿主机CUDA，~1000q/s，预计18小时
3. **零停机**: 新embedding写入新列，完成后原子切换
4. **回退**: 保留旧embedding列，必要时一键回退

```sql
ALTER TABLE doc_chunks ADD COLUMN embedding_new vector(1024);
-- 批量填充后
ALTER TABLE doc_chunks RENAME COLUMN embedding TO embedding_old;
ALTER TABLE doc_chunks RENAME COLUMN embedding_new TO embedding;
```

## 当前瓶颈判断

κ=0.820的主要瓶颈可能不在embedding模型，而在：
1. **评估集设计**: 50题中部分query与doc标题语义距离大
2. **检索策略**: hybrid权重(vector=0.7, bm25=0.3)可能非最优
3. **数据覆盖**: 气功占82%可能影响跨域平衡

建议先优化检索策略（2-3天），如果κ仍<0.90再投入模型选型（1周）。

## 时间估算

| 步骤 | 时间 |
|------|------|
| 下载2个模型 | 2h (网络) |
| 50题对比评估 | 1h |
| 结果分析+报告 | 2h |
| 全库re-embed(如需) | 18h (GPU) |
| 总计 | ~3天 |
