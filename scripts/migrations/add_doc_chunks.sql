-- doc_chunks: 文档分块表
-- 用于对 documents 表中的长文档进行分块检索
-- 配合 HNSW 向量索引和 GIN 全文索引

CREATE TABLE IF NOT EXISTS doc_chunks (
    id SERIAL PRIMARY KEY,
    doc_id INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    start_offset INT,
    end_offset INT,
    embedding vector(512),
    search_vector TSVECTOR,
    char_count INT GENERATED ALWAYS AS (length(content)) STORED,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    UNIQUE(doc_id, chunk_index)
);

-- HNSW 向量索引（分块级别精确语义搜索）
CREATE INDEX IF NOT EXISTS idx_doc_chunks_embedding
    ON doc_chunks USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

-- GIN 全文索引（分块级别关键词搜索）
CREATE INDEX IF NOT EXISTS idx_doc_chunks_search_vector
    ON doc_chunks USING gin (search_vector);

-- 父文档快速查找
CREATE INDEX IF NOT EXISTS idx_doc_chunks_doc_id
    ON doc_chunks (doc_id);

-- 触发器：自动更新 updated_at
CREATE OR REPLACE FUNCTION update_doc_chunks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_doc_chunks_updated_at ON doc_chunks;
CREATE TRIGGER trg_doc_chunks_updated_at
    BEFORE UPDATE ON doc_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_doc_chunks_updated_at();

-- 统计视图
CREATE OR REPLACE VIEW v_doc_chunks_stats AS
SELECT
    count(*) AS total_chunks,
    count(DISTINCT doc_id) AS chunked_documents,
    count(embedding) AS chunks_with_embedding,
    count(search_vector) AS chunks_with_search_vector,
    round(avg(length(content))::numeric, 1) AS avg_chunk_chars
FROM doc_chunks;
