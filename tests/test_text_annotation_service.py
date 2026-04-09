"""
测试文本标注服务（Text Annotation Service）

文字处理工程流A-5的测试套件
"""

from unittest.mock import Mock

import pytest

from backend.services.text_annotation_service import AnnotationTagService, TextAnnotationService


class TestTextAnnotationService:
    """测试文本标注服务"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock数据库会话"""
        session = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.refresh = Mock()
        session.query = Mock()
        session.delete = Mock()
        return session

    @pytest.fixture
    def service(self, mock_db_session):
        """创建服务实例"""
        return TextAnnotationService(mock_db_session)

    def test_create_annotation(self, service, mock_db_session):
        """测试创建标注"""
        # Mock查询结果
        mock_annotation = Mock()
        mock_annotation.id = 1
        mock_annotation.annotation_type = "keyword"
        mock_db_session.refresh = Mock(return_value=mock_annotation)

        # 创建标注
        service.create_annotation(
            text_block_id=1,
            annotation_type="keyword",
            content="混元灵通",
            start_pos=0,
            end_pos=4,
            importance="high",
            created_by="test_user",
        )

        # 验证调用
        assert mock_db_session.add.called
        assert mock_db_session.commit.called

    def test_get_annotation(self, service, mock_db_session):
        """测试获取标注"""
        # Mock查询结果
        mock_query = Mock()
        mock_annotation = Mock()
        mock_annotation.id = 1
        mock_query.filter.return_value.first.return_value = mock_annotation
        mock_db_session.query.return_value = mock_query

        # 获取标注
        result = service.get_annotation(1)

        # 验证
        assert result is not None
        assert result.id == 1

    def test_delete_annotation(self, service, mock_db_session):
        """测试删除标注"""
        # Mock查询结果
        mock_query = Mock()
        mock_annotation = Mock()
        mock_query.filter.return_value.first.return_value = mock_annotation
        mock_db_session.query.return_value = mock_query

        # 删除标注
        result = service.delete_annotation(1)

        # 验证
        assert result is True
        assert mock_db_session.delete.called
        assert mock_db_session.commit.called

    def test_export_json(self, service):
        """测试导出为JSON"""
        annotations = [
            {
                "id": 1,
                "text_block_id": 1,
                "annotation_type": "keyword",
                "content": "混元灵通",
                "importance": "high",
                "confidence": 0.95,
            },
            {
                "id": 2,
                "text_block_id": 1,
                "annotation_type": "topic",
                "content": "智能气功理论",
                "importance": "medium",
                "confidence": 0.85,
            },
        ]

        # 导出JSON
        json_content = service._export_json(annotations)

        # 验证
        assert "混元灵通" in json_content
        assert "智能气功理论" in json_content
        assert '"id": 1' in json_content

    def test_export_csv(self, service):
        """测试导出为CSV"""
        annotations = [
            {
                "id": 1,
                "text_block_id": 1,
                "annotation_type": "keyword",
                "content": "混元灵通",
                "importance": "high",
                "confidence": 0.95,
                "created_by": "test_user",
                "created_at": "2026-04-01T00:00:00",
            }
        ]

        # 导出CSV
        csv_content = service._export_csv(annotations)

        # 验证
        assert "id,text_block_id,annotation_type,content" in csv_content
        assert "混元灵通" in csv_content

    def test_get_statistics(self, service, mock_db_session):
        """测试获取统计信息"""
        # Mock查询结果
        mock_query = Mock()
        mock_annotations = [
            Mock(annotation_type="keyword", importance="high", confidence=0.9),
            Mock(annotation_type="keyword", importance="medium", confidence=0.8),
            Mock(annotation_type="topic", importance="low", confidence=0.7),
        ]
        mock_query.all.return_value = mock_annotations
        mock_query.filter.return_value.all.return_value = mock_annotations
        mock_db_session.query.return_value = mock_query

        # 获取统计
        stats = service.get_annotation_statistics()

        # 验证
        assert stats["total_annotations"] == 3
        assert stats["type_distribution"]["keyword"] == 2
        assert stats["type_distribution"]["topic"] == 1
        assert stats["average_confidence"] == pytest.approx(0.8, 0.1)


class TestAnnotationTagService:
    """测试标注标签服务"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock数据库会话"""
        session = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.refresh = Mock()
        session.query = Mock()
        return session

    @pytest.fixture
    def service(self, mock_db_session):
        """创建服务实例"""
        return AnnotationTagService(mock_db_session)

    def test_create_tag(self, service, mock_db_session):
        """测试创建标签"""
        # Mock查询结果
        mock_tag = Mock()
        mock_tag.id = 1
        mock_tag.name = "气功理论"
        mock_db_session.refresh.return_value = mock_tag

        # 创建标签
        service.create_tag(name="气功理论", description="智能气功相关理论标签", color="#FF0000")

        # 验证
        assert mock_db_session.add.called
        assert mock_db_session.commit.called

    def test_get_tag(self, service, mock_db_session):
        """测试获取标签"""
        # Mock查询结果
        mock_query = Mock()
        mock_tag = Mock()
        mock_tag.id = 1
        mock_tag.name = "气功理论"
        mock_query.filter.return_value.first.return_value = mock_tag
        mock_db_session.query.return_value = mock_query

        # 获取标签
        result = service.get_tag(1)

        # 验证
        assert result is not None
        assert result.id == 1
        assert result.name == "气功理论"

    def test_increment_usage(self, service, mock_db_session):
        """测试增加使用次数"""
        # Mock查询结果
        mock_query = Mock()
        mock_tag = Mock()
        mock_tag.id = 1
        mock_tag.usage_count = 5
        mock_query.filter.return_value.first.return_value = mock_tag
        mock_db_session.query.return_value = mock_query

        # 增加使用次数
        service.increment_usage(1)

        # 验证
        assert mock_tag.usage_count == 6
        assert mock_db_session.commit.called


# 集成测试示例
@pytest.mark.integration
class TestAnnotationIntegration:
    """集成测试示例"""

    def test_end_to_end_annotation_workflow(self):
        """端到端标注工作流测试"""
        # 这个测试需要真实数据库连接
        # 仅作为示例展示

        # 1. 创建标注
        # 2. 添加评论
        # 3. 导出标注
        # 4. 获取统计信息

        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
