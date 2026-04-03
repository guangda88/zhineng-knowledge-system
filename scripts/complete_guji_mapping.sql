-- 古籍数据关联完善脚本
-- 创建映射表、索引，建立完整关联

BEGIN;

-- ============================================
-- 1. 创建bid_book_name映射表
-- ============================================
DROP TABLE IF EXISTS bid_book_name CASCADE;
CREATE TABLE bid_book_name (
    bid INTEGER PRIMARY KEY,
    book_name TEXT NOT NULL,
    keywords JSONB,
    preview TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- 2. 更新 guji_scan_mapping 的关联
-- ============================================

-- 确保所有扫描文档都有正确的 book_id
UPDATE guji_scan_mapping g
SET book_id = COALESCE(
    -- 尝试从文件名中提取数字作为 book_id
    (REGEXP_REPLACE(file_name, '^\D*0*(\d+).*', '\1'))::INTEGER,
    g.book_id
)
WHERE g.book_id IS NULL OR g.book_id = 0;

-- ============================================
-- 3. 建立完整索引
-- ============================================

-- 扫描文档索引用于快速查找
CREATE INDEX IF NOT EXISTS idx_guji_scan_filename_trgm
ON guji_scan_mapping USING gin (file_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_guji_scan_file_type
ON guji_scan_mapping(file_type, book_id);

-- 内容索引用于全文搜索
CREATE INDEX IF NOT EXISTS idx_guji_content_title
ON guji_documents USING gin (to_tsvector('simple', title));

CREATE INDEX IF NOT EXISTS idx_guji_content_source
ON guji_documents(source_table, source_id);

-- 映射表索引用于关联查询
CREATE INDEX IF NOT EXISTS idx_guji_content_map_scan
ON guji_content_mapping(scan_book_id, scan_file_name);

CREATE INDEX IF NOT EXISTS idx_guji_content_map_content
ON guji_content_mapping(content_source_id, content_source_table);

-- ============================================
-- 4. 创建视图：完整古籍信息
-- ============================================
CREATE OR REPLACE VIEW v_guji_full_info AS
SELECT
    s.id as scan_id,
    s.file_name,
    s.file_path,
    s.file_type,
    s.book_id,
    g.id as document_id,
    g.source_table,
    g.source_id,
    g.title as book_name,
    g.content,
    g.content_length
FROM guji_scan_mapping s
LEFT JOIN guji_documents g ON
    (g.source_id::text = s.book_id::text OR s.file_name LIKE '%' || g.title || '%')
    AND g.source_table = 'wx200';

-- ============================================
-- 5. 数据质量报告
-- ============================================

SELECT '=== 古籍数据关联报告 ===' as report_title;

-- 1. 扫描文档统计
SELECT
    '1. 扫描文档统计' as section,
    COUNT(*) as total_files,
    COUNT(DISTINCT book_id) as unique_books,
    COUNT(CASE WHEN file_type = 'djvu' THEN 1 END) as djvu_files,
    COUNT(CASE WHEN file_type = 'pdf' THEN 1 END) as pdf_files,
    COUNT(CASE WHEN file_type = 'zip' THEN 1 END) as zip_files
FROM guji_scan_mapping;

-- 2. 内容文档统计
SELECT
    '2. 内容文档统计' as section,
    COUNT(*) as total_records,
    COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as has_title,
    COUNT(CASE WHEN title IS NULL OR title = '' THEN 1 END) as no_title,
    ROUND(AVG(content_length)::numeric, 0) as avg_length
FROM guji_documents;

-- 3. 映射关联统计
SELECT
    '3. 映射关联统计' as section,
    COUNT(*) as total_mappings,
    COUNT(DISTINCT scan_file_name) as mapped_files,
    COUNT(DISTINCT content_source_id) as mapped_content_sources
FROM guji_content_mapping;

-- 4. 按分类统计
SELECT
    '4. 路径分类统计' as section,
    CASE
        WHEN file_path LIKE '%丛刊%' THEN '四部丛刊'
        WHEN file_path LIKE '%智能气功%' THEN '气功图书馆'
        ELSE '其他'
    END as collection,
    COUNT(*) as file_count
FROM guji_scan_mapping
GROUP BY collection
ORDER BY file_count DESC;

-- ============================================
-- 6. 展示完整关联示例
-- ============================================
SELECT '=== 完整关联示例 (前10条) ===' as example_title;

SELECT
    s.file_name as 文件名,
    COALESCE(g.title, '未关联') as 书名,
    LEFT(g.content, 40) as 内容预览,
    s.file_path as 路径
FROM guji_scan_mapping s
LEFT JOIN guji_documents g ON
    (g.source_id::text = s.book_id::text OR s.file_name LIKE '%' || g.title || '%')
    AND g.source_table = 'wx200'
ORDER BY s.id
LIMIT 10;

COMMIT;

-- 查看所有相关表的索引
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('guji_documents', 'guji_scan_mapping', 'guji_content_mapping')
ORDER BY tablename, indexname;
