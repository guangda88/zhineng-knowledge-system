-- 古籍数据关联改进脚本
-- 执行顺序: 1) 创建临时映射表 2) 更新标题 3) 建立索引 4) 统计结果

BEGIN;

-- ============================================
-- 步骤1: 创建临时映射表 (用于从JSON导入)
-- ============================================
DROP TABLE IF EXISTS temp_book_mapping;
CREATE TEMP TABLE temp_book_mapping (
    id TEXT PRIMARY KEY,
    book_name TEXT NOT NULL,
    keywords JSONB,
    preview TEXT
);

-- ============================================
-- 步骤2: 更新 guji_documents 的 title
-- 从 bid_book_mapping.json 导入的数据关联
-- ============================================

-- 首先查看当前状态
SELECT '=== 更新前统计 ===' as step;
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as has_title,
    COUNT(CASE WHEN title IS NULL OR title = '' THEN 1 END) as no_title
FROM guji_documents;

-- 通过 content_source_id 关联更新 (使用 guji_content_mapping)
UPDATE guji_documents g
SET title = cm.content_book_name
FROM guji_content_mapping cm
WHERE g.source_id = cm.content_source_id
  AND g.source_table = cm.content_source_table
  AND cm.content_book_name IS NOT NULL
  AND cm.content_book_name != '';

SELECT '=== 通过 content_mapping 更新后 ===' as step;
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as has_title
FROM guji_documents;

-- 通过扫描文件名提取书名 (使用 guji_scan_mapping)
UPDATE guji_documents g
SET title = (
    SELECT DISTINCT REPLACE(
        REGEXP_REPLACE(
            REGEXP_REPLACE(gs.file_name, '\d+', ''),
            '\.(djvu|pdf|zip)$', ''
        ),
        '宋刊本|嘉業堂藏宋刊本|明翻宋岳氏相台本|中华书局', ''
    )
    FROM guji_scan_mapping gs
    WHERE gs.source_table = g.source_table
    LIMIT 1
)
WHERE g.title IS NULL OR g.title = '';

SELECT '=== 通过 scan_mapping 提取书名后 ===' as step;
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as has_title
FROM guji_documents;

-- ============================================
-- 步骤3: 建立索引
-- ============================================

-- 组合索引用于快速查找扫描文档对应的内容
CREATE INDEX IF NOT EXISTS idx_guji_scan_book_path
ON guji_scan_mapping(book_id, file_path);

-- 内容索引用于全文搜索
CREATE INDEX IF NOT EXISTS idx_guji_content_trgm
ON guji_documents USING gin (content gin_trgm_ops);

-- book_id 与 source_id 的关联索引
CREATE INDEX IF NOT EXISTS idx_guji_content_source_book
ON guji_content_mapping(scan_book_id, content_source_id);

-- ============================================
-- 步骤4: 数据质量统计
-- ============================================

SELECT '=== 最终统计 ===' as step;

-- guji_documents 统计
SELECT
    'guji_documents' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT source_table) as source_tables,
    COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as has_title,
    ROUND(AVG(content_length)::numeric, 0) as avg_content_length
FROM guji_documents

UNION ALL

-- guji_scan_mapping 统计
SELECT
    'guji_scan_mapping' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT source_table) as source_tables,
    COUNT(DISTINCT book_id) as unique_books,
    ROUND(AVG(file_size)::numeric, 0) as avg_file_size
FROM guji_scan_mapping

UNION ALL

-- guji_content_mapping 统计
SELECT
    'guji_content_mapping' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT scan_file_name) as mapped_files,
    COUNT(DISTINCT content_source_id) as content_sources,
    COUNT(DISTINCT content_source_table) as source_tables
FROM guji_content_mapping;

-- ============================================
-- 步骤5: 显示书名样本
-- ============================================
SELECT '=== 书名样本 (前20条) ===' as step;
SELECT
    source_id,
    LEFT(title, 30) as book_name,
    LEFT(content, 50) as content_preview
FROM guji_documents
WHERE title IS NOT NULL AND title != ''
ORDER BY source_id
LIMIT 20;

COMMIT;

-- ============================================
-- 查看所有索引
-- ============================================
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('guji_documents', 'guji_scan_mapping', 'guji_content_mapping')
ORDER BY tablename, indexname;
