-- 灵信通信系统 — 灵字辈大家庭跨项目讨论框架
-- 创建时间: 2026-04-03

-- 灵字辈 Agent 档案
CREATE TABLE IF NOT EXISTS lingmessage_agents (
    agent_id VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    role_description TEXT NOT NULL,
    expertise TEXT[] DEFAULT '{}',
    project_url TEXT,
    personality_prompt TEXT NOT NULL,
    avatar_emoji VARCHAR(10) DEFAULT '🤖',
    is_active BOOLEAN DEFAULT true,
    intelligence_sources TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 讨论线程
CREATE TABLE IF NOT EXISTS lingmessage_threads (
    id SERIAL PRIMARY KEY,
    topic VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active',
    priority VARCHAR(20) DEFAULT 'normal',
    max_rounds INTEGER DEFAULT 10,
    current_round INTEGER DEFAULT 0,
    created_by VARCHAR(50) REFERENCES lingmessage_agents(agent_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE,
    summary TEXT,
    key_decisions JSONB DEFAULT '[]'
);

-- 消息
CREATE TABLE IF NOT EXISTS lingmessage_messages (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES lingmessage_threads(id) ON DELETE CASCADE,
    agent_id VARCHAR(50) NOT NULL REFERENCES lingmessage_agents(agent_id),
    parent_id INTEGER REFERENCES lingmessage_messages(id),
    round_number INTEGER DEFAULT 0,
    content TEXT NOT NULL,
    message_type VARCHAR(20) DEFAULT 'response',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 共识追踪
CREATE TABLE IF NOT EXISTS lingmessage_consensus (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES lingmessage_threads(id) ON DELETE CASCADE,
    topic_aspect VARCHAR(500) NOT NULL,
    consensus_text TEXT NOT NULL,
    agreeing_agents TEXT[] NOT NULL,
    disagreeing_agents TEXT[] DEFAULT '{}',
    confidence REAL DEFAULT 0.8,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_lingmsg_thread_status ON lingmessage_threads(status);
CREATE INDEX IF NOT EXISTS idx_lingmsg_msg_thread ON lingmessage_messages(thread_id, round_number);
CREATE INDEX IF NOT EXISTS idx_lingmsg_msg_agent ON lingmessage_messages(agent_id);
CREATE INDEX IF NOT EXISTS idx_lingmsg_consensus_thread ON lingmessage_consensus(thread_id);

-- 触发器
CREATE OR REPLACE FUNCTION update_lingmessage_agent_ts()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_lingmsg_agent_ts ON lingmessage_agents;
CREATE TRIGGER trigger_lingmsg_agent_ts
    BEFORE UPDATE ON lingmessage_agents
    FOR EACH ROW EXECUTE FUNCTION update_lingmessage_agent_ts();
