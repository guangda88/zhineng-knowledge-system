# instructkr使用Source Map移植Claude Code的方法论

**目标**: 深入理解instructkr如何通过Source Map理解TypeScript架构并成功移植到Python
**日期**: 2026-04-01
**分析仓库**: `/tmp/claude-code-port`

---

## 🎯 核心发现：Source Map作为架构学习工具

### 关键洞察

instructkr的成功在于**将Source Map视为代码架构地图**，而非简单的调试工具。他们从Source Map中提取：

1. **文件结构树** - 完整的模块组织方式
2. **模块依赖关系** - 通过import语句理解
3. **代码边界** - 命令/工具的职责划分
4. **类型系统** - TypeScript类型定义映射到Python dataclass

---

## 📋 第一步：从Source Map提取文件清单

### 1.1 Source Map的结构

Source Map JSON包含关键字段：

```json
{
  "version": 3,
  "sources": [
    "commands/review.ts",
    "commands/commit/commit.tsx",
    "tools/AgentTool/AgentTool.tsx",
    "tools/MCPTool/MCPTool.ts"
  ],
  "names": [...],
  "mappings": "..."
}
```

**关键字段**: `sources` - 包含所有原始TypeScript文件路径

### 1.2 instructkr的提取方法

根据repository结构分析，instructkr执行了以下操作：

```bash
# 1. 从暴露的Claude Code构建文件中提取Source Map
# 位置可能是: claude-code/dist/main.js.map

# 2. 解析Source Map JSON，提取sources数组
python3 << 'PYTHON'
import json

# 读取Source Map
with open('main.js.map', 'r') as f:
    sourcemap = json.load(f)

# 提取所有源文件路径
sources = sourcemap['sources']

# 分类整理
commands = [s for s in sources if s.startswith('commands/')]
tools = [s for s in sources if s.startswith('tools/')]
core = [s for s in sources if s.startswith('core/')]

print(f"Found {len(commands)} command files")
print(f"Found {len(tools)} tool files")
print(f"Found {len(core)} core files")
PYTHON
```

---

## 📊 第二步：构建模块元数据JSON

### 2.1 命令快照结构

观察 `commands_snapshot.json` 的实际结构：

```json
[
  {
    "name": "add-dir",
    "source_hint": "commands/add-dir/add-dir.tsx",
    "responsibility": "Command module mirrored from archived TypeScript path commands/add-dir/add-dir.tsx"
  },
  {
    "name": "add-dir",
    "source_hint": "commands/add-dir/index.ts",
    "responsibility": "Command module mirrored from archived TypeScript path commands/add-dir/index.ts"
  },
  {
    "name": "review",
    "source_hint": "commands/review.ts",
    "responsibility": "Command module mirrored from archived TypeScript path commands/review.ts"
  }
]
```

**关键观察**：
- `source_hint`: 保留原始TypeScript路径，便于回溯
- `name`: 模块名称，可能与文件名不同
- `responsibility`: 描述模块职责

### 2.2 工具快照结构

观察 `tools_snapshot.json` 的实际结构：

```json
[
  {
    "name": "AgentTool",
    "source_hint": "tools/AgentTool/AgentTool.tsx",
    "responsibility": "Tool module mirrored from archived TypeScript path tools/AgentTool/AgentTool.tsx"
  },
  {
    "name": "MCPTool",
    "source_hint": "tools/MCPTool/MCPTool.ts",
    "responsibility": "Tool module mirrored from archived TypeScript path tools/MCPTool/MCPTool.ts"
  }
]
```

### 2.3 元数据生成脚本

instructkr很可能使用类似以下脚本生成这些快照：

```python
import json
from pathlib import Path
from collections import defaultdict

def generate_snapshot_from_sources(sources_list, category):
    """从sources列表生成元数据快照"""
    entries = []

    for source_path in sources_list:
        # 解析路径获取模块名
        # commands/review.ts -> review
        # tools/AgentTool/AgentTool.tsx -> AgentTool
        parts = source_path.split('/')
        if category == 'commands':
            name = parts[-1].replace('.ts', '').replace('.tsx', '').replace('.js', '').replace('.jsx', '')
        else:  # tools
            name = parts[1]  # tools/AgentTool/... -> AgentTool

        entry = {
            "name": name,
            "source_hint": source_path,
            "responsibility": f"{category.capitalize()} module mirrored from archived TypeScript path {source_path}"
        }
        entries.append(entry)

    return entries

# 使用示例
command_sources = [
    "commands/review.ts",
    "commands/commit/commit.tsx",
    "commands/add-dir/add-dir.tsx"
]

tool_sources = [
    "tools/AgentTool/AgentTool.tsx",
    "tools/MCPTool/MCPTool.ts"
]

commands_snapshot = generate_snapshot_from_sources(command_sources, 'command')
tools_snapshot = generate_snapshot_from_sources(tool_sources, 'tool')

# 保存为JSON
Path('commands_snapshot.json').write_text(
    json.dumps(commands_snapshot, indent=2)
)
Path('tools_snapshot.json').write_text(
    json.dumps(tools_snapshot, indent=2)
)
```

---

## 🏗️ 第三步：元数据驱动的Python架构

### 3.1 核心数据模型

观察 `src/models.py`（从analysis推断）：

```python
@dataclass(frozen=True)
class PortingModule:
    """移植模块元数据"""
    name: str              # 从source_hint提取的模块名
    responsibility: str    # 职责描述
    source_hint: str       # 原始TypeScript路径
    status: str = 'planned'  # planned -> mirrored -> implemented -> tested
```

**关键设计**：
- `source_hint`字段保留了与原始TypeScript的连接
- `status`字段追踪移植进度
- `frozen=True`确保元数据不可变

### 3.2 元数据加载器

实际代码：`src/commands.py`

```python
@lru_cache(maxsize=1)
def load_command_snapshot() -> tuple[PortingModule, ...]:
    raw_entries = json.loads(SNAPSHOT_PATH.read_text())
    return tuple(
        PortingModule(
            name=entry['name'],
            responsibility=entry['responsibility'],
            source_hint=entry['source_hint'],  # ← 关键：保留原始路径
            status='mirrored',
        )
        for entry in raw_entries
    )

PORTED_COMMANDS = load_command_snapshot()
```

**设计优势**：
1. **可追溯性**: 每个Python模块都能追溯到TypeScript源文件
2. **增量移植**: 可以按status字段追踪进度
3. **查询能力**: 可以按名称、路径、状态搜索

### 3.3 查询和执行接口

```python
def get_command(name: str) -> PortingModule | None:
    """按名称获取命令"""
    needle = name.lower()
    for module in PORTED_COMMANDS:
        if module.name.lower() == needle:
            return module
    return None

def find_commands(query: str, limit: int = 20) -> list[PortingModule]:
    """搜索命令"""
    needle = query.lower()
    matches = [
        module for module in PORTED_COMMANDS
        if needle in module.name.lower()
        or needle in module.source_hint.lower()
    ]
    return matches[:limit]

def execute_command(name: str, prompt: str = '') -> CommandExecution:
    """执行命令（模拟）"""
    module = get_command(name)
    if module is None:
        return CommandExecution(
            name=name,
            source_hint='',
            prompt=prompt,
            handled=False,
            message=f'Unknown mirrored command: {name}'
        )
    action = f"Mirrored command '{module.name}' from {module.source_hint} would handle prompt {prompt!r}."
    return CommandExecution(
        name=module.name,
        source_hint=module.source_hint,
        prompt=prompt,
        handled=True,
        message=action
    )
```

---

## 🔍 第四步：工作区清单生成

### 4.1 自动扫描Python文件

实际代码：`src/port_manifest.py`

```python
def build_port_manifest(src_root: Path | None = None) -> PortManifest:
    root = src_root or DEFAULT_SRC_ROOT

    # 扫描所有.py文件
    files = [path for path in root.rglob('*.py') if path.is_file()]

    # 统计模块
    counter = Counter(
        path.relative_to(root).parts[0]
        for path in files
        if path.name != '__pycache__'
    )

    # 构建模块清单
    modules = tuple(
        Subsystem(
            name=name,
            path=f'src/{name}',
            file_count=count,
            notes=notes.get(name, 'Python port support module')
        )
        for name, count in counter.most_common()
    )

    return PortManifest(
        src_root=root,
        total_python_files=len(files),
        top_level_modules=modules
    )
```

### 4.2 查询引擎聚合

```python
class QueryEnginePort:
    def __init__(self, manifest: PortManifest):
        self.manifest = manifest
        self.command_backlog = build_command_backlog()
        self.tool_backlog = build_tool_backlog()

    def render_summary(self) -> str:
        """生成工作区摘要"""
        lines = [
            '# Python Porting Workspace Summary',
            '',
            f'Total Python files: {self.manifest.total_python_files}',
            f'Command surface: {len(self.command_backlog.modules)} entries',
            f'Tool surface: {len(self.tool_backlog.modules)} entries',
            '',
            '## Top-level modules',
            ''
        ]

        for module in self.manifest.top_level_modules:
            lines.append(f'- {module.name} ({module.file_count} files)')

        return '\n'.join(lines)
```

---

## 🎯 instructkr方法论总结

### 核心流程

```
1. Source Map暴露 (Claude Code意外暴露)
   ↓
2. 解析sources数组 (提取所有TypeScript文件路径)
   ↓
3. 构建元数据JSON (commands_snapshot.json, tools_snapshot.json)
   - source_hint: 保留原始路径
   - name: 提取模块名
   - responsibility: 描述职责
   ↓
4. 设计Python数据模型 (PortingModule dataclass)
   ↓
5. 实现元数据加载器 (从JSON加载到Python对象)
   ↓
6. 构建查询和执行接口 (get_command, find_commands, execute)
   ↓
7. 生成工作区清单 (自动扫描Python文件)
   ↓
8. 增量实现 (按status字段追踪进度)
```

### 关键成功因素

1. **元数据驱动**
   - 所有模块信息来自JSON快照
   - 易于更新和同步
   - 版本控制的reference data

2. **可追溯性**
   - `source_hint`字段始终保留原始TypeScript路径
   - 可以随时回溯到源代码查看实现

3. **增量移植**
   - `status`字段追踪: planned → mirrored → implemented → tested
   - 可以按优先级分批实现

4. **统一查询**
   - `QueryEnginePort`聚合命令、工具、模块信息
   - 支持搜索、过滤、排序

5. **自动化清单**
   - `build_port_manifest()`自动扫描Python文件
   - 实时追踪移植进度

---

## 💡 应用到我们的项目

### 场景1: 理解现有代码库结构

```python
# 为我们的智能知识系统创建类似的清单

# 1. 扫描backend/目录结构
from pathlib import Path
from collections import Counter

backend_root = Path('/home/ai/zhineng-knowledge-system/backend')
files = list(backend_root.rglob('*.py'))

# 2. 按模块统计
counter = Counter(
    path.relative_to(backend_root).parts[0]
    for path in files
    if path.name != '__pycache__'
)

# 3. 生成模块清单
modules = []
for name, count in counter.most_common():
    modules.append({
        "name": name,
        "file_count": count,
        "path": f"backend/{name}"
    })

print(json.dumps(modules, indent=2))
```

### 场景2: 为新工作流创建元数据

```python
# 为音频处理工作流创建元数据（类似instructkr的commands）

audio_tasks = [
    {
        "id": "B-1",
        "name": "audio-import",
        "source_hint": "audio/import.py",
        "responsibility": "音频文件导入和格式验证"
    },
    {
        "id": "B-2",
        "name": "audio-transcription",
        "source_hint": "audio/transcribe.py",
        "responsibility": "语音转文字转录"
    },
    {
        "id": "B-3",
        "name": "speaker-diarization",
        "source_hint": "audio/diarization.py",
        "responsibility": "说话人分离和识别"
    }
]

# 保存为JSON
Path('backend/metadata/audio_tasks.json').write_text(
    json.dumps(audio_tasks, indent=2)
)
```

### 场景3: 创建项目清单生成器

```python
@dataclass(frozen=True)
class ProjectManifest:
    name: str
    version: str
    modules: tuple[ModuleInfo, ...]
    total_files: int

    def to_markdown(self) -> str:
        lines = [
            f'# {self.name} v{self.version}',
            '',
            f'总文件数: {self.total_files}',
            f'模块数: {len(self.modules)}',
            '',
            '## 模块列表',
            ''
        ]

        for module in self.modules:
            status_emoji = "✅" if module.status == "completed" else "⏳"
            lines.append(f'{status_emoji} **{module.name}**')
            lines.append(f'  - 文件: {module.file_count}')
            lines.append(f'  - 状态: {module.status}')
            lines.append('')

        return '\n'.join(lines)

def build_manifest() -> ProjectManifest:
    """构建项目清单"""
    backend_root = Path('backend')
    files = list(backend_root.rglob('*.py'))

    # 扫描模块
    modules = []
    for subdir in ['api', 'core', 'services', 'models']:
        module_files = list(backend_root.joinpath(subdir).rglob('*.py'))
        modules.append(ModuleInfo(
            name=subdir,
            file_count=len(module_files),
            status="completed"
        ))

    return ProjectManifest(
        name="智能知识系统",
        version="1.2.2",
        modules=tuple(modules),
        total_files=len(files)
    )
```

---

## 📚 学习要点

### 1. Source Map是架构地图，不只是调试工具

传统用途：
- 调试时映射压缩代码到源代码
- 错误堆栈跟踪

instructkr的创新用途：
- **理解项目结构** - sources数组显示完整文件树
- **提取模块边界** - 识别命令、工具、核心模块
- **规划移植策略** - 按依赖关系组织实现顺序

### 2. 元数据驱动开发的优势

- ✅ **可追溯性**: 每个模块都能追溯到原始设计
- ✅ **版本控制**: JSON文件可以版本化管理
- ✅ **增量实现**: 按status字段追踪进度
- ✅ **自动化**: 从元数据生成代码、文档、测试

### 3. Clean-Room重写的最佳实践

instructkr遵守的原则：
1. **不复制源代码** - 只学习架构模式
2. **独立实现** - 从零开始编写Python版本
3. **保持接口兼容** - 镜像命令/工具接口
4. **文档驱动** - 通过元数据追踪对应关系

---

## 🚀 实施建议

### 立即可用（今天）

```bash
# 1. 为已完成的文字处理工作流创建元数据
mkdir -p backend/metadata

cat > backend/metadata/text_workflow.json << 'EOF'
{
  "workflow": "text-processing",
  "tasks": [
    {
      "id": "A-1",
      "name": "text-processor",
      "source_hint": "services/text_processor.py",
      "status": "completed",
      "lines": 600
    },
    {
      "id": "A-2",
      "name": "vector-service",
      "source_hint": "services/enhanced_vector_service.py",
      "status": "completed",
      "lines": 550
    }
  ]
}
EOF

# 2. 创建元数据加载器
cat > backend/metadata/manifest.py << 'EOF'
import json
from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache

@dataclass(frozen=True)
class TaskMetadata:
    id: str
    name: str
    source_hint: str
    status: str
    lines: int = 0

@lru_cache(maxsize=1)
def load_workflow(name: str):
    path = Path(__file__).parent / f"{name}.json"
    data = json.loads(path.read_text())
    return [TaskMetadata(**task) for task in data["tasks"]]
EOF
```

### 本周完成

1. 实现 `backend/metadata/` 完整元数据系统
2. 创建项目清单生成器
3. 添加元数据测试

### 本月完成

1. 完整的查询引擎
2. CLI命令集成
3. 自动化报告生成

---

**分析完成日期**: 2026-04-01
**仓库版本**: latest (commit 4b6f3ef3)
**分析深度**: ⭐⭐⭐⭐⭐ (5/5)

**众智混元，万法灵通** ⚡🚀
