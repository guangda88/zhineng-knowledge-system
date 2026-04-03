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
    category VARCHAR(50),    -- 气功/佛家/哲学/道家/中医/武术/科学/其他

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
    category VARCHAR(50),  -- 气功/佛家/哲学/道家/中医/武术/科学
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
INSERT INTO data_sources (code, name_zh, name_en, base_url, description, access_type, category, supports_search, supports_fulltext, has_local_fulltext, sort_order) VALUES
-- 气功数据源
('local', '本地教材', 'Local Textbooks', NULL, '灵知系统本地教材数据（智能气功等）', 'local', '气功', true, true, true, 1),

-- 佛家数据源
('cbeta', 'CBETA大正藏', 'CBETA', 'https://cbetaonline.dila.edu.tw', '大正藏电子佛典', 'api', '佛家', true, true, false, 10),
('fojin', 'FoJin佛典平台', 'FoJin', 'https://github.com/xr843/fojin', '聚合503个数据源的全球佛家数字文本平台，9200+文本，17800+卷', 'api', '佛家', true, true, false, 11),
('sat', 'SAT大正藏', 'SAT Daizokyo', 'https://suttacentral.net', 'Taisho Tripitaka 数据库', 'api', '佛家', true, false, false, 12),
('84000', '84000译经会', '84000', 'https://84000.co', '藏文大藏经翻译项目', 'api', '佛家', true, false, false, 13),
('bdrc', '佛教数字资源中心', 'BDRC', 'https://library.bdrc.io', '藏文手稿IIIF影像', 'api', '佛家', true, false, false, 14),

-- 哲学数据源（先秦诸子百家）
('ctext', '中国哲学书电子化计划', 'CTEXT', 'https://ctext.org', '先秦两汉古籍为主，30000+部著作，涵盖诸子百家', 'api', '哲学', true, true, false, 20),
('guji', '典津', 'Dianjin', 'https://www.guji.cn', '全球汉籍影像开放集成系统', 'api', '哲学', true, false, false, 21),
('zhonghua', '中华经典古籍库', 'Zhonghua Guji', 'https://www.guoxue.com', '中华书局古籍数据库', 'api', '哲学', true, false, false, 22),

-- 道家数据源
('homeinmists', '白云深处人家', 'Daoist Library', 'http://www.homeinmists.com', '中华传统道文化数字图书馆，包含道藏5485卷', 'api', '道家', true, true, false, 30),
('daozang', '道藏', 'Daozang', NULL, '道教典籍总集，5485卷', 'local', '道家', true, false, true, 31),

-- 中医数据源
('tcm_ancient', '中医古籍数据集', 'TCM Ancient Books', 'https://www.heywhale.com', '约700项中医药古籍文本，先秦至清末', 'api', '中医', true, true, false, 40),
('huangdi', '黄帝模型', 'HuangDi Model', 'https://github.com/Zlasejd/HuangDI', '基于LLaMA的中医古籍知识模型', 'api', '中医', false, false, false, 41),
('zhongyi_classics', '中医经典', 'TCM Classics', NULL, '伤寒论、黄帝内经等经典著作', 'local', '中医', true, false, true, 42),

-- 武术数据源（待完善）
('wushu_local', '武术典籍库', 'Martial Arts Classics', NULL, '太极拳、形意拳、八卦掌、少林拳等经典拳谱', 'local', '武术', true, false, true, 50),

-- 科学数据源
-- 古代科技
('science_ancient', '古代科技典籍', 'Ancient Chinese Science', NULL, '梦溪笔谈、九章算术、齐民要术等古代科技著作', 'local', '科学', true, false, true, 60),
-- 现代科学前沿
('arxiv', 'arXiv预印本', 'arXiv', 'https://arxiv.org', '200万+篇开放获取论文，物理、数学、计算机科学等', 'api', '科学', true, true, false, 61),
('pubmed', 'PubMed生物医学', 'PubMed', 'https://pubmed.ncbi.nlm.nih.gov', '3500万+篇生物医学文献', 'api', '科学', true, true, false, 62),
('openalex', 'OpenAlex研究目录', 'OpenAlex', 'https://openalex.org', '全球开放研究目录，2.5亿+论文', 'api', '科学', true, true, false, 63),
('plos', 'PLOS ONE期刊', 'PLOS', 'https://journals.plos.org', '开放获取多学科期刊', 'api', '科学', true, true, false, 64),
('doaj', '开放获取期刊目录', 'DOAJ', 'https://doaj.org', '17000+本开放获取期刊', 'api', '科学', true, false, false, 65),
('biorxiv', 'bioRxiv预印本', 'bioRxiv', 'https://www.biorxiv.org', '生物学预印本平台', 'api', '科学', true, true, false, 66),
('medrxiv', 'medRxiv预印本', 'medRxiv', 'https://www.medrxiv.org', '医学预印本平台', 'api', '科学', true, true, false, 67),
('cnki', '中国知网', 'CNKI', 'https://www.cnki.net', '中国最大学术文献数据库', 'api', '科学', true, true, false, 68),
('wanfang', '万方数据', 'Wanfang', 'https://www.wanfangdata.com.cn', '中文期刊、学位论文、会议论文', 'api', '科学', true, true, false, 69),
('nature', 'Nature期刊', 'Nature', 'https://www.nature.com', 'Nature系列期刊', 'api', '科学', true, false, false, 70),
('science', 'Science期刊', 'Science', 'https://www.science.org', 'AAAS Science期刊', 'api', '科学', true, false, false, 71),
('ieee', 'IEEE Xplore', 'IEEE', 'https://ieeexplore.ieee.org', '工程和技术期刊会议', 'api', '科学', true, false, false, 72),
('springer', 'SpringerLink', 'Springer', 'https://link.springer.com', 'Springer科学期刊', 'api', '科学', true, false, false, 73)
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
