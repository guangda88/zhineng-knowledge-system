-- 灵知系统 - 找书查书功能数据库初始化脚本
-- 创建数据源、书籍、章节等相关表

-- 1. 数据源表
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

-- 2. 书籍表
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

    -- 向量搜索（需要pgvector扩展）
    embedding vector(1024),

    -- 统计
    view_count INTEGER DEFAULT 0,
    bookmark_count INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_books_title ON books USING gin(to_tsvector('chinese', title));
CREATE INDEX idx_books_author ON books USING gin(to_tsvector('chinese', author));
CREATE INDEX idx_books_category ON books(category);
CREATE INDEX idx_books_dynasty ON books(dynasty);
CREATE INDEX idx_books_source ON books(source_id);
CREATE INDEX idx_books_embedding ON books USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_books_created ON books(created_at DESC);

-- 全文搜索索引
CREATE INDEX idx_books_fulltext ON books USING gin(
    to_tsvector('chinese',
        COALESCE(title, '') || ' ' ||
        COALESCE(author, '') || ' ' ||
        COALESCE(description, '')
    )
);

-- 3. 章节表
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

-- 章节全文搜索
CREATE INDEX idx_chapters_content ON book_chapters USING gin(to_tsvector('chinese', content));

-- 4. 用户书签表
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

-- 5. 词典表
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

CREATE INDEX idx_dictionary_term ON dictionary(term);
CREATE INDEX idx_dictionary_category ON dictionary(category);
CREATE INDEX idx_dictionary_fulltext ON dictionary USING gin(to_tsvector('chinese', term || ' ' || COALESCE(definition, '')));

-- 6. 阅读历史表
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

-- 7. 插入默认数据源
INSERT INTO data_sources (code, name_zh, name_en, description, access_type, category, supports_search, supports_fulltext, has_local_fulltext, sort_order) VALUES
('local', '本地教材', 'Local Textbooks', '灵知系统本地教材数据', 'local', '其他', true, true, true, 1),
('guji', '典津', 'Dianjin', '全球汉籍影像开放集成系统', 'api', '儒家', true, false, false, 2),
('cbeta', 'CBETA', 'CBETA', '大正藏电子佛典', 'api', '中医', true, true, false, 3),
('ctext', '中国哲学书电子化计划', 'CTEXT', '中国古代典籍数字化平台', 'api', '儒家', true, false, false, 4),
('zhonghua', '中华经典古籍库', 'Zhonghua Guji', '中华书局古籍数据库', 'api', '儒家', true, false, false, 5)
ON CONFLICT (code) DO NOTHING;

-- 8. 创建更新时间触发器
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

-- 9. 创建统计视图
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

-- 10. 创建全文搜索函数
CREATE OR REPLACE FUNCTION search_books(search_query TEXT)
RETURNS TABLE(
    book_id INTEGER,
    title VARCHAR,
    author VARCHAR,
    category VARCHAR,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        b.id,
        b.title,
        b.author,
        b.category,
        ts_rank(b.textsearchable_index_col, to_tsquery('chinese', search_query)) AS rank
    FROM books b
    WHERE b.textsearchable_index_col @@ to_tsquery('chinese', search_query)
    ORDER BY rank DESC
    LIMIT 20;
END;
$$ LANGUAGE plpgsql;

-- 添加全文搜索列（用于上面的函数）
ALTER TABLE books ADD COLUMN textsearchable_index_col tsvector
    GENERATED ALWAYS AS (to_tsvector('chinese',
        COALESCE(title, '') || ' ' ||
        COALESCE(author, '') || ' ' ||
        COALESCE(description, '')
    )) STORED;

CREATE INDEX idx_books_textsearch ON books USING gin(textsearchable_index_col);

COMMENT ON TABLE data_sources IS '数据源配置表';
COMMENT ON TABLE books IS '书籍主表';
COMMENT ON TABLE book_chapters IS '书籍章节表';
COMMENT ON TABLE user_bookmarks IS '用户书签笔记表';
COMMENT ON TABLE dictionary IS '词典术语表';
COMMENT ON TABLE reading_history IS '阅读历史表';
