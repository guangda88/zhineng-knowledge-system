-- 智能知识系统 - 数据库初始化脚本
-- 遵循开发规则：表名小写复数、字段名小写下划线

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 文档表
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('气功', '中医', '儒家')),
    tags TEXT[] DEFAULT '{}',
    embedding vector(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);

-- 向量相似度索引
CREATE INDEX idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 聊天历史表
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_history_session ON chat_history(session_id, created_at);

-- 气功知识表（阶段2使用）
CREATE TABLE IF NOT EXISTS qigong_knowledge (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100),
    content TEXT NOT NULL,
    difficulty VARCHAR(20) CHECK (difficulty IN ('入门', '初级', '中级', '高级')),
    practice_time VARCHAR(100),
    notes TEXT,
    embedding vector(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_qigong_category ON qigong_knowledge(category);
CREATE INDEX idx_qigong_difficulty ON qigong_knowledge(difficulty);

-- 插入示例数据（阶段1使用）
INSERT INTO documents (title, content, category, tags) VALUES
    ('气功基础入门', '气功是中国传统养生方法，通过调身、调息、调心达到强身健体的目的。入门阶段需要掌握基础姿势和呼吸方法。', '气功', ARRAY['入门', '基础']),
    ('八段锦第一式', '双手托天理三焦：十字交叉手向上托起，脚跟离地，保持呼吸自然，重复8次。', '气功', ARRAY['八段锦', '功法']),
    ('站桩要领', '站桩是气功基础功法，要点：双脚与肩同宽，膝盖微曲，脊椎正直，双目微闭，呼吸自然。', '气功', ARRAY['站桩', '基础']),
    ('气功呼吸法', '腹式呼吸是气功基础呼吸法：吸气时腹部隆起，呼气时腹部收缩，呼吸细长匀静。', '气功', ARRAY['呼吸', '基础']),
    ('中医基础理论', '中医理论包括阴阳五行、气血津液、脏腑经络等，强调人体与自然的整体关系。', '中医', ARRAY['基础', '理论']),
    ('儒家修身', '儒家修身强调格物致知、诚意正心、修身齐家治国平天下的递进关系。', '儒家', ARRAY['修身', '基础']);

-- ============================================
-- 音频处理相关表
-- ============================================

-- 音频文件表
CREATE TABLE IF NOT EXISTS audio_files (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    original_name VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    duration FLOAT,
    format VARCHAR(20),
    size_bytes BIGINT,
    sample_rate INTEGER,
    channels INTEGER,
    status VARCHAR(50) DEFAULT 'uploaded',
    -- uploaded, transcribing, transcribed, failed
    tingwu_task_id VARCHAR(200),
    transcription_text TEXT,
    category VARCHAR(50),
    tags TEXT[] DEFAULT '{}',
    created_by VARCHAR(100) DEFAULT 'system',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audio_files_status ON audio_files(status);
CREATE INDEX IF NOT EXISTS idx_audio_files_category ON audio_files(category);
CREATE INDEX IF NOT EXISTS idx_audio_files_created_at ON audio_files(created_at DESC);

-- 音频分段表（转写结果）
CREATE TABLE IF NOT EXISTS audio_segments (
    id SERIAL PRIMARY KEY,
    audio_file_id INTEGER NOT NULL REFERENCES audio_files(id) ON DELETE CASCADE,
    segment_index INTEGER NOT NULL,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    text TEXT NOT NULL,
    speaker VARCHAR(100),
    confidence FLOAT,
    embedding vector(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audio_segments_file ON audio_segments(audio_file_id);
CREATE INDEX IF NOT EXISTS idx_audio_segments_embedding ON audio_segments USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 音频标注表（主表）
CREATE TABLE IF NOT EXISTS audio_annotations (
    id SERIAL PRIMARY KEY,
    audio_file_id INTEGER NOT NULL REFERENCES audio_files(id) ON DELETE CASCADE,
    segment_id INTEGER REFERENCES audio_segments(id) ON DELETE CASCADE,
    annotation_type VARCHAR(50) NOT NULL,
    -- correction, segment_label, highlight, knowledge_link,
    -- teaching_point, timestamp_note
    start_time FLOAT,
    end_time FLOAT,
    content TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active',
    verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(100),
    verified_at TIMESTAMP,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,
    parent_id INTEGER REFERENCES audio_annotations(id)
);

CREATE INDEX IF NOT EXISTS idx_annotations_audio ON audio_annotations(audio_file_id);
CREATE INDEX IF NOT EXISTS idx_annotations_segment ON audio_annotations(segment_id);
CREATE INDEX IF NOT EXISTS idx_annotations_type ON audio_annotations(annotation_type);
CREATE INDEX IF NOT EXISTS idx_annotations_time ON audio_annotations(start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_annotations_creator ON audio_annotations(created_by);
CREATE INDEX IF NOT EXISTS idx_annotations_status ON audio_annotations(status);
CREATE INDEX IF NOT EXISTS idx_annotations_content ON audio_annotations USING gin(to_tsvector('simple', content));

-- 标注标签表
CREATE TABLE IF NOT EXISTS annotation_labels (
    id SERIAL PRIMARY KEY,
    label_name VARCHAR(100) NOT NULL UNIQUE,
    label_category VARCHAR(50),
    color VARCHAR(20),
    description TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 标注-标签关联表（多对多）
CREATE TABLE IF NOT EXISTS annotation_label_relations (
    annotation_id INTEGER NOT NULL REFERENCES audio_annotations(id) ON DELETE CASCADE,
    label_id INTEGER NOT NULL REFERENCES annotation_labels(id) ON DELETE CASCADE,
    PRIMARY KEY (annotation_id, label_id)
);

-- 标注评论表（协作讨论）
CREATE TABLE IF NOT EXISTS annotation_comments (
    id SERIAL PRIMARY KEY,
    annotation_id INTEGER NOT NULL REFERENCES audio_annotations(id) ON DELETE CASCADE,
    comment_text TEXT NOT NULL,
    commented_by VARCHAR(100) NOT NULL,
    commented_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parent_comment_id INTEGER REFERENCES annotation_comments(id)
);

-- 标注变更历史（审计）
CREATE TABLE IF NOT EXISTS annotation_history (
    id SERIAL PRIMARY KEY,
    annotation_id INTEGER NOT NULL REFERENCES audio_annotations(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    changed_by VARCHAR(100) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 更新时间戳触发器函数（必须在触发器之前定义）
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- audio_files 更新时间戳触发器
CREATE TRIGGER trigger_audio_files_updated_at
    BEFORE UPDATE ON audio_files
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- audio_annotations 更新时间戳触发器
CREATE TRIGGER trigger_audio_annotations_updated_at
    BEFORE UPDATE ON audio_annotations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 生命周期追踪表 (Phase 1 Week 1)
-- ============================================

-- 用户等级表
CREATE TABLE IF NOT EXISTS user_levels (
    user_id VARCHAR(100) PRIMARY KEY,
    current_level VARCHAR(50) NOT NULL DEFAULT '入门',
    -- 入门, 初级, 中级, 高级
    level_history JSONB DEFAULT '[]',
    assessment_score FLOAT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trigger_user_levels_updated_at
    BEFORE UPDATE ON user_levels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- 生命状态追踪表
CREATE TABLE IF NOT EXISTS life_state_tracking (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL REFERENCES user_levels(user_id),
    tracked_date DATE NOT NULL DEFAULT CURRENT_DATE,
    physical_health INT CHECK (physical_health BETWEEN 1 AND 10),
    mental_peace INT CHECK (mental_peace BETWEEN 1 AND 10),
    energy_level INT CHECK (energy_level BETWEEN 1 AND 10),
    sleep_quality INT CHECK (sleep_quality BETWEEN 1 AND 10),
    emotional_stability INT CHECK (emotional_stability BETWEEN 1 AND 10),
    subjective_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_life_state_user ON life_state_tracking(user_id, tracked_date DESC);

-- 练习记录表
CREATE TABLE IF NOT EXISTS practice_records (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL REFERENCES user_levels(user_id),
    concept VARCHAR(200),
    practice_type VARCHAR(100),
    -- 站桩, 打坐, 八段锦, 呼吸法, 其他
    practice_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    duration_minutes INT,
    subjective_feeling TEXT,
    difficulty_level INT CHECK (difficulty_level BETWEEN 1 AND 5),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_practice_records_user ON practice_records(user_id, practice_date DESC);
CREATE INDEX idx_practice_records_type ON practice_records(practice_type);

-- 练习计划表
CREATE TABLE IF NOT EXISTS practice_plans (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL REFERENCES user_levels(user_id),
    plan_name VARCHAR(200) NOT NULL,
    goal TEXT,
    plan_type VARCHAR(50) DEFAULT 'manual',
    -- manual, ai_generated, template
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    -- active, completed, paused, abandoned
    daily_tasks JSONB DEFAULT '[]',
    milestones JSONB DEFAULT '[]',
    template_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trigger_practice_plans_updated_at
    BEFORE UPDATE ON practice_plans
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE INDEX idx_practice_plans_user ON practice_plans(user_id, status);
CREATE INDEX idx_practice_plans_dates ON practice_plans(start_date, end_date);
