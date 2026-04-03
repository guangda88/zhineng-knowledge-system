-- 情报系统数据库迁移
-- 版本: 1.0.0
-- 日期: 2026-03-31
-- 目的: 采集与灵知系统相关的技术/数据集前沿趋势（GitHub、npm、HuggingFace）

-- ============================================
-- 表1: 情报条目
-- ============================================
CREATE TABLE IF NOT EXISTS intelligence_items (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(20) NOT NULL,  -- 'github', 'npm', 'huggingface'
    source_id VARCHAR(255) NOT NULL,  -- 来源平台唯一ID（如 GitHub repo full_name）

    -- 基本信息
    name VARCHAR(500) NOT NULL,
    description TEXT,
    url TEXT,
    language VARCHAR(50),  -- 编程语言（GitHub）

    -- 标签与分类
    tags TEXT[] DEFAULT '{}',

    -- 指标（各平台不同）
    metrics JSONB DEFAULT '{}',
    -- GitHub: {stars, forks, open_issues, updated_at}
    -- npm: {weekly_downloads, dependents, version}
    -- HuggingFace: {downloads, likes, model_type}

    -- 相关性评分
    relevance_score INTEGER DEFAULT 0,  -- 0-100
    relevance_category VARCHAR(20) DEFAULT 'monitoring',  -- 'high_value', 'medium_value', 'monitoring'
    relevance_reason TEXT,

    -- 用户交互
    is_read BOOLEAN DEFAULT FALSE,
    notes TEXT,
    starred BOOLEAN DEFAULT FALSE,

    -- 时间戳
    collected_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- 约束
    CONSTRAINT valid_source CHECK (source IN ('github', 'npm', 'huggingface')),
    CONSTRAINT valid_relevance_category CHECK (relevance_category IN ('high_value', 'medium_value', 'monitoring')),
    CONSTRAINT valid_relevance_score CHECK (relevance_score BETWEEN 0 AND 100)
);

-- 唯一约束：同一来源平台不重复采集
CREATE UNIQUE INDEX idx_intelligence_items_source_id ON intelligence_items(source, source_id);

-- 查询索引
CREATE INDEX idx_intelligence_items_source ON intelligence_items(source);
CREATE INDEX idx_intelligence_items_relevance_category ON intelligence_items(relevance_category);
CREATE INDEX idx_intelligence_items_relevance_score ON intelligence_items(relevance_score DESC);
CREATE INDEX idx_intelligence_items_collected_at ON intelligence_items(collected_at DESC);
CREATE INDEX idx_intelligence_items_is_read ON intelligence_items(is_read) WHERE NOT is_read;
CREATE INDEX idx_intelligence_items_starred ON intelligence_items(starred) WHERE starred;

-- ============================================
-- 表2: 采集任务记录
-- ============================================
CREATE TABLE IF NOT EXISTS intelligence_collections (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(20) NOT NULL,

    -- 任务状态
    status VARCHAR(20) DEFAULT 'running',  -- 'running', 'completed', 'failed'
    keywords TEXT[] DEFAULT '{}',

    -- 结果统计
    items_found INTEGER DEFAULT 0,
    items_new INTEGER DEFAULT 0,
    items_updated INTEGER DEFAULT 0,

    -- 错误信息
    error_message TEXT,

    -- 耗时（毫秒）
    duration_ms INTEGER,

    -- 时间戳
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,

    CONSTRAINT valid_collection_source CHECK (source IN ('github', 'npm', 'huggingface', 'all')),
    CONSTRAINT valid_collection_status CHECK (status IN ('running', 'completed', 'failed'))
);

CREATE INDEX idx_intel_collections_source ON intelligence_collections(source);
CREATE INDEX idx_intel_collections_status ON intelligence_collections(status);
CREATE INDEX idx_intel_collections_started_at ON intelligence_collections(started_at DESC);

-- ============================================
-- 自动更新触发器
-- ============================================
CREATE OR REPLACE FUNCTION update_intelligence_item_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_intelligence_item_updated_at
    BEFORE UPDATE ON intelligence_items
    FOR EACH ROW
    EXECUTE FUNCTION update_intelligence_item_updated_at();

-- ============================================
-- 视图：情报摘要统计
-- ============================================
CREATE OR REPLACE VIEW v_intelligence_summary AS
SELECT
    source,
    relevance_category,
    COUNT(*) AS total_items,
    COUNT(*) FILTER (WHERE NOT is_read) AS unread_items,
    COUNT(*) FILTER (WHERE starred) AS starred_items,
    ROUND(AVG(relevance_score), 1) AS avg_relevance_score,
    MAX(collected_at) AS last_collected_at
FROM intelligence_items
GROUP BY source, relevance_category
ORDER BY source, relevance_category;

-- ============================================
-- 视图：最近采集趋势
-- ============================================
CREATE OR REPLACE VIEW v_intelligence_trends AS
SELECT
    DATE_TRUNC('day', collected_at) AS date,
    source,
    COUNT(*) AS items_collected,
    COUNT(*) FILTER (WHERE relevance_category = 'high_value') AS high_value_count,
    AVG(relevance_score) AS avg_score
FROM intelligence_items
WHERE collected_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', collected_at), source
ORDER BY date DESC, source;

-- ============================================
-- 注释
-- ============================================
COMMENT ON TABLE intelligence_items IS '情报条目：采集到的技术/数据集前沿信息';
COMMENT ON TABLE intelligence_collections IS '采集任务记录：追踪每次情报采集的执行情况';

-- ============================================
-- 完成
-- ============================================
