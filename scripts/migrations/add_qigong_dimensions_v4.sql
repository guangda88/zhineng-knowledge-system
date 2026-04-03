-- ============================================================
-- 智能气功维度体系 V4.0 数据库迁移脚本
-- 文档编号: ZQ-DIM-2026-V4.0
-- 创建日期: 2026-04-02
-- ============================================================
--
-- 功能：
-- 1. 在 documents 表添加 qigong_dims JSONB 字段
-- 2. 创建保密文档管理表（documents_confidential）
-- 3. 创建用户权限管理表（user_permissions）
-- 4. 创建访问审计日志表（access_audit_log）
-- 5. 创建受控词表（qigong_dimension_vocab）
-- 6. 创建维度子项表（qigong_dimension_items）
-- 7. 创建 GIN 索引优化 JSONB 查询
--
-- ============================================================

-- 开始事务
BEGIN;

-- ============================================================
-- 1. 在 documents 表添加 qigong_dims 字段
-- ============================================================

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS qigong_dims JSONB DEFAULT '{}'::jsonb;

-- 添加注释
COMMENT ON COLUMN documents.qigong_dims IS '智能气功维度标注（V4.0），JSONB格式存储16个维度的标注信息';

-- ============================================================
-- 2. 创建 GIN 索引优化 JSONB 查询
-- ============================================================

-- 主索引：GIN 索引支持包含查询
CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims
    ON documents USING GIN (qigong_dims)
    WHERE category = '气功';

-- 特定维度索引（常查询维度）
CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_gongfa
    ON documents USING GIN ((qigong_dims -> 'gongfa_method'))
    WHERE category = '气功' AND qigong_dims ? 'gongfa_method';

CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_discipline
    ON documents USING GIN ((qigong_dims -> 'discipline'))
    WHERE category = '气功' AND qigong_dims ? 'discipline';

CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_teaching
    ON documents USING GIN ((qigong_dims -> 'teaching_level'))
    WHERE category = '气功' AND qigong_dims ? 'teaching_level';

-- 安全级别索引
CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_security
    ON documents USING btree ((COALESCE(qigong_dims ->> 'security_level', 'public')))
    WHERE category = '气功';

-- ============================================================
-- 3. 创建保密文档管理表
-- ============================================================

CREATE TABLE IF NOT EXISTS documents_confidential (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    security_level  VARCHAR(20) NOT NULL
        CHECK (security_level IN ('public', 'internal', 'confidential', 'restricted')),
    access_reason   TEXT,
    source_system   VARCHAR(50) DEFAULT 'manual',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_confidential_doc_id
    ON documents_confidential(document_id);

CREATE INDEX IF NOT EXISTS idx_documents_confidential_security_level
    ON documents_confidential(security_level);

CREATE INDEX IF NOT EXISTS idx_documents_confidential_level_doc
    ON documents_confidential(security_level, document_id);

COMMENT ON TABLE documents_confidential IS '保密文档管理表，单独存储安全访问控制信息';

-- ============================================================
-- 4. 创建用户权限管理表
-- ============================================================

CREATE TABLE IF NOT EXISTS user_permissions (
    id              SERIAL PRIMARY KEY,
    user_id         VARCHAR(100) NOT NULL,
    username        VARCHAR(100) NOT NULL,
    security_level  VARCHAR(20) NOT NULL
        CHECK (security_level IN ('internal', 'confidential', 'restricted')),
    granted_by      VARCHAR(100),
    granted_at      TIMESTAMP DEFAULT NOW(),
    expires_at      TIMESTAMP,
    is_active       BOOLEAN DEFAULT TRUE,
    reason          TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_permissions_user_id
    ON user_permissions(user_id);

CREATE INDEX IF NOT EXISTS idx_user_permissions_security_level
    ON user_permissions(security_level);

CREATE INDEX IF NOT EXISTS idx_user_permissions_active
    ON user_permissions(user_id, is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_user_permissions_expires_at
    ON user_permissions(expires_at) WHERE expires_at IS NOT NULL;

COMMENT ON TABLE user_permissions IS '用户权限管理表，控制用户访问保密文档的权限';

-- ============================================================
-- 5. 创建访问审计日志表
-- ============================================================

CREATE TABLE IF NOT EXISTS access_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(100) NOT NULL,
    username        VARCHAR(100),
    document_id     INTEGER,
    security_level  VARCHAR(20),
    action          VARCHAR(20) NOT NULL,  -- view, download, search, export
    access_time     TIMESTAMP DEFAULT NOW(),
    result          VARCHAR(20) DEFAULT 'success',  -- success, denied, error
    ip_address      INET,
    user_agent      TEXT,
    reason          TEXT
);

CREATE INDEX IF NOT EXISTS idx_access_audit_log_user_id
    ON access_audit_log(user_id, access_time DESC);

CREATE INDEX IF NOT EXISTS idx_access_audit_log_document_id
    ON access_audit_log(document_id, access_time DESC);

CREATE INDEX IF NOT EXISTS idx_access_audit_log_security_level
    ON access_audit_log(security_level, access_time DESC);

CREATE INDEX IF NOT EXISTS idx_access_audit_log_result
    ON access_audit_log(result, access_time DESC);

-- 分区优化（可选，按月分区）
-- CREATE TABLE access_audit_log_y2026m04 PARTITION OF access_audit_log
--     FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

COMMENT ON TABLE access_audit_log IS '访问审计日志表，记录所有保密文档的访问行为';

-- ============================================================
-- 6. 创建受控词表（支持演进）
-- ============================================================

CREATE TABLE IF NOT EXISTS qigong_dimension_vocab (
    dimension_code  VARCHAR(50) PRIMARY KEY,
    dimension_name  VARCHAR(100) NOT NULL,
    category        VARCHAR(10) NOT NULL,  -- S/A/B/C/D/E
    priority        VARCHAR(10) NOT NULL DEFAULT 'P1',  -- P0/P1/P2/P3/P4
    parent_code     VARCHAR(50),
    sub_items       JSONB NOT NULL DEFAULT '[]',
    auto_extract    BOOLEAN DEFAULT FALSE,
    description     TEXT,
    updated_at      TIMESTAMP DEFAULT NOW(),

    -- 演进支持字段
    status          VARCHAR(20) DEFAULT 'active',  -- active/deprecated/experimental
    schema_version  VARCHAR(20) DEFAULT 'v4.0',
    created_at      TIMESTAMP DEFAULT NOW(),
    retired_at      TIMESTAMP,
    replacement_code VARCHAR(50),
    change_log      JSONB DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_dimension_vocab_category
    ON qigong_dimension_vocab(category, priority);

CREATE INDEX IF NOT EXISTS idx_dimension_vocab_status
    ON qigong_dimension_vocab(status);

COMMENT ON TABLE qigong_dimension_vocab IS '智能气功维度受控词表，支持版本演进';

-- ============================================================
-- 7. 创建维度子项表（支持细粒度演进）
-- ============================================================

CREATE TABLE IF NOT EXISTS qigong_dimension_items (
    item_code       VARCHAR(100) PRIMARY KEY,
    dimension_code  VARCHAR(50) NOT NULL REFERENCES qigong_dimension_vocab(dimension_code),
    item_name       VARCHAR(200) NOT NULL,
    parent_item_code VARCHAR(100),
    display_order   INTEGER DEFAULT 0,

    -- 演进支持
    status          VARCHAR(20) DEFAULT 'active',
    since_version   VARCHAR(20) DEFAULT 'v4.0',
    deprecated_in   VARCHAR(20),
    replacement_code VARCHAR(100),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dimension_items_dimension
    ON qigong_dimension_items(dimension_code, display_order);

CREATE INDEX IF NOT EXISTS idx_dimension_items_status
    ON qigong_dimension_items(status);

COMMENT ON TABLE qigong_dimension_items IS '智能气功维度子项表，支持细粒度演进';

-- ============================================================
-- 8. 初始化受控词表数据（V4.0 维度体系）
-- ============================================================

-- S类：安全维度
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, status, schema_version)
VALUES
    ('security_level', '安全级别', 'S', 'P0', 'active', 'v4.0')
ON CONFLICT (dimension_code) DO NOTHING;

-- A类：内容维度
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, status, schema_version)
VALUES
    ('theory_system', '理论体系归属', 'A', 'P0', 'active', 'v4.0'),
    ('content_topic', '内容主题', 'A', 'P0', 'active', 'v4.0'),
    ('gongfa_system', '功法体系', 'A', 'P0', 'active', 'v4.0'),
    ('content_depth', '内容深度', 'A', 'P0', 'active', 'v4.0'),
    ('discipline', '教材归属', 'A', 'P0', 'active', 'v4.0')
ON CONFLICT (dimension_code) DO NOTHING;

-- B类：情境维度
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, status, schema_version)
VALUES
    ('timeline', '时间线', 'B', 'P1', 'active', 'v4.0'),
    ('location', '场所地点', 'B', 'P1', 'active', 'v4.0'),
    ('teaching_level', '教学层次', 'B', 'P1', 'active', 'v4.0'),
    ('presentation', '传播形式', 'B', 'P1', 'active', 'v4.0')
ON CONFLICT (dimension_code) DO NOTHING;

-- C类：来源维度
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, status, schema_version)
VALUES
    ('speaker', '主讲/作者', 'C', 'P1', 'active', 'v4.0'),
    ('source_attribute', '来源属性', 'C', 'P2', 'active', 'v4.0')
ON CONFLICT (dimension_code) DO NOTHING;

-- D类：技术维度
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, status, schema_version)
VALUES
    ('media_format', '存在形式', 'D', 'P3', 'active', 'v4.0'),
    ('tech_spec', '技术规格', 'D', 'P2', 'active', 'v4.0'),
    ('data_status', '完整状态', 'D', 'P3', 'active', 'v4.0')
ON CONFLICT (dimension_code) DO NOTHING;

-- E类：扩展维度
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, status, schema_version)
VALUES
    ('application_effect', '应用成效', 'E', 'P4', 'active', 'v4.0'),
    ('related_resources', '关联网络', 'E', 'P4', 'active', 'v4.0')
ON CONFLICT (dimension_code) DO NOTHING;

-- ============================================================
-- 9. 初始化维度子项数据
-- ============================================================

-- 教材归属 (discipline)
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order)
VALUES
    ('disc_gailun', 'discipline', '概论', 1),
    ('disc_hunyuan', 'discipline', '混元整体理论', 2),
    ('disc_jingyi', 'discipline', '精义', 3),
    ('disc_gongfa', 'discipline', '功法学', 4),
    ('disc_chaochang', 'discipline', '超常智能', 5),
    ('disc_chuantong', 'discipline', '传统气功知识', 6),
    ('disc_wenhua', 'discipline', '气功与文化', 7),
    ('disc_lishi', 'discipline', '气功史', 8),
    ('disc_keyan', 'discipline', '现代科学研究', 9),
    ('disc_feijiaocai', 'discipline', '非教材', 10)
ON CONFLICT (item_code) DO NOTHING;

-- 教学层次 (teaching_level)
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order)
VALUES
    ('teach_kangfu', 'teaching_level', '康复班', 1),
    ('teach_jiaolian', 'teaching_level', '教练员班', 2),
    ('teach_shizi', 'teaching_level', '师资班', 3),
    ('teach_dazhuan', 'teaching_level', '大专课程', 4),
    ('teach_xueshu', 'teaching_level', '学术交流会', 5),
    ('teach_zhuanti', 'teaching_level', '专题班', 6),
    ('teach_gongkai', 'teaching_level', '公开讲座', 7)
ON CONFLICT (item_code) DO NOTHING;

-- 功法体系 (gongfa_system)
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, parent_item_code, display_order)
VALUES
    -- 外混元阶段
    ('gongfa_pengqi', 'gongfa_system', '捧气贯顶法', 'gongfa_wai', 1),
    ('gongfa_sanxin', 'gongfa_system', '三心并站庄', 'gongfa_wai', 2),
    -- 内混元阶段
    ('gongfa_xingshen', 'gongfa_system', '形神庄', 'gongfa_nei', 3),
    ('gongfa_wuyuan', 'gongfa_system', '五元庄', 'gongfa_nei', 4),
    -- 中混元阶段
    ('gongfa_zhongmai', 'gongfa_system', '中脉混元功', 'gongfa_zhong', 5),
    ('gongfa_zhongxian', 'gongfa_system', '中线混元功', 'gongfa_zhong', 6),
    ('gongfa_hunhua', 'gongfa_system', '混化归元功', 'gongfa_zhong', 7),
    -- 其他
    ('gongfa_zuogong', 'gongfa_system', '坐功', 'gongfa_jing', 8),
    ('gongfa_zhan', 'gongfa_system', '站功', 'gongfa_jing', 9),
    ('gongfa_wogong', 'gongfa_system', '卧功', 'gongfa_jing', 10),
    ('gongfa_zifa', 'gongfa_system', '自发功', 'gongfa_jingdong', 11),
    ('gongfa_laqi', 'gongfa_system', '拉气', 'gongfa_fuzhu', 12),
    ('gongfa_lianqi', 'gongfa_system', '练气八法', 'gongfa_fuzhu', 13),
    ('gongfa_zuchang', 'gongfa_system', '组场', 'gongfa_fuzhu', 14),
    ('gongfa_shougong', 'gongfa_system', '收功', 'gongfa_fuzhu', 15),
    ('gongfa_generic', 'gongfa_system', '通用', NULL, 16)
ON CONFLICT (item_code) DO NOTHING;

-- 内容深度 (content_depth)
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order)
VALUES
    ('depth_entry', 'content_depth', '入门', 1),
    ('depth_beginner', 'content_depth', '初级', 2),
    ('depth_intermediate', 'content_depth', '中级', 3),
    ('depth_advanced', 'content_depth', '高级', 4),
    ('depth_expert', 'content_depth', '专家', 5),
    ('depth_research', 'content_depth', '研究级', 6)
ON CONFLICT (item_code) DO NOTHING;

-- 理论体系 (theory_system)
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, parent_item_code, display_order)
VALUES
    -- 混元整体理论
    ('theory_hunyuan_main', 'theory_system', '混元整体理论', NULL, 1),
    ('theory_hunyuan_qi', 'theory_system', '混元气理论', 'theory_hunyuan_main', 2),
    ('theory_hunyuan_yiyuan', 'theory_system', '意元体理论', 'theory_hunyuan_main', 3),
    ('theory_hunyuan_yishi', 'theory_system', '意识论', 'theory_hunyuan_main', 4),
    ('theory_hunyuan_daode', 'theory_system', '道德论', 'theory_hunyuan_main', 5),
    ('theory_hunyuan_life', 'theory_system', '优化生命论', 'theory_hunyuan_main', 6),
    ('theory_hunyuan_medical', 'theory_system', '混元医疗观', 'theory_hunyuan_main', 7),
    -- 传统理论借鉴
    ('theory_tradition_main', 'theory_system', '传统理论借鉴', NULL, 8),
    ('theory_tradition_yinyang', 'theory_system', '阴阳五行', 'theory_tradition_main', 9),
    ('theory_tradition_zangxiang', 'theory_system', '藏象经络', 'theory_tradition_main', 10),
    ('theory_tradition_confucian', 'theory_system', '儒释道武', 'theory_tradition_main', 11),
    -- 现代科学结合
    ('theory_modern_main', 'theory_system', '现代科学结合', NULL, 12),
    ('theory_modern_physio', 'theory_system', '生理学', 'theory_modern_main', 13),
    ('theory_modern_anatomy', 'theory_system', '解剖学', 'theory_modern_main', 14),
    ('theory_modern_psych', 'theory_system', '心理学', 'theory_modern_main', 15),
    ('theory_modern_research', 'theory_system', '现代科研', 'theory_modern_main', 16)
ON CONFLICT (item_code) DO NOTHING;

-- 传播形式 (presentation)
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order)
VALUES
    ('pres_book', 'presentation', '书籍/教材', 1),
    ('pres_paper', 'presentation', '论文/文章', 2),
    ('pres_lecture', 'presentation', '讲课', 3),
    ('pres_talk', 'presentation', '谈话/座谈', 4),
    ('pres_note', 'presentation', '笔记', 5),
    ('pres_qa', 'presentation', '问答', 6),
    ('pres_speech', 'presentation', '致辞/发言', 7),
    ('pres_letter', 'presentation', '信函', 8),
    ('pres_interview', 'presentation', '采访', 9)
ON CONFLICT (item_code) DO NOTHING;

-- 主讲/作者 (speaker)
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order)
VALUES
    ('speaker_pangming', 'speaker', '庞明主讲', 1),
    ('speaker_pangming_assist', 'speaker', '庞明+助教', 2),
    ('speaker_assistant', 'speaker', '助教辅导', 3),
    ('speaker_student', 'speaker', '学员发言', 4),
    ('speaker_guest', 'speaker', '特邀嘉宾', 5),
    ('speaker_recording', 'speaker', '录音播放', 6),
    ('speaker_other', 'speaker', '其他', 7)
ON CONFLICT (item_code) DO NOTHING;

-- 媒体格式 (media_format)
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order)
VALUES
    ('media_text', 'media_format', '文字', 1),
    ('media_doc', 'media_format', '文档', 2),
    ('media_image', 'media_format', '图片', 3),
    ('media_audio', 'media_format', '音频', 4),
    ('media_video', 'media_format', '视频', 5),
    ('media_scan', 'media_format', '扫描版', 6)
ON CONFLICT (item_code) DO NOTHING;

-- 安全级别 (security_level)
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order)
VALUES
    ('sec_public', 'security_level', 'public', 1),
    ('sec_internal', 'security_level', 'internal', 2),
    ('sec_confidential', 'security_level', 'confidential', 3),
    ('sec_restricted', 'security_level', 'restricted', 4)
ON CONFLICT (item_code) DO NOTHING;

-- 时间线 (timeline)
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order)
VALUES
    ('time_early', 'timeline', '早期探索 (1980-1986)', 1),
    ('time_systematic', 'timeline', '系统授课 (1987-1988)', 2),
    ('time_shijiazhuang', 'timeline', '石家庄时期 (1989-1991)', 3),
    ('time_qinhuangdao', 'timeline', '秦皇岛时期 (1992-2000)', 4),
    ('time_deep_research', 'timeline', '深化研究 (2000-2009)', 5),
    ('time_inheritance', 'timeline', '传承发展 (2010-至今)', 6)
ON CONFLICT (item_code) DO NOTHING;

-- ============================================================
-- 10. 创建视图方便查询
-- ============================================================

-- 已打标的气功文档视图
CREATE OR REPLACE VIEW qigong_tagged_documents AS
SELECT
    d.id,
    d.title,
    d.category,
    d.tags,
    d.qigong_dims,
    d.created_at,
    d.updated_at,
    -- 提取常用维度
    d.qigong_dims->>'discipline' AS discipline,
    d.qigong_dims->>'teaching_level' AS teaching_level,
    d.qigong_dims->>'gongfa_method' AS gongfa_method,
    d.qigong_dims->>'content_depth' AS content_depth,
    d.qigong_dims->>'theory_system' AS theory_system,
    d.qigong_dims->>'media_format' AS media_format,
    d.qigong_dims->>'speaker' AS speaker,
    d.qigong_dims->>'security_level' AS security_level
FROM documents d
WHERE d.category = '气功'
  AND d.qigong_dims IS NOT NULL
  AND d.qigong_dims != '{}'::jsonb;

COMMENT ON VIEW qigong_tagged_documents IS '已打标的气功文档视图，包含常用维度提取';

-- 维度覆盖率统计视图
CREATE OR REPLACE VIEW qigong_coverage_stats AS
SELECT
    COUNT(*) AS total_documents,
    COUNT(*) FILTER (WHERE qigong_dims IS NOT NULL AND qigong_dims != '{}'::jsonb) AS tagged_count,
    ROUND(
        COUNT(*) FILTER (WHERE qigong_dims IS NOT NULL AND qigong_dims != '{}'::jsonb)::numeric /
        NULLIF(COUNT(*), 0) * 100, 1
    ) AS coverage_percent
FROM documents
WHERE category = '气功';

COMMENT ON VIEW qigong_coverage_stats IS '气功文档打标覆盖率统计视图';

-- ============================================================
-- 11. 创建辅助函数
-- ============================================================

-- 获取文档的安全级别函数
CREATE OR REPLACE FUNCTION get_doc_security_level(doc_id INTEGER)
RETURNS VARCHAR(20) AS $$
    SELECT COALESCE(qigong_dims->>'security_level', 'public')::varchar(20)
    FROM documents WHERE id = $1;
$$ LANGUAGE SQL STABLE;

COMMENT ON FUNCTION get_doc_security_level IS '获取文档的安全级别';

-- 检查用户是否有权限访问指定级别
CREATE OR REPLACE FUNCTION check_user_permission(
    p_user_id VARCHAR(100),
    p_required_level VARCHAR(20)
) RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM user_permissions
        WHERE user_id = p_user_id
          AND is_active = TRUE
          AND (expires_at IS NULL OR expires_at > NOW())
          AND CASE p_required_level
              WHEN 'restricted' THEN security_level = 'restricted'
              WHEN 'confidential' THEN security_level IN ('confidential', 'restricted')
              WHEN 'internal' THEN security_level IN ('internal', 'confidential', 'restricted')
              ELSE FALSE
          END
    );
$$ LANGUAGE SQL STABLE;

COMMENT ON FUNCTION check_user_permission IS '检查用户是否有权限访问指定安全级别';

-- 记录访问日志函数
CREATE OR REPLACE FUNCTION log_access(
    p_user_id VARCHAR(100),
    p_username VARCHAR(100),
    p_document_id INTEGER,
    p_security_level VARCHAR(20),
    p_action VARCHAR(20),
    p_result VARCHAR(20) DEFAULT 'success',
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
) RETURNS BIGINT AS $$
    INSERT INTO access_audit_log (
        user_id, username, document_id, security_level,
        action, result, ip_address, user_agent
    ) VALUES (
        p_user_id, p_username, p_document_id, p_security_level,
        p_action, p_result, p_ip_address, p_user_agent
    )
    RETURNING id;
$$ LANGUAGE SQL;

COMMENT ON FUNCTION log_access IS '记录访问审计日志';

-- ============================================================
-- 12. 授予必要的权限（根据实际情况调整）
-- ============================================================

-- 如果有应用用户，授予只读权限
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_user;
-- GRANT SELECT, UPDATE ON documents TO app_user;
-- GRANT SELECT, INSERT ON access_audit_log TO app_user;

-- ============================================================
-- 完成迁移
-- ============================================================

COMMIT;

-- ============================================================
-- 验证迁移结果
-- ============================================================

DO $$
BEGIN
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'V4.0 维度体系迁移完成！';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '新增表:';
    RAISE NOTICE '  - documents_confidential (保密文档)';
    RAISE NOTICE '  - user_permissions (用户权限)';
    RAISE NOTICE '  - access_audit_log (访问审计)';
    RAISE NOTICE '  - qigong_dimension_vocab (受控词表)';
    RAISE NOTICE '  - qigong_dimension_items (维度子项)';
    RAISE NOTICE '';
    RAISE NOTICE '新增字段:';
    RAISE NOTICE '  - documents.qigong_dims (JSONB)';
    RAISE NOTICE '';
    RAISE NOTICE '新增视图:';
    RAISE NOTICE '  - qigong_tagged_documents';
    RAISE NOTICE '  - qigong_coverage_stats';
    RAISE NOTICE '';
    RAISE NOTICE '新增函数:';
    RAISE NOTICE '  - get_doc_security_level(doc_id)';
    RAISE NOTICE '  - check_user_permission(user_id, level)';
    RAISE NOTICE '  - log_access(...)';
    RAISE NOTICE '===========================================';
END $$;
