-- 灵知系统 - 找书查书功能数据库初始化脚本（修正版）
-- 修正了向量维度、全文搜索配置等问题

-- ========== 扩展检查 ==========
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========== 1. 数据源表 ==========
CREATE TABLE IF NOT EXISTS data_sources (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name_zh VARCHAR(200) NOT NULL,
    name_en VARCHAR(200),
    base_url VARCHAR(500),
    api_url VARCHAR(500),
    description TEXT,
    access_type VARCHAR(20) DEFAULT 'external',  -- local/external/api
    region VARCHAR(50),
    languages VARCHAR(200),  -- 逗号分隔的ISO 639代码
    category VARCHAR(50),    -- 气功/中医/儒家/其他

    -- 能力标记
    supports_search BOOLEAN DEFAULT false,
    supports_fulltext BOOLEAN DEFAULT false,
    has_local_fulltext BOOLEAN DEFAULT false,
    has_remote_fulltext BOOLEAN DEFAULT false,
    supports_api BOOLEAN DEFAULT false,

    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_data_sources_code ON data_sources(code);
CREATE INDEX idx_data_sources_category ON data_sources(category);
CREATE INDEX idx_data_sources_active ON data_sources(is_active);

-- ========== 2. 书籍表 ==========
CREATE TABLE IF NOT EXISTS books (
    id SERIAL PRIMARY KEY,

    -- 标题信息
    title VARCHAR(500) NOT NULL,
    title_alternative VARCHAR(500),
    subtitle VARCHAR(500),

    -- 作者信息
    author VARCHAR(200),
    author_alt VARCHAR(200),
    translator VARCHAR(200),

    -- 元数据
    category VARCHAR(50),  -- 气功/中医/儒家
    dynasty VARCHAR(50),
    year VARCHAR(50),
    language VARCHAR(10) DEFAULT 'zh',

    -- 数据源关联
    source_id INTEGER REFERENCES data_sources(id),
    source_uid VARCHAR(200),
    source_url VARCHAR(500),

    -- 内容
    description TEXT,
    toc JSONB,
    has_content BOOLEAN DEFAULT false,
    total_pages INTEGER DEFAULT 0,
    total_chars INTEGER DEFAULT 0,

    -- 向量搜索（修正为512维，匹配bge-small-zh-v1.5）
    embedding vector(512),

    -- 统计
    view_count INTEGER DEFAULT 0,
    bookmark_count INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ========== 索引创建 ==========

-- 三元组索引（模糊匹配，无需chinese配置）
CREATE INDEX idx_books_title_trgm ON books USING gin(title gin_trgm_ops);
CREATE INDEX idx_books_author_trgm ON books USING gin(author gin_trgm_ops);

-- 普通索引
CREATE INDEX idx_books_category ON books(category);
CREATE INDEX idx_books_dynasty ON books(dynasty);
CREATE INDEX idx_books_source ON books(source_id);
CREATE INDEX idx_books_created ON books(created_at DESC);

-- 向量索引（修正）
CREATE INDEX idx_books_embedding ON books USING ivfflat(embedding vector_cosine_ops);

-- 组合索引用于筛选
CREATE INDEX idx_books_category_source ON books(category, source_id);

-- ========== 3. 章节表 ==========
CREATE TABLE IF NOT EXISTS book_chapters (
    id SERIAL PRIMARY KEY,
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,

    chapter_num INTEGER NOT NULL,
    title VARCHAR(500),
    level INTEGER DEFAULT 1,  -- 1=章, 2=节, 3=小节
    parent_id INTEGER REFERENCES book_chapters(id),

    content TEXT,
    char_count INTEGER DEFAULT 0,
    order_position INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chapters_book ON book_chapters(book_id);
CREATE INDEX idx_chapters_parent ON book_chapters(parent_id);
CREATE INDEX idx_chapters_order ON book_chapters(book_id, order_position);

-- 章节内容三元组索引
CREATE INDEX idx_chapters_content_trgm ON book_chapters USING gin(content gin_trgm_ops);

-- ========== 4. 用户书签表 ==========
CREATE TABLE IF NOT EXISTS user_bookmarks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
    chapter_id INTEGER REFERENCES book_chapters(id),

    note TEXT,
    highlight_text TEXT,
    char_position INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bookmarks_user ON user_bookmarks(user_id);
CREATE INDEX idx_bookmarks_book ON user_bookmarks(book_id);

-- ========== 5. 词典表 ==========
CREATE TABLE IF NOT EXISTS dictionary (
    id SERIAL PRIMARY KEY,
    term VARCHAR(200) NOT NULL,
    pinyin VARCHAR(200),
    definition TEXT,
    category VARCHAR(50),
    source VARCHAR(200),
    related_terms TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_dictionary_term_trgm ON dictionary USING gin(term gin_trgm_ops);
CREATE INDEX idx_dictionary_category ON dictionary(category);

-- ========== 6. 阅读历史表 ==========
CREATE TABLE IF NOT EXISTS reading_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
    chapter_id INTEGER REFERENCES book_chapters(id),
    progress_percent INTEGER DEFAULT 0,
    last_read_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_history_user ON reading_history(user_id);
CREATE INDEX idx_history_book ON reading_history(book_id);

-- ========== 7. 插入默认数据源 ==========
INSERT INTO data_sources (code, name_zh, name_en, description, access_type, category, supports_search, supports_fulltext, has_local_fulltext, sort_order) VALUES
('local', '本地教材', 'Local Textbooks', '灵知系统本地教材数据', 'local', '其他', true, true, true, 1),
('guji', '典津', 'Dianjin', '全球汉籍影像开放集成系统', 'api', '儒家', true, false, false, 2),
('cbeta', 'CBETA', 'CBETA', '大正藏电子佛典', 'api', '中医', true, true, false, 3),
('ctext', '中国哲学书电子化计划', 'CTEXT', '中国古代典籍数字化平台', 'api', '儒家', true, false, false, 4),
('zhonghua', '中华经典古籍库', 'Zhonghua Guji', '中华书局古籍数据库', 'api', '儒家', true, false, false, 5)
ON CONFLICT (code) DO NOTHING;

-- ========== 8. 创建更新时间触发器 ==========
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_data_sources_updated_at BEFORE UPDATE ON data_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_books_updated_at BEFORE UPDATE ON books
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_book_chapters_updated_at BEFORE UPDATE ON book_chapters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========== 9. 创建统计视图 ==========
CREATE OR REPLACE VIEW book_statistics AS
SELECT
    category,
    COUNT(*) as total_books,
    SUM(CASE WHEN has_content THEN 1 ELSE 0 END) as books_with_content,
    SUM(total_chars) as total_chars,
    SUM(view_count) as total_views,
    AVG(bookmark_count) as avg_bookmarks
FROM books
GROUP BY category;

-- ========== 10. 创建简化的搜索函数（使用ILIKE）==========
CREATE OR REPLACE FUNCTION search_books_simple(search_query TEXT)
RETURNS TABLE(
    book_id INTEGER,
    title VARCHAR,
    author VARCHAR,
    category VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        b.id,
        b.title,
        b.author,
        b.category
    FROM books b
    WHERE b.title ILIKE '%' || search_query || '%'
       OR b.author ILIKE '%' || search_query || '%'
       OR COALESCE(b.description, '') ILIKE '%' || search_query || '%'
    ORDER BY
        CASE
            WHEN b.title ILIKE search_query THEN 1
            WHEN b.title ILIKE '%' || search_query || '%' THEN 2
            ELSE 3
        END,
        b.view_count DESC
    LIMIT 20;
END;
$$ LANGUAGE plpgsql;

-- ========== 表注释 ==========
COMMENT ON TABLE data_sources IS '数据源配置表';
COMMENT ON TABLE books IS '书籍主表';
COMMENT ON TABLE book_chapters IS '书籍章节表';
COMMENT ON TABLE user_bookmarks IS '用户书签笔记表';
COMMENT ON TABLE dictionary IS '词典术语表';
COMMENT ON TABLE reading_history IS '阅读历史表';

-- ========== 验证脚本 ==========
DO $$
BEGIN
    RAISE NOTICE '=== 数据库初始化完成 ===';
    RAISE NOTICE '扩展: vector, pg_trgm, uuid-ossp';
    RAISE NOTICE '表: data_sources, books, book_chapters, user_bookmarks, dictionary, reading_history';
    RAISE NOTICE '索引: 三元组索引用于模糊搜索，向量索引用于语义搜索';
    RAISE NOTICE '向量维度: 512 (匹配 bge-small-zh-v1.5)';
END $$;
