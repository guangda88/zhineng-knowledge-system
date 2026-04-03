-- P0级优化: 数据库索引优化
-- 创建日期: 2025-03-25
-- 说明: 添加关键索引以提升查询性能

-- 分类索引
-- 用于按类别查询文档的场景
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);

-- 全文搜索索引
-- 使用GIN索引加速中文全文搜索
DROP INDEX IF EXISTS idx_documents_content_gin;
CREATE INDEX idx_documents_content_gin ON documents USING gin(to_tsvector('chinese', content));

-- 向量索引
-- 使用IVFFlat索引加速向量相似度搜索
-- 注意: 需要pgvector扩展支持
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 复合索引
-- 用于按类别和标题的组合查询
CREATE INDEX IF NOT EXISTS idx_documents_category_title ON documents(category, title);

-- 查看已创建的索引
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'documents';
