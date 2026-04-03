-- ============================================================
-- Phase 2/3: 内容提取管道 + 知识图谱 + 维度标注
-- 数据库迁移脚本
-- 创建日期: 2026-04-02
-- ============================================================

BEGIN;

-- ============================================================
-- 1. sys_books 表扩展：内容提取状态 + 维度标注
-- ============================================================

-- 内容提取状态
ALTER TABLE sys_books ADD COLUMN IF NOT EXISTS extraction_status VARCHAR(20) DEFAULT 'pending';
-- pending, extracting, extracted, failed, skipped

ALTER TABLE sys_books ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMPTZ;
ALTER TABLE sys_books ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
ALTER TABLE sys_books ADD COLUMN IF NOT EXISTS content_length INTEGER DEFAULT 0;
ALTER TABLE sys_books ADD COLUMN IF NOT EXISTS extraction_error TEXT;

-- 维度标注 (JSONB)
ALTER TABLE sys_books ADD COLUMN IF NOT EXISTS qigong_dims JSONB DEFAULT '{}'::jsonb;

-- 云端路径 (data.db 对账结果)
ALTER TABLE sys_books ADD COLUMN IF NOT EXISTS cloud_path TEXT;
ALTER TABLE sys_books ADD COLUMN IF NOT EXISTS cross_ref_status VARCHAR(20) DEFAULT 'unmatched';
-- unmatched, matched, deduplicated

COMMENT ON COLUMN sys_books.extraction_status IS '内容提取状态: pending/extracting/extracted/failed/skipped';
COMMENT ON COLUMN sys_books.qigong_dims IS '智能气功维度标注 (V4.0)，JSONB格式';
COMMENT ON COLUMN sys_books.cloud_path IS 'data.db 云端路径 (对账结果)';
COMMENT ON COLUMN sys_books.cross_ref_status IS 'data.db 对账状态: unmatched/matched/deduplicated';

-- ============================================================
-- 2. sys_books 新索引
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_sys_books_extraction_status
    ON sys_books(extraction_status) WHERE extraction_status IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sys_books_qigong_dims
    ON sys_books USING gin(qigong_dims) WHERE qigong_dims != '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_sys_books_cross_ref
    ON sys_books(cross_ref_status) WHERE cross_ref_status IS NOT NULL;

-- ============================================================
-- 3. 书籍内容表（提取的文本内容）
-- ============================================================

CREATE TABLE IF NOT EXISTS sys_book_contents (
    id BIGSERIAL PRIMARY KEY,
    sys_book_id INTEGER NOT NULL REFERENCES sys_books(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    char_count INTEGER DEFAULT 0,
    chinese_char_count INTEGER DEFAULT 0,
    content_hash VARCHAR(64) NOT NULL,
    extraction_method VARCHAR(50) NOT NULL,
    -- pymupdf, pdfplumber, python-docx, txt_direct, djvu, asr, ocr
    extraction_time_ms INTEGER,
    quality_score FLOAT DEFAULT 0,
    chunks_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_sys_book_contents_book UNIQUE(sys_book_id)
);

CREATE INDEX IF NOT EXISTS idx_sys_book_contents_method
    ON sys_book_contents(extraction_method);

CREATE INDEX IF NOT EXISTS idx_sys_book_contents_hash
    ON sys_book_contents(content_hash);

COMMENT ON TABLE sys_book_contents IS 'sys_books 提取的文本内容';

-- ============================================================
-- 4. 书籍内容块表（向量化分块）
-- ============================================================

CREATE TABLE IF NOT EXISTS sys_book_chunks (
    id BIGSERIAL PRIMARY KEY,
    sys_book_id INTEGER NOT NULL REFERENCES sys_books(id) ON DELETE CASCADE,
    content_id BIGINT REFERENCES sys_book_contents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    char_count INTEGER DEFAULT 0,
    embedding vector(512),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sys_book_chunks_book
    ON sys_book_chunks(sys_book_id, chunk_index);

CREATE INDEX IF NOT EXISTS idx_sys_book_chunks_embedding
    ON sys_book_chunks USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100)
    WHERE embedding IS NOT NULL;

COMMENT ON TABLE sys_book_chunks IS 'sys_books 内容分块（用于向量检索）';

-- ============================================================
-- 5. 知识图谱实体表
-- ============================================================

CREATE TABLE IF NOT EXISTS kg_entities (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    -- 功法, 穴位, 概念, 动作, 脏腑, 人物, 典籍, 流派
    description TEXT,
    aliases TEXT[] DEFAULT '{}',
    properties JSONB DEFAULT '{}'::jsonb,
    source_table VARCHAR(50) DEFAULT 'sys_books',
    source_ids INTEGER[] DEFAULT '{}',
    mention_count INTEGER DEFAULT 0,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_kg_entities_name_type UNIQUE(name, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_kg_entities_type ON kg_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_kg_entities_name ON kg_entities(name);
CREATE INDEX IF NOT EXISTS idx_kg_entities_source ON kg_entities(source_table);

COMMENT ON TABLE kg_entities IS '知识图谱实体表';

-- ============================================================
-- 6. 知识图谱关系表
-- ============================================================

CREATE TABLE IF NOT EXISTS kg_relations (
    id BIGSERIAL PRIMARY KEY,
    source_entity_id BIGINT NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    target_entity_id BIGINT NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    relation_type VARCHAR(100) NOT NULL,
    -- 包含, 相关, 治疗, 属于, 引用, 演变, 对应
    weight FLOAT DEFAULT 1.0,
    evidence TEXT,
    source_table VARCHAR(50) DEFAULT 'sys_books',
    source_ids INTEGER[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_kg_relation UNIQUE(source_entity_id, target_entity_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_kg_relations_source ON kg_relations(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_relations_target ON kg_relations(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_relations_type ON kg_relations(relation_type);

COMMENT ON TABLE kg_relations IS '知识图谱关系表';

-- ============================================================
-- 7. 内容提取任务表
-- ============================================================

CREATE TABLE IF NOT EXISTS extraction_tasks (
    id BIGSERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    -- batch_extract, single_extract, batch_tag, kg_build, cross_ref
    status VARCHAR(20) DEFAULT 'pending',
    -- pending, running, completed, failed, cancelled
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    config JSONB DEFAULT '{}'::jsonb,
    result_summary JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_extraction_tasks_status ON extraction_tasks(status);
CREATE INDEX IF NOT EXISTS idx_extraction_tasks_type ON extraction_tasks(task_type);

COMMENT ON TABLE extraction_tasks IS '内容提取/打标/图谱构建任务表';

-- ============================================================
-- 8. 领域关联表（跨领域知识关联）
-- ============================================================

CREATE TABLE IF NOT EXISTS domain_associations (
    id BIGSERIAL PRIMARY KEY,
    domain_a VARCHAR(50) NOT NULL,
    domain_b VARCHAR(50) NOT NULL,
    association_type VARCHAR(50) NOT NULL,
    -- 共享概念, 理论借鉴, 实践应用, 历史关联
    entity_a_id BIGINT REFERENCES kg_entities(id) ON DELETE SET NULL,
    entity_b_id BIGINT REFERENCES kg_entities(id) ON DELETE SET NULL,
    description TEXT,
    evidence TEXT,
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_domain_assoc_domains
    ON domain_associations(domain_a, domain_b);

COMMENT ON TABLE domain_associations IS '跨领域知识关联表';

COMMIT;
