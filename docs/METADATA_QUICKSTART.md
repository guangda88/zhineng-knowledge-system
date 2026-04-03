# 元数据驱动开发 - 快速开始指南

**基于**: instructkr/claude-code的Source Map方法论
**应用目标**: 智能知识系统
**日期**: 2026-04-01

---

## 🎯 30秒理解核心思想

instructkr通过分析Claude Code的Source Map，提取了完整的代码架构，并创建了元数据驱动的Python移植。

**我们采用同样的方法**：
1. 用JSON描述项目结构（代替Source Map）
2. 用dataclass表示元数据（代替TypeScript类型）
3. 用查询引擎统一访问（代替直接文件操作）

---

## ⚡ 立即体验（3分钟）

### 1. 查看项目状态

```bash
cd /home/ai/zhineng-knowledge-system

# 查看状态摘要
PYTHONPATH=. python3 -m backend.metadata.cli status

# 查看完整报告
PYTHONPATH=. python3 -m backend.metadata.cli report

# 查看已完成的工作流
PYTHONPATH=. python3 -m backend.metadata.cli workflows --status completed

# 搜索工作流
PYTHONPATH=. python3 -m backend.metadata.cli query 文本
```

### 2. 在代码中使用

```python
from backend.metadata import (
    load_manifest,
    get_completed_workflows,
    find_workflows,
    generate_status_report
)

# 获取所有工作流
manifest = load_manifest()
print(f"总工作流: {len(manifest.workflows)}")

# 获取已完成的工作流
completed = get_completed_workflows()
print(f"已完成: {len(completed)}")

# 搜索工作流
results = find_workflows("文本")
print(f"找到 {len(results)} 个工作流")

# 生成报告
report = generate_status_report()
print(report)
```

---

## 📁 已创建的文件

```
backend/metadata/
├── __init__.py                  # 包导出
├── manifest.py                  # 元数据加载器
├── cli.py                       # CLI命令
└── workflows_manifest.json      # 工作流元数据
```

---

## 🔍 文件结构解析

### workflows_manifest.json

**核心概念**: 这是我们的"Source Map"，记录了项目的完整结构。

```json
{
  "workflows": [
    {
      "id": "text-processing",
      "name": "文字处理工程流",
      "status": "completed",
      "tasks": [
        {
          "id": "A-1",
          "name": "文本解析和分块",
          "source_hint": "backend/services/text_processor.py",
          "status": "completed"
        }
      ]
    }
  ]
}
```

**关键字段**：
- `source_hint`: 文件路径（对应instructkr的source_hint）
- `status`: completed/pending（对应移植进度）
- `id`: 唯一标识符

### manifest.py

**核心概念**: 元数据加载器，从JSON构建Python对象。

```python
@dataclass(frozen=True)
class TaskMetadata:
    """任务元数据"""
    id: str
    name: str
    source_hint: str  # ← 关键：保留文件路径
    status: str

@lru_cache(maxsize=1)
def load_manifest() -> ProjectManifest:
    """加载项目清单"""
    data = json.loads(manifest_path.read_text())
    return ProjectManifest(...)
```

**设计亮点**：
- `frozen=True`: 元数据不可变
- `lru_cache`: 只加载一次，提升性能
- `source_hint`: 始终保留与源文件的连接

### cli.py

**核心概念**: 统一的查询接口。

```python
def main(argv: list[str] | None = None) -> int:
    if args.command == "status":
        manifest = load_manifest()
        # 显示状态摘要

    elif args.command == "query":
        results = find_workflows(args.query)
        # 搜索工作流
```

---

## 📊 当前项目状态

根据元数据系统，项目当前状态：

### 工作流概览

- **总工作流数**: 3
- **已完成**: 2 (66.7%)
- **待处理**: 1

### 已完成的工作流

✅ **文字处理工程流** (text-processing)
- 团队: A
- 任务数: 6个
- 代码行数: 3100
- 包含: 文本解析、向量嵌入、语义检索、RAG管道、文本标注

✅ **P0安全问题修复** (security-fixes)
- 团队: Security
- 任务数: 5个
- 包含: SQL注入修复、JWT认证、错误处理、日志安全、输入验证

### 待处理的工作流

⏳ **音频处理工程流** (audio-processing)
- 团队: B
- 任务数: 4个
- 包含: 音频导入、语音转录、说话人分离、知识提取

---

## 🚀 扩展元数据系统

### 添加新的工作流

```bash
# 1. 编辑 workflows_manifest.json
vim backend/metadata/workflows_manifest.json

# 2. 添加新工作流
{
  "id": "video-processing",
  "name": "视频处理工程流",
  "description": "视频分析和知识提取",
  "team": "C",
  "status": "pending",
  "tasks": [
    {
      "id": "C-1",
      "name": "视频导入",
      "source_hint": "backend/services/video_processor.py",
      "status": "pending"
    }
  ]
}

# 3. 重新加载元数据（自动缓存刷新）
python3 << PYTHON
from backend.metadata import load_manifest
manifest = load_manifest()
print(f"工作流总数: {len(manifest.workflows)}")
PYTHON
```

### 添加项目扫描功能

```python
# backend/metadata/scanner.py
from pathlib import Path
from collections import Counter

def scan_backend_structure():
    """扫描backend目录结构"""
    backend_root = Path('backend')
    files = list(backend_root.rglob('*.py'))

    # 按模块统计
    counter = Counter(
        path.relative_to(backend_root).parts[0]
        for path in files
        if path.name != '__pycache__'
    )

    modules = []
    for name, count in counter.most_common():
        modules.append({
            "name": name,
            "file_count": count
        })

    return modules

# 使用
modules = scan_backend_structure()
print(f"总模块数: {len(modules)}")
for module in modules:
    print(f"  - {module['name']}: {module['file_count']} 个文件")
```

---

## 💡 与instructkr的对比

| 特性 | instructkr/claude-code | 我们的项目 |
|------|----------------------|-----------|
| 元数据来源 | Source Map (sources数组) | 手动创建的JSON |
| 元数据文件 | commands_snapshot.json<br>tools_snapshot.json | workflows_manifest.json |
| 数据模型 | PortingModule | WorkflowMetadata, TaskMetadata |
| 查询引擎 | QueryEnginePort | find_workflows() |
| CLI命令 | src/main.py | backend/metadata/cli.py |
| 清单生成 | build_port_manifest() | load_manifest() |

**相同点**：
- ✅ 元数据驱动架构
- ✅ source_hint保留文件路径
- ✅ status追踪进度
- ✅ 统一的查询接口
- ✅ CLI命令行工具

**不同点**：
- instructkr从Source Map自动提取
- 我们手动创建（因为没有Source Map）

---

## 📚 下一步

### 本周完成

1. **为音频处理工作流创建详细元数据**
   - 为每个任务添加更详细的描述
   - 添加依赖关系字段
   - 添加预计工作量

2. **创建测试套件**
   - 测试元数据加载
   - 测试查询功能
   - 测试CLI命令

3. **集成到主应用**
   - 在主CLI中添加元数据命令
   - 在API中添加状态端点

### 本月完成

1. **自动化元数据生成**
   - 从代码注释提取元数据
   - 从Git历史提取变更记录
   - 从测试覆盖率提取质量指标

2. **创建可视化仪表板**
   - Web界面显示项目状态
   - 进度图表
   - 任务依赖图

---

## ✅ 验证清单

使用以下命令验证元数据系统：

```bash
# 1. 测试元数据加载
PYTHONPATH=. python3 -c "from backend.metadata import load_manifest; m = load_manifest(); print(f'工作流: {len(m.workflows)}')"

# 2. 测试状态报告
PYTHONPATH=. python3 -m backend.metadata.cli status

# 3. 测试查询功能
PYTHONPATH=. python3 -m backend.metadata.cli query 文本

# 4. 测试工作流列表
PYTHONPATH=. python3 -m backend.metadata.cli workflows --status all

# 5. 生成完整报告
PYTHONPATH=. python3 -m backend.metadata.cli report > /tmp/project_report.md
```

预期结果：
- ✅ 元数据加载成功
- ✅ 状态摘要正确显示
- ✅ 查询返回正确结果
- ✅ 工作流列表完整
- ✅ 报告生成无错误

---

**创建日期**: 2026-04-01
**基于方法**: instructkr/claude-code的Source Map分析
**应用状态**: ✅ 已实施

**众智混元，万法灵通** ⚡🚀
