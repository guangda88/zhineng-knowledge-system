-- 用户价值追踪与反馈系统
-- 版本: 1.0.0
-- 日期: 2026-04-01
-- 目的: 追踪用户使用情况，收集满意度反馈，验证系统价值

-- ============================================
-- 表1: 用户活动日志
-- ============================================
CREATE TABLE IF NOT EXISTS user_activity_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,  -- 登录用户ID（可为空，匿名用户）
    session_id VARCHAR(36) NOT NULL,  -- 会话ID（匿名或登录用户都有）

    -- 行为信息
    action_type VARCHAR(50) NOT NULL,  -- 'search', 'ask', 'audio_play', 'book_read'
    content TEXT,  -- 搜索关键词/问题/音频ID/书籍ID
    content_anonymous TEXT,  -- 匿名化后的内容（SHA-256 hash）

    -- 元数据
    metadata JSONB DEFAULT '{}',  -- {result_count: 10, response_time_ms: 150, clicked: true}

    -- 技术信息（用于防滥用和统计）
    ip_address INET,
    user_agent TEXT,

    created_at TIMESTAMP DEFAULT NOW(),

    -- 约束
    CONSTRAINT valid_action_type CHECK (action_type IN ('search', 'ask', 'audio_play', 'book_read', 'other'))
);

-- 索引
CREATE INDEX idx_activity_log_user_id ON user_activity_log(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_activity_log_session_id ON user_activity_log(session_id);
CREATE INDEX idx_activity_log_action_type ON user_activity_log(action_type);
CREATE INDEX idx_activity_log_created_at ON user_activity_log(created_at DESC);
CREATE INDEX idx_activity_log_user_date ON user_activity_log(user_id, created_at DESC) WHERE user_id IS NOT NULL;

-- 评论：用户活动日志，用于分析用户行为模式
-- 隐私：content字段根据用户隐私设置决定是否保留

-- ============================================
-- 表2: 用户反馈
-- ============================================
CREATE TABLE IF NOT EXISTS user_feedback (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,  -- 登录用户ID（可为空）
    session_id VARCHAR(36) NOT NULL,  -- 会话ID

    -- 反馈信息
    feedback_type VARCHAR(50) NOT NULL,  -- 'instant', 'weekly', 'monthly'
    rating VARCHAR(10) NOT NULL,  -- 'good', 'neutral', 'poor'
    comment TEXT,  -- 文字意见和建议

    -- 上下文信息
    context JSONB DEFAULT '{}',  -- {action_type: "ask", content_hash: "xxx", feature: "qa"}

    created_at TIMESTAMP DEFAULT NOW(),

    -- 约束
    CONSTRAINT valid_feedback_type CHECK (feedback_type IN ('instant', 'weekly', 'monthly', 'other')),
    CONSTRAINT valid_rating CHECK (rating IN ('good', 'neutral', 'poor'))
);

-- 索引
CREATE INDEX idx_feedback_user_id ON user_feedback(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_feedback_session_id ON user_feedback(session_id);
CREATE INDEX idx_feedback_rating ON user_feedback(rating);
CREATE INDEX idx_feedback_created_at ON user_feedback(created_at DESC);
CREATE INDEX idx_feedback_type_created ON user_feedback(feedback_type, created_at DESC);

-- 评论：用户满意度反馈，用于价值验证
-- 差评时comment建议必填，用于收集改进建议

-- ============================================
-- 表3: 用户状态（简化画像）
-- ============================================
CREATE TABLE IF NOT EXISTS user_profile (
    user_id UUID PRIMARY KEY,
    session_id VARCHAR(36) UNIQUE,  -- 匿名用户的临时ID（唯一）
    display_name VARCHAR(100),  -- 显示名称（可选）

    -- 用户等级
    level VARCHAR(20) DEFAULT 'guest',  -- 'guest', 'beginner', 'practitioner', 'advanced'

    -- 使用统计
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_active_at TIMESTAMP DEFAULT NOW(),
    total_sessions INTEGER DEFAULT 1,
    current_streak INTEGER DEFAULT 0,  -- 连续使用天数

    -- 反馈相关
    last_feedback_date DATE,

    -- 偏好设置
    preferences JSONB DEFAULT '{
        "privacy_mode": "standard",
        "feedback_frequency": "weekly",
        "data_retention_days": 90
    }',

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- 约束
    CONSTRAINT valid_level CHECK (level IN ('guest', 'beginner', 'practitioner', 'advanced')),
    CONSTRAINT valid_privacy_mode CHECK (preferences->>'privacy_mode' IN ('anonymous', 'standard', 'full'))
);

-- 索引
CREATE INDEX idx_user_profile_session_id ON user_profile(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_user_profile_level ON user_profile(level);
CREATE INDEX idx_user_profile_last_active ON user_profile(last_active_at DESC);

-- 评论：用户状态表，用于跟踪用户等级和使用习惯
-- 等级升级逻辑：guest → beginner (首次反馈) → practitioner (7天活跃) → advanced (30天活跃)

-- ============================================
-- 表4: 数据删除请求
-- ============================================
CREATE TABLE IF NOT EXISTS data_deletion_requests (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,  -- 可为空（匿名用户用session_id）
    session_id VARCHAR(36),
    contact_email VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'rejected'

    requested_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,

    -- 管理备注
    admin_notes TEXT,

    -- 约束
    CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'completed', 'rejected')),
    CONSTRAINT require_user_identifier CHECK (user_id IS NOT NULL OR session_id IS NOT NULL OR contact_email IS NOT NULL)
);

-- 索引
CREATE INDEX idx_deletion_status ON data_deletion_requests(status);
CREATE INDEX idx_deletion_user_id ON data_deletion_requests(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_deletion_session_id ON data_deletion_requests(session_id) WHERE session_id IS NOT NULL;

-- 评论：GDPR合规的数据删除请求跟踪表

-- ============================================
-- 触发器：自动更新 updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_profile_updated_at BEFORE UPDATE ON user_profile
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 视图：用户活动统计（用于管理员仪表板）
-- ============================================
CREATE OR REPLACE VIEW v_user_activity_stats AS
SELECT
    DATE_TRUNC('day', created_at) AS date,
    action_type,
    COUNT(DISTINCT session_id) AS unique_sessions,
    COUNT(*) AS total_actions,
    COUNT(DISTINCT user_id) AS unique_logged_in_users
FROM user_activity_log
WHERE created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', created_at), action_type
ORDER BY date DESC, action_type;

-- 评论：最近90天的用户活动统计，按日期和功能分组

-- ============================================
-- 视图：用户反馈统计
-- ============================================
CREATE OR REPLACE VIEW v_user_feedback_stats AS
SELECT
    DATE_TRUNC('day', created_at) AS date,
    feedback_type,
    rating,
    COUNT(*) AS count,
    COUNT(DISTINCT session_id) AS unique_sessions
FROM user_feedback
WHERE created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', created_at), feedback_type, rating
ORDER BY date DESC, feedback_type, rating;

-- 评论：最近90天的用户反馈统计，用于满意度趋势分析

-- ============================================
-- 实用函数：生成匿名会话ID
-- ============================================
CREATE OR REPLACE FUNCTION generate_session_id()
RETURNS VARCHAR(36) AS $$
BEGIN
    RETURN gen_random_uuid()::TEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 实用函数：匿名化内容（SHA-256 hash）
-- ============================================
CREATE OR REPLACE FUNCTION anonymize_content(content TEXT)
RETURNS VARCHAR(64) AS $$
BEGIN
    IF content IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN ENCODE(DIGEST(content, 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql;

-- 评论：用于敏感内容的匿名化，保留统计分析能力

-- ============================================
-- 实用函数：更新用户连续使用天数
-- ============================================
CREATE OR REPLACE FUNCTION update_user_streak(p_user_id UUID DEFAULT NULL, p_session_id VARCHAR DEFAULT NULL)
RETURNS INTEGER AS $$
DECLARE
    last_active_date DATE;
    streak INTEGER;
BEGIN
    IF p_user_id IS NOT NULL THEN
        SELECT DATE(last_active_at)::DATE INTO last_active_date
        FROM user_profile
        WHERE user_id = p_user_id;
    ELSE
        SELECT DATE(last_active_at)::DATE INTO last_active_date
        FROM user_profile
        WHERE session_id = p_session_id;
    END IF;

    IF NOT FOUND THEN
        RETURN 0;
    END IF;

    -- 如果昨天活跃，连续天数+1
    IF last_active_date = CURRENT_DATE - INTERVAL '1 day' THEN
        UPDATE user_profile
        SET current_streak = current_streak + 1,
            last_active_at = NOW()
        WHERE (user_id = p_user_id OR (p_user_id IS NULL AND session_id = p_session_id));
        RETURN current_streak + 1;
    -- 如果今天已经活跃，不更新
    ELSIF last_active_date = CURRENT_DATE THEN
        RETURN current_streak;
    -- 否则重置为1
    ELSE
        UPDATE user_profile
        SET current_streak = 1,
            last_active_at = NOW()
        WHERE (user_id = p_user_id OR (p_user_id IS NULL AND session_id = p_session_id));
        RETURN 1;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 数据保留策略：自动删除90天前的匿名数据
-- ============================================
-- 注意：这个策略需要通过cron job定期执行，不是自动触发
-- 示例：DELETE FROM user_activity_log WHERE user_id IS NULL AND created_at < NOW() - INTERVAL '90 days';

-- ============================================
-- 完成
-- ============================================

-- 添加注释
COMMENT ON TABLE user_activity_log IS '用户活动日志：追踪搜索、问答、音频、书籍等使用行为';
COMMENT ON TABLE user_feedback IS '用户反馈：收集满意度评价和改进建议';
COMMENT ON TABLE user_profile IS '用户状态：简化的用户画像，包含等级、使用统计、偏好设置';
COMMENT ON TABLE data_deletion_requests IS '数据删除请求：GDPR合规，记录用户删除数据的请求';

-- 权限设置（根据实际数据库用户调整）
-- GRANT SELECT, INSERT ON user_activity_log TO zhineng;
-- GRANT SELECT, INSERT ON user_feedback TO zhineng;
-- GRANT SELECT, UPDATE ON user_profile TO zhineng;
-- GRANT SELECT, INSERT ON data_deletion_requests TO zhineng;
-- GRANT SELECT ON v_user_activity_stats TO zhineng;
-- GRANT SELECT ON v_user_feedback_stats TO zhineng;
