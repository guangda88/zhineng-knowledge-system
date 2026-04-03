# 数据导入审计报告

> **审计日期**: 2026-04-03
> **审计范围**: 全部数据导入工作（sys_books、guji_documents、textbook、embedding）
> **审计原因**: 发现多项任务报告"已完成"但实际存在问题

---

## 一、发现的问题

### P0-1: BGE-M3 模型不完整，Embedding 服务持续崩溃 5 天

| 项目 | 详情 |
|------|------|
| 现象 | 容器 `zhineng-embedding` 自 3/30 22:24 起反复崩溃重启 |
| 根因 | Docker volume `embedding_cache` 为空；宿主机模型仅 4.3MB（完整应 ~2.2GB） |
| 触发链 | `SentenceTransformer("BAAI/bge-m3")` → 本地无缓存 → 尝试 HuggingFace → 容器无外网 → `[Errno 101] Network is unreachable` → 崩溃 → restart 循环 |
| 影响 | 全部向量嵌入工作阻塞；API 服务因 `depends_on: condition: service_healthy` 存在启动风险 |
| 代码缺陷 | `embedding_service.py:57` 无离线模式、无本地路径检测、无模型缺失的优雅降级 |

**修复方案**:
```yaml
# docker-compose.yml — 挂载宿主机模型目录
volumes:
  - /home/ai/ai-knowledge-base/data/models/bge-m3:/model:ro
  - embedding_cache:/cache

environment:
  EMBEDDING_MODEL: /model    # 使用本地路径而非 HuggingFace ID
```

**防护措施**:
- [ ] 添加模型文件存在性检查（启动前验证 `config.json` + `model.safetensors`）
- [ ] 添加 `TRANSFORMERS_OFFLINE=1` 环境变量，禁止静默联网下载
- [ ] 添加 healthcheck 重试上限（超过 N 次标记 unhealthy 而非无限重启）
- [ ] 把 API 对 embedding 的依赖从硬依赖改为软依赖（`condition: service_started`）

---

### P0-2: GIN 索引构建缓慢（预计 25+ 小时）

| 项目 | 详情 |
|------|------|
| 现象 | 3 个 GIN 索引在 263K 行/4.4GB 的 `guji_documents` 上已运行 2.5h，仅 10% |
| 根因 | `maintenance_work_mem=64MB`（默认值）；HDD I/O 83% 占用；3 索引串行在单事务中 |
| SQL 来源 | `scripts/complete_guji_mapping.sql` 的 `BEGIN...COMMIT` 块 |
| 影响 | 锁表阻塞 COUNT 查询和 ANALYZE，无法验证数据完整性 |

**修复方案**:
```sql
-- 1. 杀掉当前索引构建（pid 41987）
SELECT pg_terminate_backend(41987);

-- 2. 调大 maintenance_work_mem（仅当前会话）
SET maintenance_work_mem = '512MB';

-- 3. 用 CONCURRENTLY 逐个构建（不锁表）
CREATE INDEX CONCURRENTLY idx_guji_content_source
  ON guji_documents(source_table, source_id);
CREATE INDEX CONCURRENTLY idx_guji_title
  ON guji_documents USING gin(to_tsvector('simple', title));
CREATE INDEX CONCURRENTLY idx_guji_content
  ON guji_documents USING gin(to_tsvector('simple', content));
```

**防护措施**:
- [ ] 任何 `CREATE INDEX` 脚本对大表（>10万行）必须使用 `CONCURRENTLY`
- [ ] 导入脚本中禁止 `BEGIN...多个 CREATE INDEX...COMMIT` 的模式
- [ ] 在脚本中添加 `SET maintenance_work_mem = '512MB'` 前置语句
- [ ] 调优 PostgreSQL 配置（见 P1-3）

---

### P0-3: API 服务硬依赖不健康的 Embedding 服务

| 项目 | 详情 |
|------|------|
| 现象 | `docker-compose.yml` 中 `api.depends_on.embedding.condition: service_healthy` |
| 根因 | Embedding 服务永远无法 healthy → Docker 重启后 API 可能启动失败 |
| 影响 | 整个系统可用性被一个不相关的服务阻塞 |

**修复方案**:
```yaml
# 改为软依赖
api:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    embedding:
      condition: service_started   # 不等 healthcheck
```

**防护措施**:
- [ ] 核心服务（API、数据库、缓存）不应硬依赖可选服务
- [ ] API 代码中用 try/except 处理 embedding 服务不可用的情况

---

### P1-1: 数据完整性无法确认——pg_stat 统计从未更新

| 表名 | reltuples（估算） | disk_size | n_tup_ins | last_analyze | 实际判断 |
|------|-------------------|-----------|-----------|-------------|---------|
| sys_books | 3,024,428 | 2.6GB | 0 | NULL | **数据存在**（COPY 导入不触发计数器） |
| sys_books_archive | 3,024,428 | 2.0GB | 0 | NULL | **数据存在** |
| guji_documents | 263,512 | 4.4GB | 284,421 | NULL | **数据存在** |
| textbook_blocks | 10,226 | 108MB | 0 | NULL | **数据存在** |
| textbook_nodes | 2,989 | 8.9KB | 0 | NULL | **数据存在** |
| textbook_blocks_v2 | 1,123 | 22MB | 0 | NULL | **数据存在** |
| textbook_toc | 820 | 688KB | 0 | NULL | **数据存在** |
| documents | 103,240 | 894MB | 0 | NULL | **数据存在** |
| guoxue_content | 263,767 | 5.6GB | 0 | NULL | **数据存在** |
| **books** | **-1** | **8 bytes** | 0 | NULL | **❌ 空** |
| **sys_book_chunks** | **-1** | **0 bytes** | 0 | NULL | **❌ 空** |

**根因**: 所有 COPY 导入后没有执行 `ANALYZE`，autovacuum 因 `n_tup_ins=0` 不会自动触发

**修复方案**:
```sql
-- 对所有有数据的表运行 ANALYZE
ANALYZE sys_books;
ANALYZE guji_documents;
ANALYZE textbook_blocks;
ANALYZE textbook_nodes;
ANALYZE textbook_blocks_v2;
ANALYZE textbook_toc;
ANALYZE documents;
ANALYZE guoxue_content;
```

**防护措施**:
- [ ] 所有导入脚本必须在导入完成后执行 `ANALYZE <table>`
- [ ] 导入后必须执行 `SELECT COUNT(*) FROM <table>` 并打印结果
- [ ] 禁止使用 `pg_stat_user_tables.n_live_tup` 作为判断数据是否存在的依据

---

### P1-2: PostgreSQL 配置全部使用默认值

| 参数 | 当前值 | 推荐值（32GB RAM） | 说明 |
|------|--------|-------------------|------|
| `shared_buffers` | 128MB | 4GB | 缓存严重不足 |
| `work_mem` | 4MB | 128MB | 排序/哈希性能差 |
| `maintenance_work_mem` | 64MB | 1GB | CREATE INDEX 极慢 |
| `effective_cache_size` | 4GB | 24GB | 规划器低估缓存 |
| `max_wal_size` | 1GB | 4GB | WAL 可能不够 |

**修复方案**:
在 `docker-compose.yml` 的 postgres command 或 `postgresql.conf` 中设置：
```
shared_buffers = 4GB
work_mem = 128MB
maintenance_work_mem = 1GB
effective_cache_size = 24GB
max_wal_size = 4GB
```

**防护措施**:
- [ ] PostgreSQL 容器启动时必须加载自定义配置，不允许使用默认值
- [ ] 添加配置检查脚本到 `scripts/health_check.sh`

---

### P1-3: books 和 sys_book_chunks 确实为空

这两个表从未被成功导入数据：
- `books`：8 bytes 表数据，1.2MB 索引（空表+索引结构）
- `sys_book_chunks`：0 bytes 表数据（完全空）

**需要完成的导入**:
- `books`：需要从 `sys_books` 或其他源导入结构化书目数据
- `sys_book_chunks`：需要内容提取（依赖 2.9M 文件的网络盘访问）

---

### P2-1: 导入脚本缺乏幂等性和验证

| 问题 | 影响 |
|------|------|
| `import_guji_copy.py` 先 TRUNCATE 再 COPY | 中途失败数据全丢 |
| 没有导入后 COUNT 验证 | 不知道实际导入了多少行 |
| `guji_import_log` 表为空 | 没有导入历史记录 |
| 无 ANALYZE | 查询优化器统计信息错误 |

**防护措施**:
- [ ] 导入脚本模板：CREATE → COPY → COUNT → ANALYZE → LOG
- [ ] 禁止 TRUNCATE + COPY 模式，改用 INSERT ON CONFLICT 或临时表 + SWAP
- [ ] 每次导入必须写入 `import_log` 表

---

### P2-2: 50 个后台 Shell 限制被占满

- 之前的监控脚本没有清理
- 阻塞后续操作

**防护措施**:
- [ ] 监控脚本必须设置超时自动退出
- [ ] 定期清理 `job_kill` 不再需要的后台任务

---

## 二、根因链路图

```
                    根本原因                        直接后果                    连锁影响
                    ────────                        ────────                    ────────
1. 模型文件不完整 ─────────→ 无法加载 ─────────────→ Embedding 服务崩溃循环 ──→ 向量生成完全阻塞
   (4.3MB/2.2GB)              容器无外网                                     API 启动风险

2. PG 默认配置 ────────────→ maintenance_work_mem ──→ GIN 索引 25h+ ─────────→ 锁表阻塞验证
   (64MB for 4.4GB table)      太小                                          无法 ANALYZE

3. 导入脚本无 ANALYZE ─────→ pg_stat 统计不准 ─────→ 误判数据是否存在 ──────→ 虚假"已完成"报告

4. 无导入后验证 ───────────→ 不知道实际导入了什么 ──→ books/sys_book_chunks ──→ 空表未被发现
                                                                      为空未发现

5. 硬依赖链 ──────────────→ API depends_on embedding ──→ 系统级联故障风险      → 全系统不可用
   (docker-compose)            healthy
```

---

## 三、必须执行的修复措施清单

### 立即执行

| # | 操作 | 命令 |
|---|------|------|
| 1 | 终止阻塞的 GIN 索引构建 | `SELECT pg_terminate_backend(41987);` |
| 2 | 调优 PostgreSQL 配置 | 修改 docker-compose.yml postgres command |
| 3 | 对所有表执行 ANALYZE | `ANALYZE;`（全库） |
| 4 | 修复 Embedding 服务 | 挂载本地模型 + 环境变量改为本地路径 |
| 5 | 修改 API 依赖为软依赖 | `condition: service_started` |

### 验证数据

| # | 操作 |
|---|------|
| 6 | 对每个表执行 `SELECT COUNT(*)` 获取真实行数 |
| 7 | 确认 `books` 和 `sys_book_chunks` 需要重新导入 |
| 8 | 使用 CONCURRENTLY 重建 guji 索引 |

### 防止再次发生

| # | 操作 | 文件 |
|---|------|------|
| 9 | 创建标准导入流程文档 | `docs/DATA_IMPORT_SOP.md` |
| 10 | 添加导入脚本模板（含验证+ANALYZE+LOG） | `scripts/templates/` |
| 11 | Embedding 服务添加模型存在性检查 | `embedding_service.py` |
| 12 | 添加 PG 配置验证到 healthcheck | `scripts/health_check.sh` |

---

## 四、标准数据导入流程（杜绝问题再发）

```bash
# 1. 导入前检查
echo "=== 导入前环境检查 ==="
docker exec <pg> psql -c "SHOW maintenance_work_mem;"  # 必须 >= 512MB
docker exec <pg> psql -c "SELECT pg_size_pretty(pg_database_size('zhineng_kb'));"
df -h /data  # 检查磁盘空间

# 2. 执行导入（使用事务+临时表模式）
#    a. 导入到临时表
#    b. 验证行数
#    c. RENAME 临时表为正式表

# 3. 导入后验证（必须！）
docker exec <pg> psql -d zhineng_kb -c "
    SELECT COUNT(*) AS actual_count FROM <table>;
    ANALYZE <table>;
    SELECT relname, reltuples::bigint FROM pg_class WHERE relname = '<table>';
"

# 4. 创建索引（大表必须 CONCURRENTLY）
docker exec <pg> psql -d zhineng_kb -c "
    SET maintenance_work_mem = '512MB';
    CREATE INDEX CONCURRENTLY idx_name ON table(col);
"

# 5. 记录导入日志
docker exec <pg> psql -d zhineng_kb -c "
    INSERT INTO import_log (table_name, rows_imported, import_time, status)
    VALUES ('<table>', <count>, NOW(), 'success');
"

# 6. 验证索引创建
docker exec <pg> psql -d zhineng_kb -c "
    SELECT indexname, idx_scan FROM pg_stat_user_indexes
    WHERE relname = '<table>';
"
```

---

## 五、当前待办事项（按优先级）

1. **终止 GIN 索引** → 用 CONCURRENTLY + 512MB maintenance_work_mem 重建
2. **修复 Embedding 服务** → 挂载本地模型 / 下载完整模型
3. **调优 PostgreSQL** → shared_buffers=4GB, maintenance_work_mem=1GB
4. **ANALYZE 全库** → 更新统计信息
5. **确认数据** → COUNT(*) 验证每个表
6. **导入 books / sys_book_chunks** → 需要内容提取流程
7. **生成向量嵌入** → 依赖 Embedding 服务修复后
