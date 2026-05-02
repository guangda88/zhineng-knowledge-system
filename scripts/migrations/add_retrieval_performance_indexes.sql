-- 检索性能优化 - 创建缺失的索引
-- 创建时间: 2026-04-21
-- 优先级: CRITICAL - 直接影响查询性能

-- ============================================================
-- PART 1: 向量相似度索引 (IVFFlat for pgvector)
-- ============================================================
-- 使用余弦距离的 IVFFlat 索引
-- lists 参数设为 100（适用于约100万条记录）
-- 向量维度为 512（BAAI/bge-small-zh-v1.5）

-- documents 表向量索引
CREATE INDEX IF NOT EXISTS idx_documents_embedding_ivfflat
    ON documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- guoxue_content 表向量索引
CREATE INDEX IF NOT EXISTS idx_guoxue_content_embedding_ivfflat
    ON guoxue_content
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- textbook_blocks_v2 表向量索引
CREATE INDEX IF NOT EXISTS idx_textbook_blocks_v2_embedding_ivfflat
    ON textbook_blocks_v2
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- doc_chunks 表向量索引
CREATE INDEX IF NOT EXISTS idx_doc_chunks_embedding_ivfflat
    ON doc_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- audio_segments 表向量索引
CREATE INDEX IF NOT EXISTS idx_audio_segments_embedding_ivfflat
    ON audio_segments
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ============================================================
-- PART 2: GIN 索引 (BM25 全文检索)
-- ============================================================
-- 用于 ts_rank 函数的全文检索

-- documents 表 GIN 索引
CREATE INDEX IF NOT EXISTS idx_documents_search_vector_gin
    ON documents
    USING GIN (search_vector);

-- guoxue_content 表 GIN 索引
CREATE INDEX IF NOT EXISTS idx_guoxue_content_search_vector_gin
    ON guoxue_content
    USING GIN (search_vector);

-- textbook_blocks_v2 表 GIN 索引
CREATE INDEX IF NOT EXISTS idx_textbook_blocks_v2_search_vector_gin
    ON textbook_blocks_v2
    USING GIN (search_vector);

-- doc_chunks 表 GIN 索引
CREATE INDEX IF NOT EXISTS idx_doc_chunks_search_vector_gin
    ON doc_chunks
    USING GIN (search_vector);

-- ============================================================
-- PART 3: 复合索引 (上下文加载优化)
-- ============================================================

-- textbook_blocks_v2 上下文加载复合索引
CREATE INDEX IF NOT EXISTS idx_textbook_blocks_v2_node_order
    ON textbook_blocks_v2 (node_id, block_order);

-- doc_chunks 上下文加载复合索引
CREATE INDEX IF NOT EXISTS idx_doc_chunks_doc_index
    ON doc_chunks (doc_id, chunk_index);

-- ============================================================
-- 验证索引创建
-- ============================================================

SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN (
    'documents', 'guoxue_content', 'textbook_blocks_v2',
    'doc_chunks', 'audio_segments'
)
ORDER BY tablename, indexname;

-- ============================================================
-- 分析表以更新统计信息
-- ============================================================

ANALYZE documents;
ANALYZE guoxue_content;
ANALYZE textbook_blocks_v2;
ANALYZE doc_chunks;
ANALYZE audio_segments;

-- ============================================================
-- 性能影响预估
-- ============================================================
-- 创建 IVFFlat 索引:
--   - documents (~10万条): 约 2-3 分钟
--   - guoxue_content (26万条): 约 4-5 分钟
--   - textbook_blocks_v2 (6.4万条): 约 1-2 分钟
--   - doc_chunks (~1万条): 约 10-20 秒
--   - audio_segments (未知): 视数据量
--
-- 总计: 约 8-12 分钟 (串行)
--
-- 创建 GIN 索引:
--   - 每个约 30-60 秒
--
-- 总预计时间: 约 12-15 分钟
