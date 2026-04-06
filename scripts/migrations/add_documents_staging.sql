-- 知识临时区 (documents_staging)
-- 灵克/灵通问道整理的知识先存此处，审核后发布到 documents 表
-- 这是"第一个反射弧"的入库环节：缺口 → 整理 → 暂存 → 审核 → 发布

CREATE TABLE IF NOT EXISTS documents_staging (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50),
    tags TEXT[] DEFAULT '{}',
    -- 来源追踪
    source VARCHAR(50) NOT NULL DEFAULT 'manual',
    -- manual, lingke, lingtong_wendao, api, gap_fill
    source_ref JSONB DEFAULT '{}',
    -- {"gap_id": 42, "discussion_id": "xxx"} 等
    -- 审核流程
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- draft → submitted → reviewing → approved → published / rejected
    quality_score FLOAT,
    -- 自动质量评估 (0-1)
    gap_id INTEGER REFERENCES knowledge_gaps(id) ON DELETE SET NULL,
    submitted_by VARCHAR(100),
    -- 灵克, 灵通问道, admin 等
    reviewed_by VARCHAR(100),
    review_notes TEXT,
    published_doc_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    -- 发布后回填 documents.id
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_staging_status ON documents_staging(status, created_at DESC);
CREATE INDEX idx_staging_gap_id ON documents_staging(gap_id) WHERE gap_id IS NOT NULL;
CREATE INDEX idx_staging_source ON documents_staging(source);
CREATE INDEX idx_staging_category ON documents_staging(category);
CREATE INDEX idx_staging_created_at ON documents_staging(created_at DESC);
