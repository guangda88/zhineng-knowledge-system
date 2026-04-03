-- 生成任务追踪表
-- 版本: 1.0.0
-- 目的: 追踪内容生成任务的状态和输出

CREATE TABLE IF NOT EXISTS generation_tasks (
    id BIGSERIAL PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL UNIQUE,
    content_type VARCHAR(50) NOT NULL,
    topic TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    parameters JSONB DEFAULT '{}',
    output_path TEXT,
    output_format VARCHAR(20),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_generation_tasks_task_id ON generation_tasks(task_id);
CREATE INDEX idx_generation_tasks_status ON generation_tasks(status);
CREATE INDEX idx_generation_tasks_content_type ON generation_tasks(content_type);
CREATE INDEX idx_generation_tasks_created_at ON generation_tasks(created_at DESC);

COMMENT ON TABLE generation_tasks IS '内容生成任务追踪：记录生成任务的状态和输出';
