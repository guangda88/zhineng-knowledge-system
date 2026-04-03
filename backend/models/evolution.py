"""进化系统数据模型

包含多AI对比、自动进化、用户行为追踪相关模型
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DECIMAL,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models"""


# ============================================
# 模型1: 多AI对比记录
# ============================================
class AIComparisonLog(Base):
    """多AI对比记录

    记录灵知系统与竞品AI的对比结果
    """

    __tablename__ = "ai_comparison_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(PGUUID, nullable=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)

    # 请求信息
    request_type = Column(String(50), nullable=False, index=True)
    user_query = Column(Text)
    request_id = Column(String(36))

    # 灵知系统回答
    lingzhi_response = Column(Text)
    lingzhi_metadata = Column(JSONB, default=dict)

    # 其他AI回答
    competitor_responses = Column(JSONB)

    # 对比评估
    comparison_metrics = Column(JSONB)
    winner = Column(String(50))

    # 用户行为
    user_behavior = Column(JSONB)
    user_feedback = Column(String(10))  # 'good', 'neutral', 'poor'
    user_comment = Column(Text)
    user_preference = Column(String(50))

    # 进化方向
    improvement_suggestions = Column(Text)
    improvement_status = Column(
        String(20), default="pending"
    )  # 'pending', 'reviewing', 'implementing', 'completed'
    implemented_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # 约束
    __table_args__ = (
        CheckConstraint("request_type IN ('qa', 'podcast', 'other')", name="valid_request_type"),
        CheckConstraint(
            "winner IN ('lingzhi', 'hunyuan', 'doubao', 'deepseek', 'glm', 'tie')",
            name="valid_winner",
        ),
        CheckConstraint(
            "improvement_status IN ('pending', 'reviewing', 'implementing', 'completed', 'rejected')",
            name="valid_improvement_status",
        ),
    )

    def __repr__(self):
        return f"<AIComparisonLog(id={self.id}, request_type={self.request_type}, winner={self.winner})>"


# ============================================
# 模型2: 进化记录
# ============================================
class EvolutionLog(Base):
    """进化记录

    记录系统自我改进的历史
    """

    __tablename__ = "evolution_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    comparison_id = Column(
        BigInteger,
        ForeignKey("ai_comparison_log.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # 发现的问题
    issue_type = Column(String(100))
    issue_category = Column(
        String(50), index=True
    )  # 'knowledge', 'template', 'quality', 'performance'
    issue_description = Column(Text)

    # 改进措施
    improvement_type = Column(
        String(100)
    )  # 'knowledge_update', 'template_optimize', 'prompt_tune', 'bug_fix'
    improvement_action = Column(Text)
    improvement_details = Column(JSONB, default=dict)

    # 执行状态
    status = Column(
        String(20), default="pending", index=True
    )  # 'pending', 'in_progress', 'completed', 'rolled_back'
    priority = Column(
        String(20), default="medium", index=True
    )  # 'critical', 'high', 'medium', 'low'

    # 效果验证
    before_metrics = Column(JSONB)
    after_metrics = Column(JSONB)
    effectiveness_score = Column(Integer)  # 1-5
    verified_at = Column(DateTime, nullable=True)

    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    implemented_at = Column(DateTime, nullable=True)
    implemented_by = Column(String(100))  # 'auto', 'user:xxx', 'admin:xxx'

    # 约束
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'rolled_back')",
            name="valid_evolution_status",
        ),
        CheckConstraint(
            "priority IN ('critical', 'high', 'medium', 'low')", name="valid_evolution_priority"
        ),
        CheckConstraint("effectiveness_score BETWEEN 1 AND 5", name="valid_effectiveness_score"),
    )

    # 关系
    comparison = relationship("AIComparisonLog", backref="evolutions")

    def __repr__(self):
        return f"<EvolutionLog(id={self.id}, type={self.improvement_type}, status={self.status})>"


# ============================================
# 模型3: 用户焦点追踪
# ============================================
class UserFocusLog(Base):
    """用户焦点追踪

    记录用户在页面上的注意力分布
    """

    __tablename__ = "user_focus_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(PGUUID, nullable=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    request_id = Column(String(36), nullable=False, index=True)

    # 焦点数据
    element_id = Column(String(100), index=True)
    element_type = Column(String(50))  # 'heading', 'paragraph', 'link', 'button', 'image', ...
    element_content = Column(Text)  # 匿名化后的内容摘要

    # 交互数据
    dwell_time_ms = Column(Integer)  # 停留时间（毫秒）
    scroll_depth = Column(Integer)  # 滚动深度（像素）
    click_count = Column(Integer, default=0)  # 点击次数

    # 视口位置
    viewport_position = Column(JSONB)  # {x: 100, y: 200, width: 300, height: 400}

    # 上下文
    viewport_size = Column(JSONB)  # {width: 1920, height: 1080}
    device_info = Column(JSONB)  # {user_agent: "...", screen: {...}}

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # 约束
    __table_args__ = (
        CheckConstraint(
            "element_type IN ('heading', 'paragraph', 'link', 'button', 'image', 'list', 'code', 'quote', 'other')",
            name="valid_element_type",
        ),
    )

    def __repr__(self):
        return f"<UserFocusLog(id={self.id}, element_type={self.element_type}, dwell_time={self.dwell_time_ms})>"


# ============================================
# 模型4: AI性能统计
# ============================================
class AIPerformanceStats(Base):
    """AI性能统计

    统计各AI的性能指标和胜率
    """

    __tablename__ = "ai_performance_stats"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False, index=True)  # 'lingzhi', 'hunyuan', ...
    model = Column(String(100))

    # 性能指标
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    avg_latency_ms = Column(Integer)
    p95_latency_ms = Column(Integer)
    p99_latency_ms = Column(Integer)

    # 对比统计
    comparisons_participated = Column(Integer, default=0)
    comparisons_won = Column(Integer, default=0)
    win_rate = Column(DECIMAL(5, 2))

    # 用户偏好
    preferred_by_users = Column(Integer, default=0)

    # 时间窗口
    period_start = Column(DateTime, default=datetime.utcnow, index=True)
    period_end = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 约束
    __table_args__ = (
        CheckConstraint(
            "provider IN ('lingzhi', 'hunyuan', 'doubao', 'deepseek', 'glm')", name="valid_provider"
        ),
    )

    def __repr__(self):
        return f"<AIPerformanceStats(provider={self.provider}, win_rate={self.win_rate})>"

    def update_stats(
        self, success: bool, latency_ms: Optional[int] = None, won: Optional[bool] = None
    ):
        """更新统计数据

        Args:
            success: 请求是否成功
            latency_ms: 请求延迟
            won: 是否赢得对比
        """
        self.total_requests += 1

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        if latency_ms is not None:
            # 简单的移动平均（实际应该用更精确的算法）
            if self.avg_latency_ms is None:
                self.avg_latency_ms = latency_ms
            else:
                self.avg_latency_ms = int((self.avg_latency_ms * 0.9) + (latency_ms * 0.1))

        if won is not None:
            self.comparisons_participated += 1
            if won:
                self.comparisons_won += 1

            if self.comparisons_participated > 0:
                self.win_rate = self.comparisons_won / self.comparisons_participated * 100

        self.updated_at = datetime.utcnow()
