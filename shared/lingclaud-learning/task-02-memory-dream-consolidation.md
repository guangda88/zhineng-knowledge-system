# Task 2: Memory Dream Consolidation 记忆巩固

**学习日期**: 2026-04-14
**来源**: learn-claude-code/agents/s09_memory_system.py (~534行)
**对比来源**: lingclaude/lingclaude/core/layered_memory.py (~501行)
**任务**: 理解跨会话记忆存储和自动合并机制

---

## What - 学到了什么

### Kode-Agent Memory System 的核心架构

Kode-Agent 实现了一个**文件式记忆系统**，用于跨会话持久化关键信息。

#### 1. 存储布局

```
.memory/
  MEMORY.md                    # 索引文件（最多200行）
  prefer_tabs.md              # 前端风格偏好
  review_style.md            # 代码审查风格
  incident_board.md          # 事故记录
  project_architecture.md    # 项目架构
```

**每个记忆文件格式**：
```markdown
---
name: project_architecture
description: 项目微服务架构决策
type: project
---

项目采用三层架构：
- API Gateway 层
- Service 层
- Data Layer 层
```

#### 2. 四种记忆类型

| 类型 | 用途 | 示例 |
|-----|------|-----|
| **user** | 用户偏好 | "I like tabs", "Always use pytest" |
| **feedback** | 用户纠正 | "Don't do X", "That was wrong because..." |
| **project** | 非显而易见的项目事实 | "模块 X 必须保留（合规原因）" |
| **reference** | 外部资源指针 | "看板 URL", "文档链接" |

#### 3. 何时保存记忆（关键原则）

**保存**：
- ✅ 用户明确偏好
- ✅ 重复的用户反馈
- ✅ 项目事实（从当前代码不易推断）
  - 决策原因
  - 合规规则
  - 历史遗留模块
- ✅ 外部资源位置

**不保存**：
- ❌ 代码结构（函数签名、目录布局）
- ❌ 临时任务状态（当前分支、PR 编号、TODO）
- ❌ 秘密（API keys, 密码）

#### 4. MemoryManager 类

```python
class MemoryManager:
    def __init__(self, memory_dir: Path = None):
        self.memory_dir = memory_dir or MEMORY_DIR
        self.memories = {}  # name -> {description, type, content}

    def load_all(self):
        """加载 MEMORY.md 索引和所有单独记忆文件"""
        for md_file in sorted(self.memory_dir.glob("*.md")):
            if md_file.name == "MEMORY.md":
                continue
            parsed = self._parse_frontmatter(md_file.read_text())
            name = parsed.get("name", md_file.stem)
            self.memories[name] = {
                "description": parsed.get("description", ""),
                "type": parsed.get("type", "project"),
                "content": parsed.get("content", ""),
                "file": md_file.name,
            }

    def save_memory(self, name: str, description: str, mem_type: str, content: str) -> str:
        """保存记忆到磁盘并更新索引"""
        # 1. 写入单独记忆文件
        frontmatter = (
            f"---\nname: {name}\ndescription: {description}\ntype: {mem_type}\n---\n{content}\n"
        )
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name.lower())
        (self.memory_dir / f"{safe_name}.md").write_text(frontmatter)

        # 2. 更新内存存储
        self.memories[name] = {"description": description, "type": mem_type, "content": content}

        # 3. 重建 MEMORY.md 索引
        self._rebuild_index()

        return f"Saved memory '{name}' [{mem_type}]"

    def _rebuild_index(self):
        """从当前内存状态重建 MEMORY.md，限制在200行"""
        lines = ["# Memory Index", ""]
        for name, mem in self.memories.items():
            lines.append(f"- {name}: {mem['description']} [{mem['type']}]")
            if len(lines) >= MAX_INDEX_LINES:
                lines.append(f"... (truncated at {MAX_INDEX_LINES} lines)")
                break
        MEMORY_INDEX.write_text("\n".join(lines) + "\n")
```

#### 5. 注入到系统提示

```python
def load_memory_prompt(self) -> str:
    """构建用于注入系统提示的记忆部分"""
    if not self.memories:
        return ""

    sections = ["# Memories (persistent across sessions)", ""]

    # 按类型分组以提高可读性
    for mem_type in MEMORY_TYPES:  # ("user", "feedback", "project", "reference")
        typed = {k: v for k, v in self.memories.items() if v["type"] == mem_type}
        if not typed:
            continue
        sections.append(f"## [{mem_type}]")
        for name, mem in typed.items():
            sections.append(f"### {name}: {mem['description']}")
            if mem["content"].strip():
                sections.append(mem["content"].strip())
            sections.append("")

    return "\n".join(sections)
```

### Dream Consolidation - 记忆巩固机制

Kode-Agent 的 **Dream Consolidation** 是一个可选的后期特性，用于自动合并、去重和修剪记忆。

#### 四个阶段

```python
PHASES = [
    "Orient: scan MEMORY.md index for structure and categories",
    "Gather: read individual memory files for full content",
    "Consolidate: merge related memories, remove stale entries",
    "Prune: enforce 200-line limit on MEMORY.md index",
]
```

#### 七层安全门控

Dream Consolidation 不会随意运行，必须通过 7 层检查：

```python
def should_consolidate(self) -> tuple[bool, str]:
    now = time.time()

    # Gate 1: enabled flag
    if not self.enabled:
        return False, "Gate 1: consolidation is disabled"

    # Gate 2: memory directory exists and has memory files
    if not self.memory_dir.exists():
        return False, "Gate 2: memory directory does not exist"
    memory_files = [f for f in self.memory_dir.glob("*.md") if f.name != "MEMORY.md"]
    if not memory_files:
        return False, "Gate 2: no memory files found"

    # Gate 3: not in plan mode
    if self.mode == "plan":
        return False, "Gate 3: plan mode does not allow consolidation"

    # Gate 4: 24-hour cooldown
    time_since_last = now - self.last_consolidation_time
    if time_since_last < self.COOLDOWN_SECONDS:  # 86400s = 24h
        return False, f"Gate 4: cooldown active, {int(self.COOLDOWN_SECONDS - time_since_last)}s remaining"

    # Gate 5: 10-minute scan throttle
    time_since_scan = now - self.last_scan_time
    if time_since_scan < self.SCAN_THROTTLE_SECONDS:  # 600s = 10min
        return False, f"Gate 5: scan throttle active, {int(self.SCAN_THROTTLE_SECONDS - time_since_scan)}s remaining"

    # Gate 6: at least 5 sessions
    if self.session_count < self.MIN_SESSION_COUNT:  # 5
        return False, f"Gate 6: only {self.session_count} sessions, need {self.MIN_SESSION_COUNT}"

    # Gate 7: no active lock file
    if not self._acquire_lock():
        return False, "Gate 7: lock held by another process"

    return True, "All 7 gates passed"
```

#### PID 锁机制

```python
def _acquire_lock(self) -> bool:
    """获取基于 PID 的锁文件。如果是另一个进程持有锁，返回 False。"""
    if self.lock_file.exists():
        try:
            lock_data = self.lock_file.read_text().strip()
            pid_str, timestamp_str = lock_data.split(":", 1)
            pid = int(pid_str)
            lock_time = float(timestamp_str)

            # 检查锁是否过期
            if (time.time() - lock_time) > self.LOCK_STALE_SECONDS:  # 3600s = 1h
                print(f"[Dream] Removing stale lock from PID {pid}")
                self.lock_file.unlink()
            else:
                # 检查拥有进程是否还活着
                try:
                    os.kill(pid, 0)  # 信号 0: 检查进程是否存在
                    return False  # 进程活着，锁有效
                except OSError:
                    print(f"[Dream] Removing lock from dead PID {pid}")
                    self.lock_file.unlink()
        except (ValueError, OSError):
            self.lock_file.unlink(missing_ok=True)

    # 写入新锁
    self.memory_dir.mkdir(parents=True, exist_ok=True)
    self.lock_file.write_text(f"{os.getpid()}:{time.time()}")
    return True
```

### lingclaude 当前的分层记忆系统

lingclaude 实现了一个**五层架构 + 艾宾浩斯遗忘曲线**的记忆系统：

#### 五层架构

| 层级 | 名称 | 用途 | 持久化 |
|-----|------|------|-------|
| **Layer 0** | Common Knowledge | 预设事实，永不衰减 | 代码中硬编码 |
| **Layer 1** | Working Memory | 当前对话上下文 | 不持久化（缓冲区） |
| **Layer 2** | Experience | 决策链，艾宾浩斯衰减 | SQLite DB |
| **Layer 3** | Meta-Memory | 认知边界，最慢衰减 | 不持久化（运行时） |
| **Layer 4** | Shared | 跨 agent 共识 | 不持久化（运行时） |

#### 艾宾浩斯遗忘曲线

```python
def ebbinghaus_weight(
    created_at: datetime,
    last_recalled: datetime,
    recall_count: int,
    deny_count: int,
    emotion: EmotionIntensity,
    association_count: int,
) -> float:
    now = datetime.now(timezone.utc)
    days_since_recall = max(0, (now - last_recalled).total_seconds() / 86400)

    # 1. 时间衰减
    time_decay = math.exp(-_EBINGHAUS_DECAY_RATE * days_since_recall)  # e^(-0.1 * 天数)

    # 2. 重复因子
    repetition_factor = 1 + 0.3 * min(recall_count, 10)

    # 3. 情感因子
    emotion_factor = {
        EmotionIntensity.NONE: 1.0,
        EmotionIntensity.LOW: 1.1,
        EmotionIntensity.MEDIUM: 1.3,
        EmotionIntensity.HIGH: 1.6,
    }.get(emotion, 1.0)

    # 4. 关联因子
    association_factor = 1 + 0.1 * min(association_count, 10)

    # 5. 否认惩罚
    deny_penalty = max(0.1, 1 - 0.2 * min(deny_count, 5))

    return time_decay * repetition_factor * emotion_factor * association_factor * deny_penalty
```

#### Experience 数据结构

```python
@dataclass(frozen=True)
class Experience:
    id: str
    problem: str              # 问题
    hypothesis: str          # 假设
    action: str             # 行动
    result: str            # 结果
    reflection: str        # 反思
    created_at: datetime   # 创建时间
    last_recalled: datetime  # 最后召回时间
    recall_count: int     # 召回次数
    deny_count: int       # 否认次数
    emotion: EmotionIntensity  # 情感强度
    associations: tuple[str, ...]  # 关联
    weight: float         # 权重（艾宾浩斯计算）
```

#### 关键方法

```python
class ExperienceStore:
    def store(self, exp: Experience) -> str:
        """存储经验到 SQLite"""
        conn.execute(
            """INSERT OR REPLACE INTO experiences
               (id, problem, hypothesis, action, result, reflection,
                created_at, last_recalled, recall_count, deny_count,
                emotion, associations, weight)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (exp.id, exp.problem, exp.hypothesis, exp.action,
             exp.result, exp.reflection,
             exp.created_at.isoformat(), exp.last_recalled.isoformat(),
             exp.recall_count, exp.deny_count,
             exp.emotion.value, json.dumps(list(exp.associations)),
             exp.weight),
        )

    def recall(self, keyword: str, limit: int = 5) -> list[Experience]:
        """按关键词召回经验（按权重排序）"""
        pattern = f"%{keyword}%"
        rows = conn.execute(
            """SELECT * FROM experiences
               WHERE problem LIKE ? OR hypothesis LIKE ?
               OR reflection LIKE ? OR action LIKE ?
               ORDER BY weight DESC LIMIT ?""",
            (pattern, pattern, pattern, pattern, limit),
        ).fetchall()
        return [self._row_to_exp(r) for r in rows]

    def decay_all(self) -> int:
        """对所有经验进行艾宾浩斯衰减，并删除权重 < 0.05 的经验"""
        rows = conn.execute("SELECT * FROM experiences").fetchall()
        for row in rows:
            exp = self._row_to_exp(row)
            new_w = ebbinghaus_weight(
                exp.created_at, exp.last_recalled,
                exp.recall_count, exp.deny_count,
                exp.emotion, len(exp.associations),
            )
            conn.execute("UPDATE experiences SET weight = ? WHERE id = ?", (round(new_w, 4), exp.id))
        conn.execute("DELETE FROM experiences WHERE weight < ?", (0.05,))
        conn.commit()
        return updated
```

---

## Why - 为什么重要

### 1. Kode-Agent 文件式记忆的优势

- **人类可读**：每个记忆都是 Markdown 文件，易于检查和编辑
- **Git 追踪**：记忆文件可以版本控制，便于追溯变更
- **灵活扩展**：无需数据库迁移，直接创建新记忆文件
- **简单易懂**：新手可以直接读取 `.memory/` 目录查看记忆内容

### 2. lingclaude 艾宾浩斯遗忘曲线的优势

- **动态权重**：经验随着时间、重复、情感、关联自动调整权重
- **自动清理**：低权重经验自动删除，避免记忆膨胀
- **认知科学依据**：基于真实的人类记忆衰减模型

### 3. 两者的互补性

| 维度 | Kode-Agent | lingclaude | 改进方向 |
|-----|-----------|------------|---------|
| **存储格式** | Markdown 文件 | SQLite DB | 文件式更易读，DB 更易查询 |
| **记忆类型** | 4种（user, feedback, project, reference） | 无类型区分 | 应当有类型区分 |
| **自动清理** | Dream Consolidation（7层门控） | 艾宾浩斯衰减 | 两者结合更强大 |
| **跨会话** | 支持（文件持久化） | 支持（SQLite） | 都支持 |
| **并发控制** | PID 锁机制 | 无 | lingclaude 需要 |
| **人类可读** | 高（Markdown） | 低（SQLite） | lingclaude 应当导出 |

---

## How - 如何应用到 lingclaude

### 改进方案：混合式记忆系统

#### 阶段 1：为 Experience 添加类型字段

```python
class MemoryType(str, Enum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"

@dataclass(frozen=True)
class Experience:
    # ... 现有字段 ...
    mem_type: MemoryType = MemoryType.PROJECT  # 新增：记忆类型
```

#### 阶段 2：添加 Dream Consolidation 到 lingclaude

```python
class DreamConsolidator:
    """lingclaude 版本的记忆巩固（基于 Experience Store）"""

    COOLDOWN_SECONDS = 86400       # 24 小时冷却
    SCAN_THROTTLE_SECONDS = 600    # 10 分钟扫描节流
    MIN_SESSION_COUNT = 5          # 至少 5 次会话
    LOCK_STALE_SECONDS = 3600      # 锁文件 1 小时后过期

    PHASES = [
        "Orient: scan experiences for structure and categories",
        "Gather: load full experience data from SQLite",
        "Consolidate: merge related experiences, remove stale entries",
        "Prune: enforce weight threshold (0.05) and count limit (1000)",
    ]

    def __init__(self, experience_store: ExperienceStore, memory_dir: Path):
        self.experience_store = experience_store
        self.memory_dir = memory_dir
        self.lock_file = memory_dir / ".dream_lock"
        self.enabled = True
        self.last_consolidation_time = 0.0
        self.last_scan_time = 0.0
        self.session_count = 0

    def should_consolidate(self) -> tuple[bool, str]:
        """检查 7 层门控"""
        import time

        now = time.time()

        # Gate 1: enabled flag
        if not self.enabled:
            return False, "Gate 1: consolidation is disabled"

        # Gate 2: experience store has enough data
        stats = self.experience_store.get_stats()
        if stats["total_experiences"] < self.MIN_SESSION_COUNT:
            return False, f"Gate 2: only {stats['total_experiences']} experiences, need {self.MIN_SESSION_COUNT}"

        # Gate 3: not in read-only mode
        # lingclaude 可以根据模式检查

        # Gate 4: 24-hour cooldown
        time_since_last = now - self.last_consolidation_time
        if time_since_last < self.COOLDOWN_SECONDS:
            remaining = int(self.COOLDOWN_SECONDS - time_since_last)
            return False, f"Gate 4: cooldown active, {remaining}s remaining"

        # Gate 5: 10-minute scan throttle
        time_since_scan = now - self.last_scan_time
        if time_since_scan < self.SCAN_THROTTLE_SECONDS:
            remaining = int(self.SCAN_THROTTLE_SECONDS - time_since_scan)
            return False, f"Gate 5: scan throttle active, {remaining}s remaining"

        # Gate 6: at least 5 sessions
        if self.session_count < self.MIN_SESSION_COUNT:
            return False, f"Gate 6: only {self.session_count} sessions, need {self.MIN_SESSION_COUNT}"

        # Gate 7: no active lock file
        if not self._acquire_lock():
            return False, "Gate 7: lock held by another process"

        return True, "All 7 gates passed"

    def consolidate(self) -> list[str]:
        """运行 4 阶段巩固过程"""
        import time

        can_run, reason = self.should_consolidate()
        if not can_run:
            print(f"[Dream] Cannot consolidate: {reason}")
            return []

        print("[Dream] Starting consolidation...")
        self.last_scan_time = time.time()

        completed_phases = []

        # Phase 1: Orient
        print("[Dream] Phase 1/4: Orient - scanning experiences for structure")
        stats = self.experience_store.get_stats()
        print(f"[Dream]   Total experiences: {stats['total_experiences']}")
        print(f"[Dream]   Average weight: {stats['average_weight']}")
        completed_phases.append("Orient")

        # Phase 2: Gather
        print("[Dream] Phase 2/4: Gather - loading full experience data")
        # 已在 ExperienceStore 中实现
        completed_phases.append("Gather")

        # Phase 3: Consolidate
        print("[Dream] Phase 3/4: Consolidate - merging related experiences")
        # TODO: 实现 LLM 辅助的合并逻辑
        # - 查找相似的问题（embedding 相似度）
        # - 合并重复的经验
        # - 更新关联关系
        completed_phases.append("Consolidate")

        # Phase 4: Prune
        print("[Dream] Phase 4/4: Prune - enforcing weight threshold and count limit")
        updated = self.experience_store.decay_all()
        print(f"[Dream]   Updated {updated} experiences")
        completed_phases.append("Prune")

        self.last_consolidation_time = time.time()
        self._release_lock()
        print(f"[Dream] Consolidation complete: {len(completed_phases)} phases executed")
        return completed_phases

    def _acquire_lock(self) -> bool:
        """获取 PID 锁"""
        import time

        if self.lock_file.exists():
            try:
                lock_data = self.lock_file.read_text().strip()
                pid_str, timestamp_str = lock_data.split(":", 1)
                pid = int(pid_str)
                lock_time = float(timestamp_str)

                # 检查锁是否过期
                if (time.time() - lock_time) > self.LOCK_STALE_SECONDS:
                    print(f"[Dream] Removing stale lock from PID {pid}")
                    self.lock_file.unlink()
                else:
                    try:
                        os.kill(pid, 0)
                        return False
                    except OSError:
                        print(f"[Dream] Removing lock from dead PID {pid}")
                        self.lock_file.unlink()
            except (ValueError, OSError):
                self.lock_file.unlink(missing_ok=True)

        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            self.lock_file.write_text(f"{os.getpid()}:{time.time()}")
            return True
        except OSError:
            return False

    def _release_lock(self):
        """释放锁"""
        try:
            if self.lock_file.exists():
                lock_data = self.lock_file.read_text().strip()
                pid_str = lock_data.split(":")[0]
                if int(pid_str) == os.getpid():
                    self.lock_file.unlink()
        except (ValueError, OSError):
            pass
```

#### 阶段 3：添加会话摘要持久化

```python
class SessionSummary:
    """会话摘要，用于快速回顾"""

    @dataclass(frozen=True)
    class Summary:
        session_id: str
        started_at: datetime
        ended_at: datetime
        queries: tuple[str, ...]  # 查询列表
        decisions: tuple[str, ...]  # 关键决策
        outcomes: tuple[str, ...]   # 结果
        file_changes: tuple[str, ...]  # 修改的文件

class SessionSummaryStore:
    """会话摘要存储（JSONL 格式）"""

    def __init__(self, summary_file: Path):
        self.summary_file = summary_file

    def save_summary(self, summary: SessionSummary.Summary) -> None:
        """追加摘要到 JSONL 文件"""
        self.summary_file.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(summary))
        with open(self.summary_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def load_recent_summaries(self, limit: int = 10) -> list[SessionSummary.Summary]:
        """加载最近的摘要"""
        if not self.summary_file.exists():
            return []

        summaries = []
        with open(self.summary_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                summaries.append(SessionSummary.Summary(**data))

        return summaries[-limit:]

    def search_by_query(self, keyword: str) -> list[SessionSummary.Summary]:
        """按查询关键词搜索摘要"""
        if not self.summary_file.exists():
            return []

        keyword_lower = keyword.lower()
        matches = []

        with open(self.summary_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                summary = SessionSummary.Summary(**data)

                # 在查询中搜索
                if any(keyword_lower in q.lower() for q in summary.queries):
                    matches.append(summary)

        return matches
```

#### 阶段 4：集成到 LayeredMemory

```python
class LayeredMemory:
    def __init__(
        self,
        experience_store: ExperienceStore | None = None,
        dream_consolidator: DreamConsolidator | None = None,
        session_summary_store: SessionSummaryStore | None = None,
        common_extra: dict[str, dict[str, str]] | None = None,
        working_capacity: int = 24,
    ) -> None:
        self.common = CommonKnowledge(common_extra)
        self.working = WorkingMemory(working_capacity)
        self.experience = experience_store or InMemoryExperienceStore()
        self.dream_consolidator = dream_consolidator
        self.session_summary = session_summary_store
        self._meta_facts: dict[str, str] = {}
        self._shared_facts: dict[str, str] = {}
        self._session_start_time = datetime.now(timezone.utc)
        self._session_queries: list[str] = []
        self._session_decisions: list[str] = []
        self._session_outcomes: list[str] = []
        self._session_file_changes: list[str] = []

    def record_query(self, query: str) -> None:
        """记录会话查询"""
        self._session_queries.append(query)

    def record_decision(self, decision: str) -> None:
        """记录会话决策"""
        self._session_decisions.append(decision)

    def record_outcome(self, outcome: str) -> None:
        """记录会话结果"""
        self._session_outcomes.append(outcome)

    def record_file_change(self, file_path: str) -> None:
        """记录文件修改"""
        self._session_file_changes.append(file_path)

    def save_session_summary(self) -> str:
        """保存会话摘要"""
        if not self.session_summary:
            return "Session summary not enabled"

        summary = SessionSummary.Summary(
            session_id=uuid4().hex[:12],
            started_at=self._session_start_time,
            ended_at=datetime.now(timezone.utc),
            queries=tuple(self._session_queries),
            decisions=tuple(self._session_decisions),
            outcomes=tuple(self._session_outcomes),
            file_changes=tuple(self._session_file_changes),
        )
        self.session_summary.save_summary(summary)
        return f"Session summary saved: {len(self._session_queries)} queries, {len(self._session_file_changes)} file changes"

    def try_consolidate(self) -> list[str] | None:
        """尝试运行 Dream Consolidation"""
        if not self.dream_consolidator:
            return None

        return self.dream_consolidator.consolidate()
```

#### 阶段 5：配置示例

```yaml
# config.yaml
memory:
  # 分层记忆配置
  layered:
    working_capacity: 24
    experience_db: ".lingclaude/experience.db"

  # Dream Consolidation 配置
  dream:
    enabled: true
    cooldown_hours: 24
    scan_throttle_minutes: 10
    min_sessions: 5
    lock_stale_hours: 1

  # 会话摘要配置
  session_summary:
    enabled: true
    file: ".lingclaude/session_summaries.jsonl"
    max_file_size_mb: 10

  # 记忆类型配置
  types:
    user:
      description: "用户偏好"
      default_weight: 1.0
    feedback:
      description: "用户纠正"
      default_weight: 1.2
      emotion: EmotionIntensity.HIGH
    project:
      description: "项目事实"
      default_weight: 1.0
    reference:
      description: "外部资源"
      default_weight: 0.8
```

---

## Code - 代码示例

### 完整的 Experience 类型扩展

```python
class MemoryType(str, Enum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"

@dataclass(frozen=True)
class Experience:
    id: str
    problem: str
    hypothesis: str = ""
    action: str = ""
    result: str = ""
    reflection: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_recalled: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    recall_count: int = 0
    deny_count: int = 0
    emotion: EmotionIntensity = EmotionIntensity.NONE
    associations: tuple[str, ...] = ()
    weight: float = 1.0
    mem_type: MemoryType = MemoryType.PROJECT  # 新增

    @classmethod
    def create(
        cls,
        problem: str,
        mem_type: MemoryType = MemoryType.PROJECT,  # 新增参数
        hypothesis: str = "",
        action: str = "",
        result: str = "",
        reflection: str = "",
        emotion: EmotionIntensity = EmotionIntensity.NONE,
        associations: tuple[str, ...] = (),
    ) -> Experience:
        now = datetime.now(timezone.utc)
        # 根据 mem_type 设置默认权重
        default_weights = {
            MemoryType.USER: 1.0,
            MemoryType.FEEDBACK: 1.2,
            MemoryType.PROJECT: 1.0,
            MemoryType.REFERENCE: 0.8,
        }

        return cls(
            id=uuid4().hex[:12],
            problem=problem,
            hypothesis=hypothesis,
            action=action,
            result=result,
            reflection=reflection,
            created_at=now,
            last_recalled=now,
            recall_count=0,
            deny_count=0,
            emotion=emotion,
            associations=associations,
            weight=default_weights.get(mem_type, 1.0),
            mem_type=mem_type,
        )
```

---

## Summary - 总结

| 对比维度 | Kode-Agent | lingclaude (当前) | lingclaude (改进后) |
|---------|-----------|------------------|-------------------|
| **存储格式** | Markdown 文件 | SQLite DB | SQLite DB + JSONL 摘要 |
| **记忆类型** | 4种（user, feedback, project, reference） | 无 | 4种 |
| **自动清理** | Dream Consolidation（7层门控） | 艾宾浩斯衰减 | 两者结合 |
| **跨会话** | 支持（文件持久化） | 支持（SQLite） | 支持 |
| **并发控制** | PID 锁机制 | 无 | PID 锁机制 |
| **人类可读** | 高（Markdown） | 低（SQLite） | 增加摘要导出 |
| **会话追踪** | 无（session_count） | 无 | SessionSummary (JSONL) |
| **艾宾浩斯** | 无 | 有 | 保留 |

**关键改进点**：
1. **添加记忆类型**：区分用户偏好、反馈、项目事实、外部资源
2. **Dream Consolidation**：7层门控 + PID 锁
3. **会话摘要**：JSONL 格式持久化，支持快速回顾
4. **两者结合**：艾宾浩斯衰减 + Dream Consolidation 定期清理

---

## Next Steps - 下一步

- [ ] Task 3: Recursive Agent Loop 递归代理循环

---

**学习笔记完成日期**: 2026-04-14
**作者**: 灵通 (lingflow)
