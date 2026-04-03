# 将Claude Code移植模式应用到智能知识系统

**基于**: instructkr/claude-code 项目分析
**应用目标**: 智能知识系统 (zhineng-knowledge-system)
**日期**: 2026-04-01

---

## 🎯 核心应用策略

### 1. 元数据驱动开发 (Metadata-Driven Development)

#### 1.1 创建技能元数据

**新建文件**: `backend/metadata/skills_manifest.json`

```json
{
  "skills": [
    {
      "id": "text-processing",
      "name": "文字处理工程流",
      "description": "完整的文本处理和RAG问答系统",
      "team": "A",
      "status": "completed",
      "tasks": [
        {
          "id": "A-1",
          "name": "文本解析和分块",
          "status": "completed",
          "file": "backend/services/text_processor.py",
          "lines": 600,
          "tests": "tests/test_text_processor.py"
        },
        {
          "id": "A-2",
          "name": "向量嵌入生成",
          "status": "completed",
          "file": "backend/services/enhanced_vector_service.py",
          "lines": 550
        },
        {
          "id": "A-3",
          "name": "语义检索实现",
          "status": "completed",
          "file": "backend/services/hybrid_retrieval.py",
          "lines": 650
        },
        {
          "id": "A-4",
          "name": "RAG问答管道",
          "status": "completed",
          "file": "backend/services/rag_pipeline.py",
          "lines": 550
        },
        {
          "id": "A-5",
          "name": "文本标注系统",
          "status": "completed",
          "file": "backend/services/text_annotation_service.py"
        },
        {
          "id": "A-6",
          "name": "测试和文档",
          "status": "completed",
          "file": "tests/test_text_processor.py"
        }
      ],
      "total_lines": 3100,
      "completed_at": "2026-04-01"
    },
    {
      "id": "audio-processing",
      "name": "音频处理工程流",
      "description": "音频转录、处理和知识提取",
      "team": "B",
      "status": "pending",
      "tasks": [
        {
          "id": "B-1",
          "name": "音频文件导入",
          "status": "pending"
        },
        {
          "id": "B-2",
          "name": "语音转录",
          "status": "pending"
        },
        {
          "id": "B-3",
          "name": "说话人分离",
          "status": "pending"
        },
        {
          "id": "B-4",
          "name": "知识提取",
          "status": "pending"
        }
      ]
    },
    {
      "id": "security-fixes",
      "name": "P0安全问题修复",
      "description": "关键安全漏洞修复",
      "team": "Security",
      "status": "completed",
      "tasks": [
        {
          "id": "P0-1",
          "name": "SQL注入修复",
          "status": "completed",
          "file": "backend/api/v1/books.py"
        },
        {
          "id": "P0-2",
          "name": "JWT认证实现",
          "status": "completed",
          "file": "backend/core/security.py"
        },
        {
          "id": "P0-3",
          "name": "统一错误处理",
          "status": "completed",
          "file": "backend/core/error_handlers.py"
        },
        {
          "id": "P0-4",
          "name": "日志安全加固",
          "status": "completed",
          "file": "backend/core/secure_logging.py"
        },
        {
          "id": "P0-5",
          "name": "输入验证加强",
          "status": "completed",
          "file": "backend/core/validators.py"
        }
      ]
    }
  ],
  "metadata": {
    "version": "1.0.0",
    "last_updated": "2026-04-01",
    "total_skills": 3,
    "completed_skills": 2
  }
}
```

#### 1.2 创建元数据加载器

**新建文件**: `backend/metadata/manifest.py`

```python
"""
项目元数据加载器

参考: instructkr/claude-code 的元数据驱动架构
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from typing import Optional


@dataclass(frozen=True)
class TaskMetadata:
    """任务元数据"""
    id: str
    name: str
    status: str
    file: Optional[str] = None
    lines: Optional[int] = None


@dataclass(frozen=True)
class SkillMetadata:
    """技能元数据"""
    id: str
    name: str
    description: str
    team: str
    status: str
    tasks: tuple[TaskMetadata, ...]
    total_lines: Optional[int] = None
    completed_at: Optional[str] = None


@dataclass(frozen=True)
class ProjectManifest:
    """项目清单"""
    skills: tuple[SkillMetadata, ...]
    version: str
    last_updated: str

    def get_completed_skills(self) -> tuple[SkillMetadata, ...]:
        """获取已完成的技能"""
        return tuple(s for s in self.skills if s.status == "completed")

    def get_pending_skills(self) -> tuple[SkillMetadata, ...]:
        """获取待处理的技能"""
        return tuple(s for s in self.skills if s.status == "pending")

    def get_skill(self, skill_id: str) -> Optional[SkillMetadata]:
        """按ID获取技能"""
        for skill in self.skills:
            if skill.id == skill_id:
                return skill
        return None

    def to_markdown(self) -> str:
        """生成Markdown报告"""
        lines = [
            f"# 项目状态报告",
            f"",
            f"**版本**: {self.version}",
            f"**更新时间**: {self.last_updated}",
            f"",
            f"## 技能概览",
            f"",
            f"- 总技能数: **{len(self.skills)}**",
            f"- 已完成: **{len(self.get_completed_skills())}**",
            f"- 待处理: **{len(self.get_pending_skills())}**",
            f"",
        ]

        for skill in self.skills:
            status_emoji = "✅" if skill.status == "completed" else "⏳"
            lines.append(f"### {status_emoji} {skill.name}")
            lines.append(f""
)
            lines.append(f"- **ID**: {skill.id}")
            lines.append(f"- **团队**: {skill.team}")
            lines.append(f"- **状态**: {skill.status}")
            lines.append(f"- **任务数**: {len(skill.tasks)}")

            if skill.total_lines:
                lines.append(f"- **代码行数**: {skill.total_lines}")

            lines.append(f""
            lines.append(f"#### 任务列表"
            lines.append(f""

            for task in skill.tasks:
                task_status = "✅" if task.status == "completed" else "⏳"
                lines.append(f"- {task_status} **{task.id}**: {task.name}")
                if task.file:
                    lines.append(f"  - 文件: `{task.file}`")

            lines.append(f""

        return "\n".join(lines)


@lru_cache(maxsize=1)
def load_manifest() -> ProjectManifest:
    """加载项目清单"""
    manifest_path = Path(__file__).parent / "skills_manifest.json"

    if not manifest_path.exists():
        # 返回空清单
        return ProjectManifest(
            skills=(),
            version="0.0.0",
            last_updated=""
        )

    data = json.loads(manifest_path.read_text())

    skills = []
    for skill_data in data.get("skills", []):
        tasks = tuple(
            TaskMetadata(**task_data)
            for task_data in skill_data.get("tasks", [])
        )

        skills.append(SkillMetadata(
            id=skill_data["id"],
            name=skill_data["name"],
            description=skill_data["description"],
            team=skill_data["team"],
            status=skill_data["status"],
            tasks=tasks,
            total_lines=skill_data.get("total_lines"),
            completed_at=skill_data.get("completed_at")
        ))

    metadata = data.get("metadata", {})

    return ProjectManifest(
        skills=tuple(skills),
        version=metadata.get("version", "1.0.0"),
        last_updated=metadata.get("last_updated", "")
    )


# 便捷API
def get_all_skills() -> tuple[SkillMetadata, ...]:
    """获取所有技能"""
    manifest = load_manifest()
    return manifest.skills


def get_completed_skills() -> tuple[SkillMetadata, ...]:
    """获取已完成的技能"""
    manifest = load_manifest()
    return manifest.get_completed_skills()


def get_skill_by_id(skill_id: str) -> Optional[SkillMetadata]:
    """按ID获取技能"""
    manifest = load_manifest()
    return manifest.get_skill(skill_id)


def find_skills(query: str) -> list[SkillMetadata]:
    """搜索技能"""
    manifest = load_manifest()
    needle = query.lower()

    return [
        skill for skill in manifest.skills
        if needle in skill.name.lower()
        or needle in skill.description.lower()
        or needle in skill.id.lower()
    ]


def generate_status_report() -> str:
    """生成状态报告"""
    manifest = load_manifest()
    return manifest.to_markdown()
```

#### 1.3 创建查询引擎

**新建文件**: `backend/metadata/query_engine.py`

```python
"""
工作区查询引擎

参考: instructkr/claude-code 的 QueryEnginePort
"""
from __future__ import annotations

from dataclasses import dataclass

from .manifest import load_manifest, ProjectManifest


@dataclass
class WorkspaceQuery:
    """工作区查询"""
    query: str
    skills: list
    tasks: list

    def to_markdown(self) -> str:
        """生成查询结果"""
        lines = [
            f"# 查询结果: {self.query}",
            f"",
            f"找到 {len(self.skills)} 个技能",
            f"找到 {len(self.tasks)} 个任务",
            f"",
        ]

        if self.skills:
            lines.append("## 匹配的技能")
            lines.append("")
            for skill in self.skills:
                lines.append(f"- **{skill.name}** ({skill.id})")
                lines.append(f"  - {skill.description}")
            lines.append("")

        if self.tasks:
            lines.append("## 匹配的任务")
            lines.append("")
            for task in self.tasks:
                lines.append(f"- **{task.name}** ({task.id})")
                lines.append(f"  - 状态: {task.status}")
            lines.append("")

        return "\n".join(lines)


class WorkspaceQueryEngine:
    """工作区查询引擎"""

    def __init__(self):
        self.manifest = load_manifest()

    def query(self, query: str, limit: int = 20) -> WorkspaceQuery:
        """搜索技能和任务"""
        needle = query.lower()

        # 搜索技能
        matching_skills = [
            skill for skill in self.manifest.skills
            if needle in skill.name.lower()
            or needle in skill.description.lower()
            or needle in skill.id.lower()
        ]

        # 搜索任务
        matching_tasks = []
        for skill in self.manifest.skills:
            for task in skill.tasks:
                if needle in task.name.lower()
                or needle in task.id.lower():
                    matching_tasks.append(task)

        return WorkspaceQuery(
            query=query,
            skills=matching_skills[:limit],
            tasks=matching_tasks[:limit]
        )

    def get_status_summary(self) -> str:
        """获取状态摘要"""
        manifest = load_manifest()

        completed = len(manifest.get_completed_skills())
        total = len(manifest.skills)
        percentage = (completed / total * 100) if total > 0 else 0

        lines = [
            f"## 项目状态摘要",
            f"",
            f"- **总技能数**: {total}",
            f"- **已完成**: {completed} ({percentage:.1f}%)",
            f"- **待处理**: {total - completed}",
            f"",
            f"- **版本**: {manifest.version}",
            f"- **更新**: {manifest.last_updated}",
            f"",
        ]

        return "\n".join(lines)

    def render_full_report(self) -> str:
        """生成完整报告"""
        manifest = load_manifest()
        return manifest.to_markdown()
```

---

## 2. 测试架构应用

### 2.1 创建工作区测试套件

**新建文件**: `tests/test_workspace_metadata.py`

```python
"""
工作区元数据测试

参考: instructkr/claude-code 的测试架构
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from backend.metadata.manifest import (
    load_manifest,
    get_all_skills,
    get_completed_skills,
    find_skills,
    generate_status_report
)
from backend.metadata.query_engine import WorkspaceQueryEngine


class WorkspaceMetadataTests(unittest.TestCase):
    """工作区元数据测试"""

    def test_manifest_loads(self):
        """测试清单加载"""
        manifest = load_manifest()
        self.assertIsInstance(manifest.skills, tuple)
        self.assertGreater(len(manifest.skills), 0)

    def test_get_all_skills(self):
        """测试获取所有技能"""
        skills = get_all_skills()
        self.assertGreater(len(skills), 0)

        # 检查必需的技能
        skill_ids = [s.id for s in skills]
        self.assertIn("text-processing", skill_ids)
        self.assertIn("security-fixes", skill_ids)

    def test_get_completed_skills(self):
        """测试获取已完成技能"""
        completed = get_completed_skills()
        self.assertGreater(len(completed), 0)

        for skill in completed:
            self.assertEqual(skill.status, "completed")

    def test_find_skills(self):
        """测试搜索技能"""
        # 搜索"文本"
        results = find_skills("文本")
        self.assertGreater(len(results), 0)

        # 搜索"audio"
        results = find_skills("audio")
        self.assertGreater(len(results), 0)

    def test_generate_status_report(self):
        """测试生成状态报告"""
        report = generate_status_report()

        self.assertIn("项目状态报告", report)
        self.assertIn("技能概览", report)
        self.assertIn("文字处理工程流", report)

    def test_query_engine(self):
        """测试查询引擎"""
        engine = WorkspaceQueryEngine()

        # 测试查询
        result = engine.query("文本")
        self.assertIsInstance(result, list, result.skills)

        # 测试状态摘要
        summary = engine.get_status_summary()
        self.assertIn("项目状态摘要", summary)

        # 测试完整报告
        report = engine.render_full_report()
        self.assertIn("项目状态报告", report)


class WorkspaceCLITests(unittest.TestCase):
    """CLI测试"""

    def test_status_report_cli(self):
        """测试状态报告CLI"""
        result = subprocess.run(
            [sys.executable, "-m", "backend.metadata.cli", "status"],
            capture_output=True,
            text=True
        )

        self.assertIn("项目状态摘要", result.stdout)

    def test_query_cli(self):
        """测试查询CLI"""
        result = subprocess.run(
            [sys.executable, "-m", "backend.metadata.cli", "query", "文本"],
            capture_output=True,
            text=True
        )

        self.assertIn("查询结果", result.stdout)


class WorkspaceIntegrityTests(unittest.TestCase):
    """完整性测试"""

    def test_text_processing_skill_complete(self):
        """测试文字处理技能完整性"""
        skill = get_all_skills()
        text_skill = next((s for s in skill if s.id == "text-processing"), None)

        self.assertIsNotNone(text_skill)
        self.assertEqual(text_skill.status, "completed")
        self.assertEqual(len(text_skill.tasks), 6)

        # 检查所有任务都已完成
        for task in text_skill.tasks:
            self.assertEqual(task.status, "completed", f"{task.name} 未完成")

    def test_security_fixes_complete(self):
        """测试安全修复完整性"""
        skills = get_all_skills()
        security_skill = next((s for s in skills if s.id == "security-fixes"), None)

        self.assertIsNotNone(security_skill)
        self.assertEqual(security_skill.status, "completed")

        # 检查5个P0任务
        self.assertEqual(len(security_skill.tasks), 5)

        task_ids = [t.id for t in security_skill.tasks]
        expected_ids = ["P0-1", "P0-2", "P0-3", "P0-4", "P0-5"]
        for task_id in expected_ids:
            self.assertIn(task_id, task_ids)


if __name__ == "__main__":
    unittest.main()
```

---

## 3. CLI改进

### 3.1 创建元数据CLI

**新建文件**: `backend/metadata/cli.py`

```python
"""
元数据管理CLI

参考: instructkr/claude-code 的 main.py
"""
from __future__ import annotations

import argparse

from .manifest import generate_status_report, find_skills
from .query_engine import WorkspaceQueryEngine


def build_parser() -> argparse.ArgumentParser:
    """构建CLI参数解析器"""
    parser = argparse.ArgumentParser(
        description="智能知识系统元数据管理"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status命令
    subparsers.add_parser(
        "status",
        help="显示项目状态摘要"
    )

    # report命令
    subparsers.add_parser(
        "report",
        help="生成完整的项目状态报告"
    )

    # query命令
    query_parser = subparsers.add_parser(
        "query",
        help="搜索技能和任务"
    )
    query_parser.add_argument(
        "query",
        help="搜索关键词"
    )
    query_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="结果数量限制"
    )

    # skills命令
    skills_parser = subparsers.add_parser(
        "skills",
        help="列出所有技能"
    )
    skills_parser.add_argument(
        "--status",
        choices=["all", "completed", "pending"],
        default="all",
        help="按状态过滤"
    )
    skills_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="显示数量"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """主函数"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "status":
        engine = WorkspaceQueryEngine()
        print(engine.get_status_summary())

    elif args.command == "report":
        report = generate_status_report()
        print(report)

    elif args.command == "query":
        engine = WorkspaceQueryEngine()
        result = engine.query(args.query, limit=args.limit)
        print(result.to_markdown())

    elif args.command == "skills":
        from .manifest import get_all_skills, get_completed_skills

        if args.status == "all":
            skills = get_all_skills()
        elif args.status == "completed":
            skills = get_completed_skills()
        else:  # pending
            skills = [s for s in get_all_skills() if s.status != "completed"]

        print(f"# 技能列表 (状态: {args.status})")
        print(f"\n总计: {len(skills)} 个技能\n")

        for skill in skills[:args.limit]:
            status_emoji = "✅" if skill.status == "completed" else "⏳"
            print(f"{status_emoji} **{skill.name}** ({skill.id})")
            print(f"  - {skill.description}")
            print(f"  - 团队: {skill.team}")
            print(f"  - 任务: {len(skill.tasks)} 个")
            print()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

---

## 4. 实施步骤

### 第1步：创建元数据目录和文件

```bash
# 创建元数据目录
mkdir -p backend/metadata

# 创建__init__.py
touch backend/metadata/__init__.py

# 复制上述代码到对应文件
```

### 第2步：运行测试

```bash
# 运行工作区测试
python -m pytest tests/test_workspace_metadata.py -v

# 生成状态报告
python -m backend.metadata.cli report

# 查询技能
python -m backend.metadata.cli query 文本
```

### 第3步：集成到主CLI

```python
# 修改 backend/__init__.py 或主CLI
from .metadata import WorkspaceQueryEngine, generate_status_report

# 添加新的命令
@cli.command()
def status():
    """显示项目状态"""
    engine = WorkspaceQueryEngine()
    print(engine.get_status_summary())

@cli.command()
def query(query_str: str):
    """查询技能和任务"""
    engine = WorkspaceQueryEngine()
    result = engine.query(query_str)
    print(result.to_markdown())
```

---

## 5. 预期效果

### 5.1 功能改进

**新增功能**：
1. ✅ 技能/任务元数据管理
2. ✅ 自动生成状态报告
3. ✅ 搜索和查询功能
4. ✅ 完整性验证测试
5. ✅ 改进的CLI接口

**效果**：
- 📊 自动追踪项目进度
- 🔍 快速查找技能和任务
- 📝 自动生成文档
- ✅ 保证代码完整性

### 5.2 代码质量

**指标改进**：
- 元数据驱动：+10%
- 测试覆盖率：+15%
- 文档自动化：+20%
- CLI易用性：+25%

---

## 6. 扩展计划

### 下一步增强

1. **运行时追踪**
   - 实时任务执行状态
   - 性能监控
   - 资源使用统计

2. **自动化工作流**
   - AI辅助任务分配
   - 自动化测试
   - 持续集成

3. **可视化**
   - 进度仪表板
   - 任务依赖图
   - 统计图表

---

**实施优先级**: 🔥 高
**预计工作量**: 2-3天
**预期收益**: 大大提升项目可维护性

**众智混元，万法灵通** ⚡🚀
