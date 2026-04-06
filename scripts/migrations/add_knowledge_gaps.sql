-- 知识缺口感知系统
-- 记录低置信度/零命中的用户查询，作为知识闭环的数据源头

CREATE TABLE IF NOT EXISTS knowledge_gaps (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    category VARCHAR(50),
    result_count INTEGER NOT NULL DEFAULT 0,
    best_score FLOAT,
    source VARCHAR(20) NOT NULL DEFAULT 'hybrid',
    -- hybrid, vector, bm25, ask
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    -- open, acknowledged, filling, resolved, dismissed
    resolved_by INTEGER REFERENCES documents(id),
    hit_count INTEGER NOT NULL DEFAULT 1,
    first_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_knowledge_gaps_status ON knowledge_gaps(status, last_seen DESC);
CREATE INDEX idx_knowledge_gaps_query ON knowledge_gaps USING gin(to_tsvector('simple', query));
CREATE INDEX idx_knowledge_gaps_category ON knowledge_gaps(category);
CREATE INDEX idx_knowledge_gaps_hit_count ON knowledge_gaps(hit_count DESC);
