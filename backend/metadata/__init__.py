"""
元数据管理包

基于 instructkr/claude-code 的元数据驱动架构
"""

from .manifest import (
    ProjectManifest,
    TaskMetadata,
    WorkflowMetadata,
    find_workflows,
    generate_status_report,
    get_all_workflows,
    get_completed_workflows,
    get_workflow_by_id,
    load_manifest,
)

__all__ = [
    "load_manifest",
    "get_all_workflows",
    "get_completed_workflows",
    "get_workflow_by_id",
    "find_workflows",
    "generate_status_report",
    "ProjectManifest",
    "WorkflowMetadata",
    "TaskMetadata",
]
