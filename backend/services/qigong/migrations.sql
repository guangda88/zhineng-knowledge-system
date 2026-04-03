-- =====================================================
-- 智能气功资料维度体系 - 数据库迁移脚本
-- 版本: V4.0
-- 日期: 2026-04-02
-- =====================================================

-- =====================================================
-- 迁移 001: 添加维度字段和索引
-- =====================================================

-- 1. 添加 qigong_dims JSONB 字段到 documents 表
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents'
        AND column_name = 'qigong_dims'
    ) THEN
        ALTER TABLE documents
        ADD COLUMN qigong_dims JSONB DEFAULT '{}';
    END IF;
END $$;

-- 2. 创建 GIN 索引（高效 JSONB 查询）
CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims
    ON documents USING GIN (qigong_dims)
    WHERE category = '气功';

-- 3. 创建部分索引（按具体维度查询优化）
CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_gongfa
    ON documents ((qigong_dims->>'gongfa_method'))
    WHERE qigong_dims ? 'gongfa_method' AND category = '气功';

CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_discipline
    ON documents ((qigong_dims->>'discipline'))
    WHERE qigong_dims ? 'discipline' AND category = '气功';

CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_teaching
    ON documents ((qigong_dims->>'teaching_level'))
    WHERE qigong_dims ? 'teaching_level' AND category = '气功';

CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_theory
    ON documents ((qigong_dims->>'theory_system'))
    WHERE qigong_dims ? 'theory_system' AND category = '气功';

CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_depth
    ON documents ((qigong_dims->>'content_depth'))
    WHERE qigong_dims ? 'content_depth' AND category = '气功';

-- 4. 创建触发器（自动更新 updated_at）
CREATE OR REPLACE FUNCTION documents_qigong_dims_update()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_documents_qigong_dims_update ON documents;
CREATE TRIGGER trigger_documents_qigong_dims_update
BEFORE UPDATE ON documents
FOR EACH ROW
WHEN (OLD.qigong_dims IS DISTINCT FROM NEW.qigong_dims)
EXECUTE FUNCTION documents_qigong_dims_update();

-- =====================================================
-- 迁移 002: 创建受控词表
-- =====================================================

-- 维度词表（支持演进）
CREATE TABLE IF NOT EXISTS qigong_dimension_vocab (
    dimension_code  VARCHAR(50) PRIMARY KEY,
    dimension_name  VARCHAR(100) NOT NULL,
    category        VARCHAR(10) NOT NULL,  -- A/B/C/D/E
    priority        VARCHAR(10) NOT NULL DEFAULT 'P1',  -- P0/P1/P2/P3/P4
    parent_code     VARCHAR(50),
    sub_items       JSONB NOT NULL DEFAULT '[]',
    auto_extract    BOOLEAN DEFAULT FALSE,
    description     TEXT,

    -- 演进支持
    status          VARCHAR(20) DEFAULT 'active',  -- active/deprecated/experimental
    schema_version  VARCHAR(20) DEFAULT 'v4.0',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    retired_at      TIMESTAMP,
    replacement_code VARCHAR(50),
    change_log      JSONB DEFAULT '[]'
);

-- 维度子项表
CREATE TABLE IF NOT EXISTS qigong_dimension_items (
    item_code       VARCHAR(100) PRIMARY KEY,
    dimension_code  VARCHAR(50) NOT NULL,
    item_name       VARCHAR(200) NOT NULL,
    parent_item_code VARCHAR(100),
    display_order   INTEGER DEFAULT 0,

    status          VARCHAR(20) DEFAULT 'active',
    since_version   VARCHAR(20) DEFAULT 'v4.0',
    deprecated_in   VARCHAR(20),
    replacement_code VARCHAR(100),

    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (dimension_code) REFERENCES qigong_dimension_vocab(dimension_code)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_dimension_vocab_cat
    ON qigong_dimension_vocab(category, priority);
CREATE INDEX IF NOT EXISTS idx_dimension_items_dim
    ON qigong_dimension_items(dimension_code, display_order);

-- =====================================================
-- 迁移 003: 初始化受控词表数据
-- =====================================================

-- S类: 安全维度（保密数据访问控制）
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, description) VALUES
('security_level', '安全级别', 'S', 'P0', '控制资料访问权限，防止保密数据泄露')
ON CONFLICT (dimension_code) DO UPDATE SET
    category = 'S',
    priority = 'P0',
    description = '控制资料访问权限，防止保密数据泄露',
    updated_at = NOW();

INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order) VALUES
('sec_public', 'security_level', 'public', 1),
('sec_internal', 'security_level', 'internal', 2),
('sec_confidential', 'security_level', 'confidential', 3),
('sec_restricted', 'security_level', 'restricted', 4)
ON CONFLICT DO NOTHING;

-- A类: 内容维度
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, description) VALUES
('theory_system', '理论体系归属', 'A', 'P0', '标识资料所属的理论体系'),
('content_topic', '内容主题', 'A', 'P0', '描述资料的具体内容主题，两级结构'),
('gongfa_system', '功法体系', 'A', 'P0', '按智能气功三阶段六步功法体系分类'),
('content_depth', '内容深度', 'A', 'P0', '描述资料的理论深度和适用对象'),
('discipline', '教材归属', 'A', 'P0', '对应智能气功科学九册教材体系')
ON CONFLICT (dimension_code) DO UPDATE SET
    updated_at = NOW();

-- B类: 情境维度
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, description) VALUES
('timeline', '时间线', 'B', 'P1', '按智能气功发展历程划分时期'),
('location', '场所地点', 'B', 'P1', '记录资料产生的地点信息'),
('teaching_level', '教学层次', 'B', 'P1', '合并课程级别与对应受众'),
('presentation', '传播形式', 'B', 'P1', '描述资料的固有内容形态')
ON CONFLICT (dimension_code) DO UPDATE SET
    updated_at = NOW();

-- C类: 来源维度
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, description) VALUES
('speaker', '主讲/作者', 'C', 'P1', '记录资料的主讲人或作者'),
('source_attribute', '来源属性', 'C', 'P2', '描述资料的来源、整理方式、权威等级')
ON CONFLICT (dimension_code) DO UPDATE SET
    updated_at = NOW();

-- D类: 技术维度
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, description) VALUES
('media_format', '存在形式', 'D', 'P3', '描述资料的媒体格式'),
('tech_spec', '技术规格', 'D', 'P2', '合并载体介质与收录方式'),
('data_status', '完整状态', 'D', 'P3', '描述资料的完整性、处理状态和发布状态')
ON CONFLICT (dimension_code) DO UPDATE SET
    updated_at = NOW();

-- E类: 扩展维度
INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, description) VALUES
('application_effect', '应用成效', 'E', 'P4', '记录资料中提到的应用效果数据'),
('related_resources', '关联网络', 'E', 'P4', '构建资料间的关联关系')
ON CONFLICT (dimension_code) DO UPDATE SET
    updated_at = NOW();

-- 插入子项（关键维度）
-- content_topic 一级类
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order) VALUES
('topic_theory', 'content_topic', '理论类', 1),
('topic_gongfa', 'content_topic', '功法类', 2),
('topic_application', 'content_topic', '应用类', 3),
('topic_comprehensive', 'content_topic', '综合类', 4)
ON CONFLICT DO NOTHING;

-- gongfa_system 子项
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order) VALUES
('gongfa_outer', 'gongfa_system', '外混元', 1),
('gongfa_inner', 'gongfa_system', '内混元', 2),
('gongfa_central', 'gongfa_system', '中混元', 3),
('gongfa_jingong', 'gongfa_system', '静功类', 4),
('gongfa_jingdong', 'gongfa_system', '静动功类', 5),
('gongfa_auxiliary', 'gongfa_system', '辅助功法', 6),
('gongfa_general', 'gongfa_system', '通用', 7)
ON CONFLICT DO NOTHING;

-- content_depth 子项
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order) VALUES
('depth_intro', 'content_depth', '入门', 1),
('depth_beginner', 'content_depth', '初级', 2),
('depth_intermediate', 'content_depth', '中级', 3),
('depth_advanced', 'content_depth', '高级', 4),
('depth_expert', 'content_depth', '专家', 5),
('depth_research', 'content_depth', '研究级', 6)
ON CONFLICT DO NOTHING;

-- discipline 子项
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order) VALUES
('disc_intro', 'discipline', '概论', 1),
('disc_hunyuan', 'discipline', '混元整体理论', 2),
('disc_jingyi', 'discipline', '精义', 3),
('disc_gongfa', 'discipline', '功法学', 4),
('disc_supernormal', 'discipline', '超常智能', 5),
('disc_traditional', 'discipline', '传统气功知识', 6),
('disc_culture', 'discipline', '气功与文化', 7),
('disc_history', 'discipline', '气功史', 8),
('disc_research', 'discipline', '现代科学研究', 9),
('disc_none', 'discipline', '非教材', 10)
ON CONFLICT DO NOTHING;

-- =====================================================
-- 迁移 004: 创建统计视图
-- =====================================================

-- 维度覆盖率统计视图
CREATE OR REPLACE VIEW v_qigong_coverage_stats AS
SELECT
    COUNT(*) AS total_docs,
    COUNT(*) FILTER (WHERE qigong_dims IS NOT NULL AND qigong_dims != '{}'::jsonb) AS tagged_docs,
    ROUND(
        COUNT(*) FILTER (WHERE qigong_dims IS NOT NULL AND qigong_dims != '{}'::jsonb)::numeric /
        NULLIF(COUNT(*), 0) * 100,
        2
    ) AS coverage_percent
FROM documents
WHERE category = '气功';

-- 维度分布统计视图
CREATE OR REPLACE VIEW v_qigong_dimension_distribution AS
SELECT
    'gongfa_method' AS dimension,
    qigong_dims->>'gongfa_method' AS value,
    COUNT(*) AS count
FROM documents
WHERE category = '气功' AND qigong_dims ? 'gongfa_method'
GROUP BY qigong_dims->>'gongfa_method'

UNION ALL

SELECT
    'discipline' AS dimension,
    qigong_dims->>'discipline' AS value,
    COUNT(*) AS count
FROM documents
WHERE category = '气功' AND qigong_dims ? 'discipline'
GROUP BY qigong_dims->>'discipline'

UNION ALL

SELECT
    'teaching_level' AS dimension,
    qigong_dims->>'teaching_level' AS value,
    COUNT(*) AS count
FROM documents
WHERE category = '气功' AND qigong_dims ? 'teaching_level'
GROUP BY qigong_dims->>'teaching_level';

-- =====================================================
-- 回滚脚本（如需回滚）
-- =====================================================

-- DROP VIEW IF EXISTS v_qigong_coverage_stats;
-- DROP VIEW IF EXISTS v_qigong_dimension_distribution;
-- DROP TABLE IF EXISTS qigong_dimension_items;
-- DROP TABLE IF EXISTS qigong_dimension_vocab;
-- DROP TRIGGER IF EXISTS trigger_documents_qigong_dims_update ON documents;
-- DROP FUNCTION IF EXISTS documents_qigong_dims_update();
-- DROP INDEX IF EXISTS idx_documents_qigong_dims_depth;
-- DROP INDEX IF EXISTS idx_documents_qigong_dims_theory;
-- DROP INDEX IF EXISTS idx_documents_qigong_dims_teaching;
-- DROP INDEX IF EXISTS idx_documents_qigong_dims_discipline;
-- DROP INDEX IF EXISTS idx_documents_qigong_dims_gongfa;
-- DROP INDEX IF EXISTS idx_documents_qigong_dims;
-- ALTER TABLE documents DROP COLUMN IF EXISTS qigong_dims;

-- =====================================================
-- 验证脚本
-- =====================================================

-- 验证迁移是否成功
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    -- 检查 qigong_dims 字段
    SELECT COUNT(*) INTO v_count
    FROM information_schema.columns
    WHERE table_name = 'documents' AND column_name = 'qigong_dims';

    IF v_count = 0 THEN
        RAISE EXCEPTION 'qigong_dims column not found';
    END IF;

    -- 检查索引
    SELECT COUNT(*) INTO v_count
    FROM pg_indexes
    WHERE indexname LIKE 'idx_documents_qigong%';

    IF v_count < 5 THEN
        RAISE EXCEPTION 'qigong indexes not created correctly, found only % indexes', v_count;
    END IF;

    -- 检查词表
    SELECT COUNT(*) INTO v_count FROM qigong_dimension_vocab;
    IF v_count < 10 THEN
        RAISE EXCEPTION 'dimension_vocab table not populated, found only % rows', v_count;
    END IF;

    RAISE NOTICE 'Migration validated successfully!';
END;
$$;

-- =====================================================
-- 迁移 005: 保密数据访问控制表
-- =====================================================

-- 1. 保密文档表（与 documents 表分离）
CREATE TABLE IF NOT EXISTS documents_confidential (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    security_level  VARCHAR(20) NOT NULL CHECK (security_level IN ('internal', 'confidential', 'restricted')),
    access_reason   TEXT,
    source_system   VARCHAR(100),
    created_at      TIMESTAMP DEFAULT NOW(),
    created_by      VARCHAR(100),

    -- 授权控制
    requires_explicit_auth BOOLEAN DEFAULT TRUE,
    auth_expiry    TIMESTAMP,

    UNIQUE(document_id)
);

-- 2. 用户权限表
CREATE TABLE IF NOT EXISTS user_permissions (
    id              SERIAL PRIMARY KEY,
    user_id         VARCHAR(100) NOT NULL,
    username        VARCHAR(100) NOT NULL,
    security_level  VARCHAR(20) NOT NULL CHECK (security_level IN ('internal', 'confidential', 'restricted')),
    granted_by      VARCHAR(100),
    granted_at      TIMESTAMP DEFAULT NOW(),
    expires_at      TIMESTAMP,
    is_active       BOOLEAN DEFAULT TRUE,
    reason          TEXT,

    -- 约束：同一用户同一级别只能有一条有效记录
    UNIQUE(user_id, security_level) WHERE is_active = TRUE
);

-- 3. 访问审计日志表
CREATE TABLE IF NOT EXISTS access_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(100) NOT NULL,
    username        VARCHAR(100),
    document_id     INTEGER,
    security_level  VARCHAR(20),
    action          VARCHAR(20) NOT NULL CHECK (action IN ('view', 'download', 'export', 'search', 'denied')),
    access_time     TIMESTAMP DEFAULT NOW(),
    ip_address      INET,
    user_agent      TEXT,
    result          VARCHAR(20) DEFAULT 'success' CHECK (result IN ('success', 'denied', 'error')),
    denial_reason   TEXT,
    session_id      VARCHAR(100),

    -- 自动过期策略（默认保留90天）
    expires_at      TIMESTAMP DEFAULT (NOW() + INTERVAL '90 days')
);

-- 4. 临时授权表（用于临时访问）
CREATE TABLE IF NOT EXISTS temporary_access_grants (
    id              SERIAL PRIMARY KEY,
    grant_code      VARCHAR(50) UNIQUE NOT NULL,
    user_id         VARCHAR(100),
    security_level  VARCHAR(20) NOT NULL,
    document_ids    INTEGER[] DEFAULT NULL,  -- NULL 表示全部该级别文档
    granted_by      VARCHAR(100) NOT NULL,
    granted_at      TIMESTAMP DEFAULT NOW(),
    expires_at      TIMESTAMP NOT NULL,
    max_access_count INTEGER DEFAULT NULL,
    access_count    INTEGER DEFAULT 0,
    reason          TEXT,
    is_active       BOOLEAN DEFAULT TRUE
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_confidential_doc_level
    ON documents_confidential(security_level) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_confidential_doc_id
    ON documents_confidential(document_id);

CREATE INDEX IF NOT EXISTS idx_user_permissions_user
    ON user_permissions(user_id, is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_user_permissions_level
    ON user_permissions(security_level, is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_audit_log_user_time
    ON access_audit_log(user_id, access_time DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_doc_time
    ON access_audit_log(document_id, access_time DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_action_time
    ON access_audit_log(action, access_time DESC);

CREATE INDEX IF NOT EXISTS idx_temp_grant_code
    ON temporary_access_grants(grant_code) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_temp_grant_expiry
    ON temporary_access_grants(expires_at) WHERE is_active = TRUE;

-- 触发器：自动标记过期授权为无效
CREATE OR REPLACE FUNCTION check_temp_grant_expiry()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.expires_at < NOW() THEN
        NEW.is_active := FALSE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_temp_grant_expiry ON temporary_access_grants;
CREATE TRIGGER trigger_temp_grant_expiry
BEFORE INSERT OR UPDATE ON temporary_access_grants
FOR EACH ROW
EXECUTE FUNCTION check_temp_grant_expiry();

-- 触发器：记录访问时检查临时授权次数
CREATE OR REPLACE FUNCTION check_temp_grant_access_count()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.result = 'success' THEN
        UPDATE temporary_access_grants
        SET access_count = access_count + 1,
            is_active = CASE
                WHEN max_access_count IS NOT NULL AND access_count + 1 >= max_access_count
                THEN FALSE
                ELSE is_active
            END
        WHERE grant_code IN (
            SELECT grant_code FROM user_permissions
            WHERE user_id = NEW.user_id
        ) AND is_active = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 迁移 006: 创建安全视图
-- =====================================================

-- 公开文档视图（不含保密文档）
CREATE OR REPLACE VIEW v_public_documents AS
SELECT d.*
FROM documents d
LEFT JOIN documents_confidential dc ON d.id = dc.document_id
WHERE dc.document_id IS NULL
   OR d.category != '气功';

-- 用户可访问文档视图
CREATE OR REPLACE VIEW v_user_accessible_documents AS
SELECT d.*
FROM documents d
LEFT JOIN documents_confidential dc ON d.id = dc.document_id
WHERE dc.document_id IS NULL  -- 非保密文档全部可访问
   OR NOT EXISTS (
       SELECT 1 FROM documents_confidential dc2
       WHERE dc2.document_id = d.id
         AND dc2.security_level IN ('confidential', 'restricted')
   );

-- 访问统计视图
CREATE OR REPLACE VIEW v_access_statistics AS
SELECT
    DATE(access_time) AS access_date,
    security_level,
    action,
    result,
    COUNT(*) AS access_count
FROM access_audit_log
GROUP BY DATE(access_time), security_level, action, result
ORDER BY access_date DESC, security_level, action;

-- =====================================================
-- 迁移 007: 安全辅助函数
-- =====================================================

-- 检查用户是否有访问权限
CREATE OR REPLACE FUNCTION check_user_access(
    p_user_id VARCHAR,
    p_security_level VARCHAR
) RETURNS BOOLEAN AS $$
DECLARE
    v_has_permission BOOLEAN := FALSE;
BEGIN
    -- 超级管理员检查
    IF EXISTS (
        SELECT 1 FROM user_permissions
        WHERE user_id = p_user_id
          AND security_level = 'restricted'
          AND is_active = TRUE
          AND (expires_at IS NULL OR expires_at > NOW())
    ) THEN
        RETURN TRUE;
    END IF;

    -- 检查具体级别权限
    IF p_security_level = 'public' THEN
        RETURN TRUE;
    ELSIF p_security_level = 'internal' THEN
        SELECT EXISTS (
            SELECT 1 FROM user_permissions
            WHERE user_id = p_user_id
              AND security_level IN ('internal', 'confidential', 'restricted')
              AND is_active = TRUE
              AND (expires_at IS NULL OR expires_at > NOW())
        ) INTO v_has_permission;
    ELSIF p_security_level IN ('confidential', 'restricted') THEN
        SELECT EXISTS (
            SELECT 1 FROM user_permissions
            WHERE user_id = p_user_id
              AND security_level = p_security_level
              AND is_active = TRUE
              AND (expires_at IS NULL OR expires_at > NOW())
        ) INTO v_has_permission;
    END IF;

    -- 检查临时授权
    IF NOT v_has_permission THEN
        SELECT EXISTS (
            SELECT 1 FROM temporary_access_grants
            WHERE user_id = p_user_id
              AND security_level = p_security_level
              AND is_active = TRUE
              AND expires_at > NOW()
              AND (max_access_count IS NULL OR access_count < max_access_count)
        ) INTO v_has_permission;
    END IF;

    RETURN v_has_permission;
END;
$$ LANGUAGE plpgsql;

-- 记录访问日志
CREATE OR REPLACE FUNCTION log_access(
    p_user_id VARCHAR,
    p_username VARCHAR DEFAULT NULL,
    p_document_id INTEGER DEFAULT NULL,
    p_security_level VARCHAR DEFAULT NULL,
    p_action VARCHAR,
    p_result VARCHAR DEFAULT 'success',
    p_denial_reason VARCHAR DEFAULT NULL
) RETURNS BIGINT AS $$
DECLARE
    v_log_id BIGINT;
BEGIN
    INSERT INTO access_audit_log (
        user_id, username, document_id, security_level,
        action, result, denial_reason
    ) VALUES (
        p_user_id, p_username, p_document_id, p_security_level,
        p_action, p_result, p_denial_reason
    ) RETURNING id INTO v_log_id;

    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql;

-- 授予用户权限
CREATE OR REPLACE FUNCTION grant_permission(
    p_user_id VARCHAR,
    p_username VARCHAR,
    p_security_level VARCHAR,
    p_granted_by VARCHAR,
    p_expires_at TIMESTAMP DEFAULT NULL,
    p_reason VARCHAR DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_perm_id INTEGER;
BEGIN
    INSERT INTO user_permissions (
        user_id, username, security_level,
        granted_by, expires_at, reason
    ) VALUES (
        p_user_id, p_username, p_security_level,
        p_granted_by, p_expires_at, p_reason
    ) ON CONFLICT (user_id, security_level)
      DO UPDATE SET
        is_active = TRUE,
        expires_at = COALESCE(p_expires_at, user_permissions.expires_at),
        granted_by = p_granted_by,
        reason = p_reason,
        granted_at = NOW()
    RETURNING id INTO v_perm_id;

    -- 记录授权日志
    PERFORM log_access(
        p_granted_by, p_granted_by, NULL, p_security_level,
        'grant_permission', 'success', NULL
    );

    RETURN v_perm_id;
END;
$$ LANGUAGE plpgsql;

-- 撤销用户权限
CREATE OR REPLACE FUNCTION revoke_permission(
    p_user_id VARCHAR,
    p_security_level VARCHAR,
    p_revoked_by VARCHAR
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE user_permissions
    SET is_active = FALSE
    WHERE user_id = p_user_id
      AND security_level = p_security_level;

    -- 记录撤销日志
    PERFORM log_access(
        p_revoked_by, p_revoked_by, NULL, p_security_level,
        'revoke_permission', 'success', NULL
    );

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 回滚脚本（如需回滚）
-- =====================================================

-- DROP VIEW IF EXISTS v_access_statistics;
-- DROP VIEW IF EXISTS v_user_accessible_documents;
-- DROP VIEW IF EXISTS v_public_documents;
-- DROP FUNCTION IF EXISTS revoke_permission;
-- DROP FUNCTION IF EXISTS grant_permission;
-- DROP FUNCTION IF EXISTS log_access;
-- DROP FUNCTION IF EXISTS check_user_access;
-- DROP TRIGGER IF EXISTS trigger_temp_grant_expiry ON temporary_access_grants;
-- DROP FUNCTION IF EXISTS check_temp_grant_access_count;
-- DROP FUNCTION IF EXISTS check_temp_grant_expiry;
-- DROP TABLE IF EXISTS temporary_access_grants;
-- DROP TABLE IF EXISTS access_audit_log;
-- DROP TABLE IF EXISTS user_permissions;
-- DROP TABLE IF EXISTS documents_confidential;
