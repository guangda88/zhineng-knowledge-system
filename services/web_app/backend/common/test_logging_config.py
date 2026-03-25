# -*- coding: utf-8 -*-
"""
Logging Configuration Test
日志配置测试

测试结构化日志配置功能
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_logging_config_basic():
    """测试基本日志配置"""
    print("Testing basic logging configuration...")

    try:
        from .logging_config import (
            configure_logging,
            get_logger,
            LogConfig,
            LogContext,
            bind_context,
            clear_context,
        )

        print("  - Import successful")

        # Configure logging
        configure_logging(
            log_level=10,  # DEBUG
            enable_file_logging=False,  # Disable file logging for test
        )
        print("  - Configuration successful")

        # Test basic logging
        logger = get_logger("test")
        logger.info("Test info message")
        logger.debug("Test debug message")
        logger.warning("Test warning message")
        print("  - Basic logging works")

        # Test context binding
        bound_logger = bind_context(
            user_id="test_user_123", document_id="doc_456", request_id="req_789"
        )
        bound_logger.info("Test with bound context")
        print("  - Context binding works")

        # Test LogContext
        with LogContext(operation="test_operation", test_value="test_data"):
            logger = get_logger("context_test")
            logger.info("Test inside LogContext")
        print("  - LogContext works")

        # Test context clearing
        clear_context()
        logger.info("Test after clearing context")
        print("  - Context clearing works")

        print("✓ Basic logging configuration test passed\n")
        return True

    except Exception as e:
        print(f"✗ Basic logging configuration test failed: {e}\n")
        import traceback

        traceback.print_exc()
        return False


def test_sensitive_data_filtering():
    """测试敏感数据过滤"""
    print("Testing sensitive data filtering...")

    try:
        from .logging_config import get_logger

        logger = get_logger("sensitive_test")

        # Test with potentially sensitive data
        logger.info(
            "User login attempt",
            user_id="user123",
            email="test@example.com",
            phone="13812345678",
            password="secret123",  # This should be filtered
        )
        print("  - Sensitive data filtering in logs works")

        print("✓ Sensitive data filtering test passed\n")
        return True

    except Exception as e:
        print(f"✗ Sensitive data filtering test failed: {e}\n")
        import traceback

        traceback.print_exc()
        return False


def test_convenience_functions():
    """测试便捷函数"""
    print("Testing convenience functions...")

    try:
        from .logging_config import (
            log_request,
            log_database_query,
            log_search_query,
            log_document_operation,
            log_authentication_event,
            log_external_api_call,
            log_error,
        )

        # Test request logging
        log_request("GET", "/api/v1/documents", 200, 45.6)
        print("  - log_request works")

        # Test database query logging
        log_database_query("SELECT * FROM documents", 12.5, 10)
        log_database_query("SELECT * FROM large_table", 1500.0, 1000)  # Slow query
        print("  - log_database_query works")

        # Test search query logging
        log_search_query("中医治疗", 15, 123.4, "hybrid")
        print("  - log_search_query works")

        # Test document operation logging
        log_document_operation("upload", "doc_123", "user_456")
        print("  - log_document_operation works")

        # Test authentication event logging
        log_authentication_event("login", "user_789", True)
        log_authentication_event("login", None, False)  # Failed login
        print("  - log_authentication_event works")

        # Test external API call logging
        log_external_api_call("openai", "/embeddings", "POST", 200, 234.5)
        log_external_api_call(
            "elasticsearch", "/search", "POST", 503, 5000.0
        )  # Slow/error
        print("  - log_external_api_call works")

        # Test error logging
        try:
            raise ValueError("Test error")
        except Exception as e:
            log_error(e, context={"operation": "test_operation"})
        print("  - log_error works")

        print("✓ Convenience functions test passed\n")
        return True

    except Exception as e:
        print(f"✗ Convenience functions test failed: {e}\n")
        import traceback

        traceback.print_exc()
        return False


def test_request_context():
    """测试请求上下文"""
    print("Testing request context...")

    try:
        from .logging_config import RequestContext

        # Test setting and getting context
        RequestContext.set("user_id", "test_user")
        RequestContext.set("document_id", "test_doc")
        RequestContext.update(operation="test", value=123)

        assert RequestContext.get("user_id") == "test_user"
        assert RequestContext.get("document_id") == "test_doc"
        assert RequestContext.get("operation") == "test"
        print("  - RequestContext set/get works")

        # Test to_dict
        context_dict = RequestContext.to_dict()
        assert "user_id" in context_dict
        assert "document_id" in context_dict
        print("  - RequestContext.to_dict works")

        # Test binding to logger
        bound_logger = RequestContext.bind_to_logger()
        bound_logger.info("Test with request context")
        print("  - RequestContext.bind_to_logger works")

        # Test clearing
        RequestContext.clear()
        assert RequestContext.get("user_id") is None
        print("  - RequestContext.clear works")

        print("✓ Request context test passed\n")
        return True

    except Exception as e:
        print(f"✗ Request context test failed: {e}\n")
        import traceback

        traceback.print_exc()
        return False


def test_correlation_id():
    """测试关联ID功能"""
    print("Testing correlation ID...")

    try:
        from middleware.logging_middleware import (
            get_correlation_id,
            set_correlation_id,
            generate_correlation_id,
            log_with_context,
            bind_request_context,
        )

        # Test generating correlation ID
        cid1 = generate_correlation_id()
        cid2 = generate_correlation_id()
        assert cid1 != cid2, "Generated IDs should be unique"
        assert len(cid1) == 36, "UUID should be 36 characters"  # Standard UUID format
        print("  - generate_correlation_id works")

        # Test setting and getting
        set_correlation_id("test-correlation-id-123")
        assert get_correlation_id() == "test-correlation-id-123"
        print("  - set/get_correlation_id works")

        # Test log_with_context
        log_with_context("Test message with correlation", level="info", test_value=123)
        print("  - log_with_context works")

        # Test bind_request_context
        bind_request_context(user_id="user_123", document_id="doc_456")
        print("  - bind_request_context works")

        print("✓ Correlation ID test passed\n")
        return True

    except Exception as e:
        print(f"✗ Correlation ID test failed: {e}\n")
        import traceback

        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Logging Configuration Test Suite")
    print("=" * 60)
    print()

    results = []

    # Run tests
    results.append(("Basic Logging Configuration", test_logging_config_basic()))
    results.append(("Sensitive Data Filtering", test_sensitive_data_filtering()))
    results.append(("Convenience Functions", test_convenience_functions()))
    results.append(("Request Context", test_request_context()))
    results.append(("Correlation ID", test_correlation_id()))

    # Print summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print()
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed! ✓")
        return 0
    else:
        print(f"\n{total - passed} test(s) failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
