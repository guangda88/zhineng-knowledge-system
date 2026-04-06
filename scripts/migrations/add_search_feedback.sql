-- 检索反馈闭环
-- 用户对搜索结果的反馈，用于评估检索质量、修正缺口判定、优化排序

CREATE TABLE IF NOT EXISTS search_feedback (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    doc_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    feedback_type VARCHAR(20) NOT NULL,
    -- helpful, not_helpful, wrong, irrelevant, partial
    rating SMALLINT CHECK (rating >= 1 AND rating <= 5),
    category VARCHAR(50),
    search_method VARCHAR(20),
    -- vector, bm25, hybrid, ask
    rank_position INTEGER,
    similarity_score FLOAT,
    comment TEXT,
    session_id VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_search_feedback_query ON search_feedback(query);
CREATE INDEX idx_search_feedback_doc_id ON search_feedback(doc_id) WHERE doc_id IS NOT NULL;
CREATE INDEX idx_search_feedback_type ON search_feedback(feedback_type);
CREATE INDEX idx_search_feedback_created_at ON search_feedback(created_at DESC);
