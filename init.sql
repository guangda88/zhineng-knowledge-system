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
    embedding vector(1024),
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
    embedding vector(1024),
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

-- 更新时间戳触发器
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
