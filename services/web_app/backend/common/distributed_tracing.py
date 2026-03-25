# -*- coding: utf-8 -*-
"""
Distributed Tracing Integration
分布式追踪集成

Provides distributed tracing capabilities for microservices architecture:
- Trace context propagation across service boundaries
- Span creation and management
- Integration with OpenTelemetry concepts
- Correlation with external systems
"""

import uuid
import time
from contextvars import ContextVar
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# Context variables for trace propagation
_trace_context_var: ContextVar["TraceContext"] = ContextVar(
    "trace_context", default=None
)


class TraceStatus(Enum):
    """Trace span status"""

    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Span:
    """
    A span represents a unit of work in a distributed trace
    Span 表示分布式追踪中的一个工作单元
    """

    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: Optional[str] = None
    operation_name: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: TraceStatus = TraceStatus.STARTED
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    service_name: str = ""

    @property
    def duration_ms(self) -> Optional[float]:
        """Get span duration in milliseconds"""
        if self.end_time is not None:
            return (self.end_time - self.start_time) * 1000
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary for logging"""
        return {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation_name,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "tags": self.tags,
            "service": self.service_name,
            "log_count": len(self.logs),
        }

    def finish(self, status: TraceStatus = TraceStatus.COMPLETED) -> None:
        """Mark the span as finished"""
        self.end_time = time.time()
        self.status = status

    def add_tag(self, key: str, value: Any) -> None:
        """Add a tag to this span"""
        self.tags[key] = value

    def add_tags(self, tags: Dict[str, Any]) -> None:
        """Add multiple tags to this span"""
        self.tags.update(tags)

    def log(self, message: str, **kwargs) -> None:
        """Add a log entry to this span"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            **kwargs,
        }
        self.logs.append(log_entry)


@dataclass
class TraceContext:
    """
    Trace context for distributed tracing
    分布式追踪上下文

    Manages the trace across service boundaries
    """

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    parent_span_id: Optional[str] = None
    spans: List[Span] = field(default_factory=list)
    baggage: Dict[str, str] = field(default_factory=dict)

    # Common tracing headers
    TRACE_ID_HEADER = "X-Trace-ID"
    SPAN_ID_HEADER = "X-Span-ID"
    PARENT_SPAN_HEADER = "X-Parent-Span-ID"
    BAGGAGE_HEADER = "X-Trace-Baggage"

    def create_span(self, operation_name: str, **kwargs) -> Span:
        """
        Create a new span as a child of current trace

        Args:
            operation_name: Name of the operation being traced
            **kwargs: Additional tags for the span

        Returns:
            A new Span instance
        """
        span = Span(
            operation_name=operation_name,
            parent_span_id=self.get_current_span_id(),
            service_name=self.service_name,
            tags=kwargs,
        )
        self.spans.append(span)
        return span

    def get_current_span_id(self) -> Optional[str]:
        """Get the ID of the most recent active span"""
        if self.spans:
            return self.spans[-1].span_id
        return None

    def add_baggage(self, key: str, value: str) -> None:
        """Add baggage item (propagated to downstream services)"""
        self.baggage[key] = value

    def get_baggage(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get baggage item"""
        return self.baggage.get(key, default)

    def to_headers(self) -> Dict[str, str]:
        """
        Convert trace context to HTTP headers for propagation

        Returns:
            Dictionary of headers to send with outbound requests
        """
        headers = {
            self.TRACE_ID_HEADER: self.trace_id,
        }
        if self.spans:
            current_span = self.spans[-1]
            headers[self.SPAN_ID_HEADER] = current_span.span_id

        if self.baggage:
            # Encode baggage as comma-separated key=value pairs
            baggage_str = ",".join(f"{k}={v}" for k, v in self.baggage.items())
            headers[self.BAGGAGE_HEADER] = baggage_str

        return headers

    @classmethod
    def from_headers(cls, headers: Dict[str, str], service_name: str) -> "TraceContext":
        """
        Create TraceContext from incoming HTTP headers

        Args:
            headers: Incoming request headers
            service_name: Name of the current service

        Returns:
            A new TraceContext instance
        """
        # Extract or generate trace ID
        trace_id = headers.get(cls.TRACE_ID_HEADER) or str(uuid.uuid4())

        # Extract parent span if present
        parent_span_id = headers.get(cls.SPAN_ID_HEADER)

        # Parse baggage
        baggage = {}
        baggage_header = headers.get(cls.BAGGAGE_HEADER, "")
        for item in baggage_header.split(","):
            if "=" in item:
                key, value = item.split("=", 1)
                baggage[key.strip()] = value.strip()

        return cls(
            trace_id=trace_id,
            service_name=service_name,
            parent_span_id=parent_span_id,
            baggage=baggage,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace context to dictionary for logging"""
        return {
            "trace_id": self.trace_id,
            "service": self.service_name,
            "parent_span_id": self.parent_span_id,
            "span_count": len(self.spans),
            "baggage": self.baggage,
            "spans": [
                span.to_dict() for span in self.spans if span.duration_ms is not None
            ],
        }


def get_trace_context() -> Optional[TraceContext]:
    """Get the current trace context from context variable"""
    return _trace_context_var.get()


def set_trace_context(context: TraceContext) -> None:
    """Set the trace context in the context variable"""
    _trace_context_var.set(context)


def clear_trace_context() -> None:
    """Clear the trace context"""
    _trace_context_var.set(None)


def init_trace_context(
    service_name: str, headers: Optional[Dict[str, str]] = None
) -> TraceContext:
    """
    Initialize a new trace context

    Args:
        service_name: Name of the current service
        headers: Optional incoming request headers

    Returns:
        A new TraceContext instance
    """
    if headers:
        context = TraceContext.from_headers(headers, service_name)
    else:
        context = TraceContext(service_name=service_name)

    set_trace_context(context)
    return context


class TracedOperation:
    """
    Context manager for tracing operations
    追踪操作的上下文管理器

    Usage:
        with TracedOperation("database_query", table="users"):
            # perform database query
            pass
    """

    def __init__(self, operation_name: str, **tags):
        self.operation_name = operation_name
        self.tags = tags

    def __enter__(self):
        context = get_trace_context()
        if context is None:
            # Auto-initialize context if not present
            context = TraceContext(service_name="unknown")
            set_trace_context(context)

        self.span = context.create_span(self.operation_name, **self.tags)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.span.finish(TraceStatus.FAILED)
            self.span.log("Operation failed", error=str(exc_val))
        else:
            self.span.finish(TraceStatus.COMPLETED)


def trace_incoming_request(
    service_name: str, headers: Dict[str, str], operation_name: str = "http_request"
) -> Span:
    """
    Trace an incoming HTTP request

    Args:
        service_name: Name of the service
        headers: Request headers
        operation_name: Name for the operation span

    Returns:
        A Span for the request
    """
    context = init_trace_context(service_name, headers)
    span = context.create_span(operation_name)

    # Log request details
    span.add_tag("request_type", "incoming")
    span.log("Request received")

    return span


def trace_outgoing_request(
    url: str, method: str, operation_name: Optional[str] = None
) -> Span:
    """
    Trace an outgoing HTTP request

    Args:
        url: Target URL
        method: HTTP method
        operation_name: Optional name for the span

    Returns:
        Headers dict with tracing info and the created span
    """
    context = get_trace_context()
    if context is None:
        return {}, None

    span = context.create_span(operation_name or f"http_{method.lower()}")
    span.add_tag("http.method", method)
    span.add_tag("http.url", url)
    span.add_tag("request_type", "outgoing")

    headers = context.to_headers()

    return headers, span


def propagate_trace_headers(
    base_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Get headers for trace propagation

    Args:
        base_headers: Existing headers to extend

    Returns:
        Headers dictionary with trace information
    """
    context = get_trace_context()
    if context is None:
        return base_headers or {}

    trace_headers = context.to_headers()

    if base_headers:
        result = base_headers.copy()
        result.update(trace_headers)
        return result

    return trace_headers


class DistributedTracer:
    """
    High-level distributed tracing interface
    分布式追踪高级接口

    Provides convenient methods for common tracing scenarios
    """

    def __init__(self, service_name: str):
        self.service_name = service_name

    def trace_database_query(
        self, query: str, db_type: str = "postgresql", **kwargs
    ) -> Span:
        """Trace a database query"""
        context = get_trace_context()
        if context is None:
            context = init_trace_context(self.service_name, {})

        span = context.create_span("database_query")
        span.add_tags(
            {
                "db.type": db_type,
                "db.query": query[:500],  # Truncate long queries
                **kwargs,
            }
        )
        span.log("Database query started")
        return span

    def trace_cache_operation(
        self,
        operation: str,  # hit, miss, set, delete
        key: str,
        cache_type: str = "redis",
    ) -> Span:
        """Trace a cache operation"""
        context = get_trace_context()
        if context is None:
            context = init_trace_context(self.service_name, {})

        span = context.create_span(f"cache_{operation}")
        span.add_tags(
            {
                "cache.type": cache_type,
                "cache.key": key[:200],  # Truncate long keys
            }
        )
        return span

    def trace_external_call(
        self, service: str, endpoint: str, method: str = "POST", **kwargs
    ) -> Span:
        """Trace an external service call"""
        context = get_trace_context()
        if context is None:
            context = init_trace_context(self.service_name, {})

        span = context.create_span(f"external_{service.lower()}")
        span.add_tags(
            {
                "external.service": service,
                "external.endpoint": endpoint,
                "external.method": method,
                **kwargs,
            }
        )
        return span

    def trace_search_operation(
        self, query: str, results_count: int, search_type: str = "hybrid", **kwargs
    ) -> Span:
        """Trace a search operation"""
        context = get_trace_context()
        if context is None:
            context = init_trace_context(self.service_name, {})

        span = context.create_span("search")
        span.add_tags(
            {
                "search.query": query[:200],
                "search.results_count": results_count,
                "search.type": search_type,
                **kwargs,
            }
        )
        return span

    def trace_document_operation(
        self,
        operation: str,  # upload, download, delete, update
        document_id: str,
        **kwargs,
    ) -> Span:
        """Trace a document operation"""
        context = get_trace_context()
        if context is None:
            context = init_trace_context(self.service_name, {})

        span = context.create_span(f"document_{operation}")
        span.add_tags(
            {"document.id": document_id, "document.operation": operation, **kwargs}
        )
        return span


def get_tracer(service_name: str) -> DistributedTracer:
    """Get a tracer instance for the given service"""
    return DistributedTracer(service_name)


# Convenience decorator for tracing functions
def traced(operation_name: Optional[str] = None):
    """
    Decorator to automatically trace function execution

    Usage:
        @traced("user_authentication")
        def authenticate_user(username, password):
            # ... authentication logic
            pass
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            with TracedOperation(op_name):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Context manager will mark as failed
                    raise

        return wrapper

    return decorator
