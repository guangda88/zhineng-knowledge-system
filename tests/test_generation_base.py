"""生成器基类测试

测试services/generation/base.py的基础功能
"""

from backend.services.generation.base import (
    BaseGenerator,
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
    OutputFormat,
)


class TestOutputFormat:
    """输出格式枚举测试"""

    def test_format_values(self):
        """测试格式值"""
        # 使用实际的枚举值
        formats = [f.value for f in OutputFormat]
        assert "json" in formats
        assert "markdown" in formats or "md" in formats


class TestGenerationStatus:
    """生成状态枚举测试"""

    def test_status_values(self):
        """测试状态值"""
        assert GenerationStatus.PENDING.value == "pending"
        assert GenerationStatus.IN_PROGRESS.value == "in_progress"
        assert GenerationStatus.COMPLETED.value == "completed"
        assert GenerationStatus.FAILED.value == "failed"


class TestGenerationRequest:
    """生成请求测试"""

    def test_request_creation(self):
        """测试请求创建"""
        request = GenerationRequest(
            task_id="task1",
            topic="智能气功基础",
            content_type="report",
            parameters={"style": "educational"},
            output_format=OutputFormat.MARKDOWN,
        )
        assert request.task_id == "task1"
        assert request.topic == "智能气功基础"
        assert request.content_type == "report"
        assert request.parameters["style"] == "educational"
        assert request.output_format == OutputFormat.MARKDOWN

    def test_request_defaults(self):
        """测试请求默认值"""
        request = GenerationRequest(
            task_id="task2",
            topic="测试主题",
            content_type="analysis",
            parameters={},
            output_format=OutputFormat.JSON,
        )
        assert request.created_at is not None


class TestGenerationResult:
    """生成结果测试"""

    def test_result_success(self):
        """测试成功结果"""
        result = GenerationResult(
            task_id="task1",
            status=GenerationStatus.COMPLETED,
            output_path="/outputs/test1.md",
            output_url="/outputs/test1.md",
            metadata={"words": 1000},
        )
        assert result.task_id == "task1"
        assert result.status == GenerationStatus.COMPLETED
        assert result.output_path == "/outputs/test1.md"
        assert result.error_message is None

    def test_result_failure(self):
        """测试失败结果"""
        result = GenerationResult(
            task_id="task2",
            status=GenerationStatus.FAILED,
            error_message="生成失败：无法连接到AI服务",
        )
        assert result.status == GenerationStatus.FAILED
        assert result.error_message == "生成失败：无法连接到AI服务"
        assert result.output_path is None


class TestBaseGenerator:
    """生成器基类测试"""

    def test_base_generator_is_abstract(self):
        """测试基类是抽象类"""
        # BaseGenerator是抽象类，不能直接实例化
        from abc import ABC

        assert issubclass(BaseGenerator, ABC)

    def test_base_generator_has_required_methods(self):
        """测试基类有必需的方法"""

        # 检查抽象方法存在
        assert hasattr(BaseGenerator, "generate")
        assert hasattr(BaseGenerator, "validate_request")
        assert hasattr(BaseGenerator, "generate_with_progress")
