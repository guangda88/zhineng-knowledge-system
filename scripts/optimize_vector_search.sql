-- 向量搜索优化SQL脚本
-- 为books表的embedding列创建IVFFlat索引

-- 检查pgvector扩展
SELECT * FROM pg_extension WHERE extname = 'vector';

-- 检查当前表结构
\d books

-- 查看当前向量数据统计
SELECT
    COUNT(*) as total_books,
    COUNT(embedding) as books_with_embedding,
    ROUND(COUNT(embedding)::NUMERIC / COUNT(*) * 100, 2) as coverage_percent
FROM books;

-- 创建IVFFlat索引（推荐用于精确度优先的场景）
-- 参数说明：
--   - lists: 聚类中心数量，建议设置为 rows/1000
--   - 对于10万条数据，lists=100是较好的起点
CREATE INDEX CONCURRENTLY IF NOT EXISTS books_embedding_ivfflat_idx
ON books USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 或者创建HNSW索引（推荐用于速度优先的场景）
-- 参数说明：
--   - m: 每个节点的最大连接数（默认16，范围2-100）
--   - ef_construction: 构建时的搜索范围（默认64，范围4-400）
-- DROP INDEX IF EXISTS books_embedding_hnsw_idx;
-- CREATE INDEX CONCURRENTLY books_embedding_hnsw_idx
-- ON books USING hnsw (embedding vector_cosine_ops)
-- WITH (m = 16, ef_construction = 64);

-- 分析查询计划（测试索引效果）
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, author, category, dynasty,
       1 - (embedding <=> '[0.1, 0.2, ...]'::vector) as similarity
FROM books
WHERE embedding IS NOT NULL
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;

-- 性能对比：使用向量搜索
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, 1 - (embedding <=> '[0.1, 0.2, ...]'::vector) as similarity
FROM books
WHERE embedding IS NOT NULL
  AND 1 - (embedding <=> '[0.1, 0.2, ...]'::vector) > 0.7
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;

-- 查看索引使用情况
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'books';

-- 查看索引大小
SELECT
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid::regclass)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND relname = 'books'
  AND indexname LIKE '%embedding%';

-- 维护建议：定期VACUUM ANALYZE
VACUUM ANALYZE books;

-- 监控查询性能
SELECT
    schemaname,
    tablename,
    indexrelname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND relname = 'books'
  AND indexrelname LIKE '%embedding%';

-- 备注：
-- 1. IVFFlat索引适合：
--    - 数据量较大（>10万条）
--    - 需要高精确度
--    - 更新频率不高
--
-- 2. HNSW索引适合：
--    - 查询速度优先
--    - 数据更新频繁
--    - 内存充足
--
-- 3. 索引维护：
--    - 定期运行 VACUUM ANALYZE
--    - 监控索引大小和性能
--    - 根据数据量调整lists参数
