-- 修复 user_profile 表以支持匿名用户
-- 问题：user_id 是 PRIMARY KEY 且 NOT NULL，但匿名用户没有 user_id
-- 解决：使 user_id 可为 NULL，使用代理主键

BEGIN;

-- 1. 删除现有主键约束
ALTER TABLE user_profile DROP CONSTRAINT user_profile_pkey;

-- 2. 使 user_id 可为 NULL
ALTER TABLE user_profile ALTER COLUMN user_id DROP NOT NULL;

-- 3. 添加新的代理主键
ALTER TABLE user_profile ADD COLUMN id BIGSERIAL PRIMARY KEY;

-- 4. 删除旧的 UNIQUE 约束（如果存在）
ALTER TABLE user_profile DROP CONSTRAINT IF EXISTS user_profile_session_id_key;

-- 5. 重新创建唯一约束（允许 NULL user_id）
-- 注意：NULL 值在唯一约束中被视为不同值，所以多个 NULL user_id 是允许的
CREATE UNIQUE INDEX idx_user_profile_user_id ON user_profile(user_id) WHERE user_id IS NOT NULL;

-- 6. 确保 session_id 对每个用户唯一（包括匿名用户）
CREATE UNIQUE INDEX idx_user_profile_session_id_unique ON user_profile(session_id) WHERE session_id IS NOT NULL;

COMMIT;

-- 验证修改
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'user_profile'
ORDER BY ordinal_position;
