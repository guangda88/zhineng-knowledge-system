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
    source_hint: str
    status: str
    lines: Optional[int] = None
    tests: Optional[str] = None
    cve: Optional[str] = None


@dataclass(frozen=True)
class WorkflowMetadata:
    """工作流元数据"""

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

    workflows: tuple[WorkflowMetadata, ...]
    version: str
    last_updated: str

    def get_completed_workflows(self) -> tuple[WorkflowMetadata, ...]:
        """获取已完成的工作流"""
        return tuple(w for w in self.workflows if w.status == "completed")

    def get_pending_workflows(self) -> tuple[WorkflowMetadata, ...]:
        """获取待处理的工作流"""
        return tuple(w for w in self.workflows if w.status == "pending")

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowMetadata]:
        """按ID获取工作流"""
        for workflow in self.workflows:
            if workflow.id == workflow_id:
                return workflow
        return None

    def to_markdown(self) -> str:
        """生成Markdown报告"""
        lines = [
            "# 项目状态报告",
            "",
            f"**版本**: {self.version}",
            f"**更新时间**: {self.last_updated}",
            "",
            "## 工作流概览",
            "",
            f"- 总工作流数: **{len(self.workflows)}**",
            f"- 已完成: **{len(self.get_completed_workflows())}**",
            f"- 待处理: **{len(self.get_pending_workflows())}**",
            "",
        ]

        for workflow in self.workflows:
            status_emoji = "✅" if workflow.status == "completed" else "⏳"
            lines.append(f"### {status_emoji} {workflow.name}")
            lines.append("")
            lines.append(f"- **ID**: {workflow.id}")
            lines.append(f"- **团队**: {workflow.team}")
            lines.append(f"- **状态**: {workflow.status}")
            lines.append(f"- **任务数**: {len(workflow.tasks)}")

            if workflow.total_lines:
                lines.append(f"- **代码行数**: {workflow.total_lines}")

            lines.append("")
            lines.append("#### 任务列表")
            lines.append("")

            for task in workflow.tasks:
                task_status = "✅" if task.status == "completed" else "⏳"
                lines.append(f"- {task_status} **{task.id}**: {task.name}")
                if task.source_hint:
                    lines.append(f"  - 文件: `{task.source_hint}`")

            lines.append("")

        return "\\n".join(lines)


@lru_cache(maxsize=1)
def load_manifest() -> ProjectManifest:
    """加载项目清单"""
    manifest_path = Path(__file__).parent / "workflows_manifest.json"

    if not manifest_path.exists():
        # 返回空清单
        return ProjectManifest(workflows=(), version="0.0.0", last_updated="")

    data = json.loads(manifest_path.read_text())

    workflows = []
    for workflow_data in data.get("workflows", []):
        tasks = tuple(TaskMetadata(**task_data) for task_data in workflow_data.get("tasks", []))

        workflows.append(
            WorkflowMetadata(
                id=workflow_data["id"],
                name=workflow_data["name"],
                description=workflow_data["description"],
                team=workflow_data["team"],
                status=workflow_data["status"],
                tasks=tasks,
                total_lines=workflow_data.get("total_lines"),
                completed_at=workflow_data.get("completed_at"),
            )
        )

    metadata = data.get("metadata", {})

    return ProjectManifest(
        workflows=tuple(workflows),
        version=metadata.get("version", "1.0.0"),
        last_updated=metadata.get("last_updated", ""),
    )


# 便捷API
def get_all_workflows() -> tuple[WorkflowMetadata, ...]:
    """获取所有工作流"""
    manifest = load_manifest()
    return manifest.workflows


def get_completed_workflows() -> tuple[WorkflowMetadata, ...]:
    """获取已完成的工作流"""
    manifest = load_manifest()
    return manifest.get_completed_workflows()


def get_workflow_by_id(workflow_id: str) -> Optional[WorkflowMetadata]:
    """按ID获取工作流"""
    manifest = load_manifest()
    return manifest.get_workflow(workflow_id)


def find_workflows(query: str) -> list[WorkflowMetadata]:
    """搜索工作流"""
    manifest = load_manifest()
    needle = query.lower()

    return [
        workflow
        for workflow in manifest.workflows
        if needle in workflow.name.lower()
        or needle in workflow.description.lower()
        or needle in workflow.id.lower()
    ]


def generate_status_report() -> str:
    """生成状态报告"""
    manifest = load_manifest()
    return manifest.to_markdown()


if __name__ == "__main__":
    # 测试：生成状态报告
    print(generate_status_report())
