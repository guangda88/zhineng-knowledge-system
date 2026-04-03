-- 自学习和自进化系统数据库迁移
-- 版本: 1.0.0
-- 日期: 2026-04-01
-- 目的: 支持多AI对比学习、用户行为追踪、自动进化

-- ============================================
-- 表1: 多AI对比记录
-- ============================================
CREATE TABLE IF NOT EXISTS ai_comparison_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,  -- 登录用户ID（可为空）
    session_id VARCHAR(36) NOT NULL,  -- 会话ID

    -- 请求信息
    request_type VARCHAR(50) NOT NULL,  -- 'qa', 'podcast', 'other'
    user_query TEXT,  -- 用户问题或请求
    request_id VARCHAR(36),  -- 关联原始请求ID

    -- 灵知系统回答
    lingzhi_response TEXT,
    lingzhi_metadata JSONB DEFAULT '{}',

    -- 其他AI回答
    competitor_responses JSONB,  -- {hunyuan: {...}, doubao: {...}, ...}

    -- 对比评估
    comparison_metrics JSONB,  -- {scores: {...}, winner: "...", ...}
    winner VARCHAR(50),  -- 'lingzhi', 'hunyuan', 'doubao', ...

    -- 用户行为
    user_behavior JSONB,  -- {focus_points: [...], dwell_time: {...}, ...}
    user_feedback VARCHAR(10),  -- 'good', 'neutral', 'poor'
    user_comment TEXT,
    user_preference VARCHAR(50),  -- 用户更喜欢哪个

    -- 进化方向
    improvement_suggestions TEXT,
    improvement_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'reviewing', 'implementing', 'completed'
    implemented_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),

    -- 约束
    CONSTRAINT valid_request_type CHECK (request_type IN ('qa', 'podcast', 'other')),
    CONSTRAINT valid_winner CHECK (winner IN ('lingzhi', 'hunyuan', 'doubao', 'deepseek', 'glm', 'tie')),
    CONSTRAINT valid_improvement_status CHECK (improvement_status IN ('pending', 'reviewing', 'implementing', 'completed', 'rejected'))
);

-- 索引
CREATE INDEX idx_ai_comparison_user_id ON ai_comparison_log(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_ai_comparison_session_id ON ai_comparison_log(session_id);
CREATE INDEX idx_ai_comparison_request_type ON ai_comparison_log(request_type);
CREATE INDEX idx_ai_comparison_winner ON ai_comparison_log(winner);
CREATE INDEX idx_ai_comparison_created_at ON ai_comparison_log(created_at DESC);

-- 评论：记录每次多AI对比的结果和用户反馈

-- ============================================
-- 表2: 进化记录
-- ============================================
CREATE TABLE IF NOT EXISTS evolution_log (
    id BIGSERIAL PRIMARY KEY,
    comparison_id BIGINT REFERENCES ai_comparison_log(id) ON DELETE SET NULL,

    -- 发现的问题
    issue_type VARCHAR(100),
    issue_category VARCHAR(50),  -- 'knowledge', 'template', 'quality', 'performance'
    issue_description TEXT,

    -- 改进措施
    improvement_type VARCHAR(100),  -- 'knowledge_update', 'template_optimize', 'prompt_tune', 'bug_fix'
    improvement_action TEXT,
    improvement_details JSONB DEFAULT '{}',

    -- 执行状态
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'rolled_back'
    priority VARCHAR(20) DEFAULT 'medium',  -- 'critical', 'high', 'medium', 'low'

    -- 效果验证
    before_metrics JSONB,
    after_metrics JSONB,
    effectiveness_score INTEGER,  -- 1-5
    verified_at TIMESTAMP,

    -- 元数据
    created_at TIMESTAMP DEFAULT NOW(),
    implemented_at TIMESTAMP,
    implemented_by VARCHAR(100),  -- 'auto', 'user:xxx', 'admin:xxx'

    -- 约束
    CONSTRAINT valid_evolution_status CHECK (status IN ('pending', 'in_progress', 'completed', 'rolled_back')),
    CONSTRAINT valid_evolution_priority CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    CONSTRAINT valid_effectiveness_score CHECK (effectiveness_score BETWEEN 1 AND 5)
);

-- 索引
CREATE INDEX idx_evolution_comparison_id ON evolution_log(comparison_id);
CREATE INDEX idx_evolution_status ON evolution_log(status);
CREATE INDEX idx_evolution_priority ON evolution_log(priority);
CREATE INDEX idx_evolution_category ON evolution_log(issue_category);
CREATE INDEX idx_evolution_created_at ON evolution_log(created_at DESC);

-- 评论：记录系统自我进化的历史

-- ============================================
-- 表3: 用户焦点追踪
-- ============================================
CREATE TABLE IF NOT EXISTS user_focus_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    session_id VARCHAR(36) NOT NULL,
    request_id VARCHAR(36) NOT NULL,  -- 关联ai_comparison_log或user_activity_log

    -- 焦点数据
    element_id VARCHAR(100),  -- DOM元素ID或选择器
    element_type VARCHAR(50),  -- 'heading', 'paragraph', 'link', 'button', 'image', ...
    element_content TEXT,  -- 匿名化后的内容摘要（可选）

    -- 交互数据
    dwell_time_ms INTEGER,  -- 停留时间（毫秒）
    scroll_depth INTEGER,  -- 滚动深度（像素）
    click_count INTEGER DEFAULT 0,  -- 点击次数

    -- 视口位置
    viewport_position JSONB,  -- {x: 100, y: 200, width: 300, height: 400}

    -- 上下文
    viewport_size JSONB,  -- {width: 1920, height: 1080}
    device_info JSONB,  -- {user_agent: "...", screen: {...}}

    timestamp TIMESTAMP DEFAULT NOW(),

    -- 约束
    CONSTRAINT valid_element_type CHECK (element_type IN ('heading', 'paragraph', 'link', 'button', 'image', 'list', 'code', 'quote', 'other'))
);

-- 索引
CREATE INDEX idx_focus_user_id ON user_focus_log(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_focus_session_id ON user_focus_log(session_id);
CREATE INDEX idx_focus_request_id ON user_focus_log(request_id);
CREATE INDEX idx_focus_element_id ON user_focus_log(element_id);
CREATE INDEX idx_focus_timestamp ON user_focus_log(timestamp DESC);

-- 评论：记录用户在页面上的焦点移动和停留时间，用于分析兴趣点

-- ============================================
-- 表4: AI性能统计
-- ============================================
CREATE TABLE IF NOT EXISTS ai_performance_stats (
    id BIGSERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,  -- 'lingzhi', 'hunyuan', ...
    model VARCHAR(100),

    -- 性能指标
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    avg_latency_ms INTEGER,
    p95_latency_ms INTEGER,
    p99_latency_ms INTEGER,

    -- 对比统计
    comparisons_participated INTEGER DEFAULT 0,
    comparisons_won INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 2),

    -- 用户偏好
    preferred_by_users INTEGER DEFAULT 0,

    -- 时间窗口
    period_start TIMESTAMP DEFAULT NOW(),
    period_end TIMESTAMP,

    updated_at TIMESTAMP DEFAULT NOW(),

    -- 约束
    CONSTRAINT valid_provider CHECK (provider IN ('lingzhi', 'hunyuan', 'doubao', 'deepseek', 'glm'))
);

-- 索引
CREATE INDEX idx_ai_perf_provider ON ai_performance_stats(provider);
CREATE INDEX idx_ai_perf_period_start ON ai_performance_stats(period_start DESC);

-- 评论：统计各AI的性能指标，用于对比和选型

-- ============================================
-- 触发器：自动更新updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_ai_perf_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_ai_perf_stats_updated_at
    BEFORE UPDATE ON ai_performance_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_ai_perf_updated_at();

-- ============================================
-- 视图：AI对比摘要
-- ============================================
CREATE OR REPLACE VIEW v_ai_comparison_summary AS
SELECT
    DATE_TRUNC('day', created_at) AS date,
    request_type,
    COUNT(*) AS total_comparisons,
    winner,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY DATE_TRUNC('day', created_at), request_type) AS win_rate
FROM ai_comparison_log
WHERE created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', created_at), request_type, winner
ORDER BY date DESC, request_type, winner;

-- 评论：按日期和请求类型统计各AI的胜率

-- ============================================
-- 视图：进化趋势
-- ============================================
CREATE OR REPLACE VIEW v_evolution_trends AS
SELECT
    DATE_TRUNC('week', created_at) AS week,
    issue_category,
    COUNT(*) AS total_issues,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS resolved_issues,
    AVG(effectiveness_score) FILTER (WHERE effectiveness_score IS NOT NULL) AS avg_effectiveness
FROM evolution_log
WHERE created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('week', created_at), issue_category
ORDER BY week DESC, issue_category;

-- 评论：按周统计问题发现和解决趋势

-- ============================================
-- 实用函数：更新AI性能统计
-- ============================================
CREATE OR REPLACE FUNCTION update_ai_performance_stats(
    p_provider VARCHAR,
    p_success BOOLEAN,
    p_latency_ms INTEGER
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO ai_performance_stats (provider, period_start)
    VALUES (p_provider, NOW())
    ON CONFLICT (provider, period_start)
    DO UPDATE SET
        total_requests = ai_performance_stats.total_requests + 1,
        successful_requests = ai_performance_stats.successful_requests + CASE WHEN p_success THEN 1 ELSE 0 END,
        failed_requests = ai_performance_stats.failed_requests + CASE WHEN NOT p_success THEN 1 ELSE 0 END,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 实用函数：记录AI对比并更新胜率
-- ============================================
CREATE OR REPLACE FUNCTION record_ai_comparison(
    p_winner VARCHAR,
    p_request_type VARCHAR
)
RETURNS VOID AS $$
BEGIN
    -- 更新参与方统计
    INSERT INTO ai_performance_stats (provider, period_start, comparisons_participated)
    VALUES (p_winner, NOW())
    ON CONFLICT (provider, period_start)
    DO UPDATE SET
        comparisons_participated = ai_performance_stats.comparisons_participated + 1,
        comparisons_won = ai_performance_stats.comparisons_won + 1,
        win_rate = (ai_performance_stats.comparisons_won + 1.0) / (ai_performance_stats.comparisons_participated + 1.0) * 100,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 数据清理策略
-- ============================================
-- 匿名用户焦点数据保留30天
-- DELETE FROM user_focus_log WHERE user_id IS NULL AND timestamp < NOW() - INTERVAL '30 days';

-- 已完成的进化记录保留1年
-- DELETE FROM evolution_log WHERE status = 'completed' AND implemented_at < NOW() - INTERVAL '1 year';

-- ============================================
-- 完成
-- ============================================

-- 添加注释
COMMENT ON TABLE ai_comparison_log IS '多AI对比记录：记录灵知系统与竞品AI的对比结果';
COMMENT ON TABLE evolution_log IS '进化记录：记录系统自我改进的历史';
COMMENT ON TABLE user_focus_log IS '用户焦点追踪：记录用户在页面上的注意力分布';
COMMENT ON TABLE ai_performance_stats IS 'AI性能统计：记录各AI的性能指标和胜率';

-- 权限设置（根据实际数据库用户调整）
-- GRANT SELECT, INSERT ON ai_comparison_log TO zhineng;
-- GRANT SELECT, INSERT ON evolution_log TO zhineng;
-- GRANT SELECT, INSERT ON user_focus_log TO zhineng;
-- GRANT SELECT, UPDATE ON ai_performance_stats TO zhineng;
-- GRANT SELECT ON v_ai_comparison_summary TO zhineng;
-- GRANT SELECT ON v_evolution_trends TO zhineng;
