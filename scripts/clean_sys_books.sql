-- P0: sys_books 清洗脚本
-- 前置条件: 标注任务完成 (qigong_dims tagging done)
-- 执行方式: psql -U zhineng -d zhineng_kb -f scripts/clean_sys_books.sql

-- ============================================
-- Step 0: 创建完整备份表
-- ============================================
CREATE TABLE IF NOT EXISTS sys_books_archive AS SELECT * FROM sys_books;

-- 验证备份
-- SELECT count(*) FROM sys_books_archive;  -- 应为 3,024,428

-- ============================================
-- Step 1: 添加 data_quality 标记列
-- ============================================
ALTER TABLE sys_books ADD COLUMN IF NOT EXISTS data_quality VARCHAR(30) DEFAULT 'active';

-- ============================================
-- Step 2: Dry-run 统计 (先运行确认)
-- ============================================

-- 2a. 目录行: size=0 且无扩展名
SELECT 'directories' AS category, count(*) AS rows_to_exclude
FROM sys_books
WHERE data_quality = 'active'
  AND (filename NOT LIKE '%.%' OR filename LIKE '%.')
  AND (size = 0 OR size IS NULL);

-- 2b. 代码文件
SELECT 'code_files' AS category, count(*) AS rows_to_exclude
FROM sys_books
WHERE data_quality = 'active'
  AND LOWER(filename) ~ '\.(js|ts|d\.ts|py|css|map|json|xml|yml|yaml|sh|bat|md|git|npmignore|editorconfig|eslintrc|prettierrc|babelrc|dockerfile|makefile|cmake|gradle|toml|ini|cfg|conf|log|lock|cache|tmp|bak|swp|swo)$';

-- 2c. 图片文件
SELECT 'image_files' AS category, count(*) AS rows_to_exclude
FROM sys_books
WHERE data_quality = 'active'
  AND LOWER(filename) ~ '\.(jpg|jpeg|png|tif|tiff|gif|bmp|svg|ico|webp|raw|cr2|nef|psd|ai|eps)$';

-- 2d. 音视频文件
SELECT 'media_files' AS category, count(*) AS rows_to_exclude
FROM sys_books
WHERE data_quality = 'active'
  AND LOWER(filename) ~ '\.(mp3|mp4|flv|avi|wav|wma|wmv|mkv|mov|aac|ogg|flac|m4a|m4v|3gp|dat|vob|asf|rm|rmvb)$';

-- 2e. 汇总
SELECT
  count(*) FILTER (WHERE data_quality = 'active') AS will_remain_active,
  count(*) FILTER (WHERE data_quality != 'active') AS already_excluded,
  count(*) AS total
FROM sys_books;

-- ============================================
-- Step 3: 执行清洗 (确认 dry-run 后再执行)
-- ============================================

-- 3a. 排除目录
UPDATE sys_books SET data_quality = 'excluded_dir'
WHERE data_quality = 'active'
  AND (filename NOT LIKE '%.%' OR filename LIKE '%.')
  AND (size = 0 OR size IS NULL);

-- 3b. 排除代码文件
UPDATE sys_books SET data_quality = 'excluded_code'
WHERE data_quality = 'active'
  AND LOWER(filename) ~ '\.(js|ts|d\.ts|py|css|map|json|xml|yml|yaml|sh|bat|md)$';

-- 3c. 排除图片文件
UPDATE sys_books SET data_quality = 'excluded_image'
WHERE data_quality = 'active'
  AND LOWER(filename) ~ '\.(jpg|jpeg|png|tif|tiff|gif|bmp|svg|ico|webp)$';

-- 3d. 排除音视频
UPDATE sys_books SET data_quality = 'excluded_media'
WHERE data_quality = 'active'
  AND LOWER(filename) ~ '\.(mp3|mp4|flv|avi|wav|wma|wmv|mkv|mov|aac|ogg|flac|m4a|m4v|3gp|dat|vob|asf|rm|rmvb)$';

-- ============================================
-- Step 4: 验证清洗结果
-- ============================================
SELECT data_quality, count(*) AS cnt,
  round(count(*) * 100.0 / (SELECT count(*) FROM sys_books), 1) AS pct
FROM sys_books
GROUP BY data_quality
ORDER BY cnt DESC;

-- 预期:
-- active:          ~570,000 (18.8%)
-- excluded_dir:    ~1,246,000 (41.2%)
-- excluded_image:  ~410,000 (13.6%)
-- excluded_code:   ~146,000 (4.8%)
-- excluded_media:  ~86,000 (2.8%)

-- ============================================
-- Step 5: 更新索引 (可选)
-- ============================================
-- 创建部分索引只覆盖 active 行
CREATE INDEX IF NOT EXISTS idx_sys_books_active
  ON sys_books (filename) WHERE data_quality = 'active';

-- ============================================
-- 回滚方案 (如果需要恢复)
-- ============================================
-- UPDATE sys_books SET data_quality = 'active';
-- 或从备份恢复:
-- DROP TABLE sys_books;
-- CREATE TABLE sys_books AS SELECT * FROM sys_books_archive;
