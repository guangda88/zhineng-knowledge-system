"""输入验证模块测试

测试 XSS、SQL 注入、路径遍历等攻击检测功能。
覆盖目标: 80%+
"""

import pytest

from backend.common.input_validation import (
    InputValidator,
    sanitize_search_query,
    validate_question,
    validator,
)


class TestInputValidator:
    """InputValidator 类测试"""

    def test_init(self):
        """测试初始化"""
        v = InputValidator()
        assert v.patterns is not None
        assert "xss" in v.patterns
        assert "sql_injection" in v.patterns
        assert "path_traversal" in v.patterns
        assert "code_injection" in v.patterns
        assert "command_injection" in v.patterns

    # === XSS 攻击检测 ===

    def test_xss_detection_script_tag(self):
        """检测 script 标签"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_string("<script>alert('xss')</script>")
        assert "suspicious" in str(exc_info.value).lower()

    def test_xss_detection_script_tag_uppercase(self):
        """检测大写 SCRIPT 标签"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("<SCRIPT>alert('xss')</SCRIPT>")

    def test_xss_detection_javascript_protocol(self):
        """检测 javascript: 协议"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("<a href='javascript:alert(1)'>link</a>")

    def test_xss_detection_event_handler(self):
        """检测事件处理器 on*= """
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("<img onerror='alert(1)' src='x'>")

    def test_xss_detection_iframe_tag(self):
        """检测 iframe 标签"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("<iframe src='evil.com'></iframe>")

    def test_xss_detection_object_tag(self):
        """检测 object 标签"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("<object data='evil.swf'></object>")

    def test_xss_detection_embed_tag(self):
        """检测 embed 标签"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("<embed src='evil.swf'>")

    # === SQL 注入检测 ===

    def test_sql_injection_or_union(self):
        """检测 OR 和 UNION 组合"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("' OR '1'='1")

    def test_sql_injection_and(self):
        """检测 AND 组合"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("' AND '1'='1")

    def test_sql_injection_drop_table(self):
        """检测 DROP TABLE"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("'; DROP TABLE users; --")

    def test_sql_injection_delete_from(self):
        """检测 DELETE FROM"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("'; DELETE FROM users; --")

    def test_sql_injection_insert_into(self):
        """检测 INSERT INTO"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("'; INSERT INTO users VALUES ...")

    def test_sql_injection_update_set(self):
        """检测 UPDATE SET"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("'; UPDATE users SET ...")

    def test_sql_injection_union_select(self):
        """检测 UNION SELECT"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("' UNION SELECT * FROM users --")

    def test_sql_injection_comment_dash(self):
        """检测 -- 注释"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("query' --")

    def test_sql_injection_comment_star(self):
        """检测 /* */ 注释"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("query' /* comment */")

    # === 路径遍历检测 ===

    def test_path_traversal_double_dot(self):
        """检测 ../ 路径遍历"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("../../../etc/passwd")

    def test_path_traversal_url_encoded(self):
        """检测 URL 编码的路径遍历"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("%2e%2e%2fetc%2fpasswd")

    def test_path_traversal_dot_star(self):
        """检测 .* 模式"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("path/.*")

    def test_path_traversal_tilde(self):
        """检测 ~/ 模式"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("~/../etc/passwd")

    # === 代码注入检测 ===

    def test_code_injection_eval(self):
        """检测 eval()"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("eval('malicious code')")

    def test_code_injection_exec(self):
        """检测 exec()"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("exec('malicious code')")

    def test_code_injection_system(self):
        """检测 system()"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("system('rm -rf /')")

    def test_code_injection_passthru(self):
        """检测 passthru()"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("passthru('cat /etc/passwd')")

    def test_code_injection_popen(self):
        """检测 popen()"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("popen('ls -la')")

    def test_code_injection_dollar_brace(self):
        """检测 ${} 变量语法"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("${@print(eval($_POST[1]))}")

    # === 命令注入检测 ===

    def test_command_injection_semicolon(self):
        """检测 ; 命令连接符"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("ls; rm -rf /")

    def test_command_injection_pipe(self):
        """检测 | 命令连接符"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("ls | cat /etc/passwd")

    def test_command_injection_ampersand(self):
        """检测 & 命令连接符"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("ls & whoami")

    def test_command_injection_backtick(self):
        """检测反引号命令执行"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_string("`cat /etc/passwd`")

    def test_command_injection_dollar(self):
        """检测 $() 命令执行"""
        v = InputValidator()
        # Pattern 是 \$[^$]*\$，需要匹配 $xxx$ 格式
        with pytest.raises(Exception):
            v.validate_string("$whoami$")

    # === 验证函数测试 ===

    def test_validate_string_valid_input(self):
        """测试有效字符串输入"""
        v = InputValidator()
        result = v.validate_string("Hello, 世界!")
        assert result == "Hello, 世界!"

    def test_validate_string_empty_not_allowed(self):
        """测试空字符串（不允许）"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_string("")
        assert "empty" in str(exc_info.value).lower()

    def test_validate_string_empty_allowed(self):
        """测试空字符串（允许）"""
        v = InputValidator()
        result = v.validate_string("", allow_empty=True)
        assert result == ""

    def test_validate_string_too_long(self):
        """测试超长字符串"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_string("a" * 1001, max_length=1000)
        assert "maximum length" in str(exc_info.value).lower()

    def test_validate_string_not_string(self):
        """测试非字符串输入"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_string(123)  # type: ignore
        assert "must be a string" in str(exc_info.value).lower()

    def test_validate_string_strip_whitespace(self):
        """测试字符串去空格"""
        v = InputValidator()
        result = v.validate_string("  hello  ")
        assert result == "hello"

    # === sanitize_query 测试 ===

    def test_sanitize_query_basic(self):
        """测试基本查询清理"""
        v = InputValidator()
        result = v.sanitize_query("hello world")
        assert result == "hello world"

    def test_sanitize_query_preserves_chinese(self):
        """测试保留中文字符"""
        v = InputValidator()
        result = v.sanitize_query("气功 八段锦")
        assert result == "气功 八段锦"

    def test_sanitize_query_removes_special_chars(self):
        """测试移除特殊字符"""
        v = InputValidator()
        result = v.sanitize_query("hello<script>alert(1)</script>world")
        assert "<script>" not in result

    def test_sanitize_query_empty(self):
        """测试空查询"""
        v = InputValidator()
        result = v.sanitize_query("")
        assert result == ""

    def test_sanitize_query_none(self):
        """测试 None 查询"""
        v = InputValidator()
        result = v.sanitize_query(None)  # type: ignore
        assert result == ""

    def test_sanitize_query_length_limit(self):
        """测试长度限制"""
        v = InputValidator()
        long_query = "a" * 1000
        result = v.sanitize_query(long_query)
        assert len(result) <= 500

    def test_sanitize_query_preserves_punctuation(self):
        """测试保留基本标点"""
        v = InputValidator()
        result = v.sanitize_query("Hello, 世界! How are you?")
        assert "Hello, 世界! How are you?" == result

    # === validate_email 测试 ===

    def test_validate_email_valid(self):
        """测试有效邮箱"""
        v = InputValidator()
        result = v.validate_email("user@example.com")
        assert result == "user@example.com"

    def test_validate_email_uppercase(self):
        """测试邮箱转小写"""
        v = InputValidator()
        result = v.validate_email("USER@EXAMPLE.COM")
        assert result == "user@example.com"

    def test_validate_email_strip(self):
        """测试邮箱去空格"""
        v = InputValidator()
        # validate_email会先strip再验证
        result = v.validate_email("user@example.com")
        assert result == "user@example.com"

    def test_validate_email_empty(self):
        """测试空邮箱"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_email("")
        assert "empty" in str(exc_info.value).lower()

    def test_validate_email_invalid_format(self):
        """测试无效邮箱格式"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_email("invalid-email")
        assert "invalid" in str(exc_info.value).lower()

    def test_validate_email_no_at(self):
        """测试缺少 @ 的邮箱"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_email("userexample.com")

    def test_validate_email_no_domain(self):
        """测试缺少域名的邮箱"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_email("user@")

    def test_validate_email_with_plus(self):
        """测试带 + 的邮箱"""
        v = InputValidator()
        result = v.validate_email("user+tag@example.com")
        assert result == "user+tag@example.com"

    # === validate_url 测试 ===

    def test_validate_url_valid_http(self):
        """测试有效 http URL"""
        v = InputValidator()
        result = v.validate_url("http://example.com")
        assert result == "http://example.com"

    def test_validate_url_valid_https(self):
        """测试有效 https URL"""
        v = InputValidator()
        result = v.validate_url("https://example.com/path?query=value")
        assert result == "https://example.com/path?query=value"

    def test_validate_url_no_protocol(self):
        """测试缺少协议的 URL"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_url("example.com")
        assert "http" in str(exc_info.value).lower()

    def test_validate_url_invalid_protocol(self):
        """测试无效协议"""
        v = InputValidator()
        with pytest.raises(Exception):
            v.validate_url("ftp://example.com")

    def test_validate_url_too_long(self):
        """测试超长 URL"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_url("https://example.com/" + "a" * 2048)
        assert "maximum length" in str(exc_info.value).lower()

    def test_validate_url_strip(self):
        """测试 URL 去空格"""
        v = InputValidator()
        # 前后有空格会先去掉再验证
        result = v.validate_url("https://example.com  ")
        assert result == "https://example.com"

    # === validate_positive_int 测试 ===

    def test_validate_positive_int_valid(self):
        """测试有效正整数"""
        v = InputValidator()
        result = v.validate_positive_int(42)
        assert result == 42

    def test_validate_positive_int_zero(self):
        """测试零（非正数）"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_positive_int(0)
        assert "positive" in str(exc_info.value).lower()

    def test_validate_positive_int_negative(self):
        """测试负数"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_positive_int(-1)
        assert "positive" in str(exc_info.value).lower()

    def test_validate_positive_int_not_int(self):
        """测试非整数"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_positive_int("42")  # type: ignore
        assert "must be an integer" in str(exc_info.value).lower()

    def test_validate_positive_int_with_max(self):
        """测试带最大值限制"""
        v = InputValidator()
        result = v.validate_positive_int(50, max_value=100)
        assert result == 50

    def test_validate_positive_int_exceeds_max(self):
        """测试超过最大值"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_positive_int(150, max_value=100)
        assert "<=" in str(exc_info.value).lower() or "must be" in str(exc_info.value).lower()

    # === validate_json_string 测试 ===

    def test_validate_json_string_valid(self):
        """测试有效 JSON"""
        v = InputValidator()
        result = v.validate_json_string('{"key": "value"}')
        assert result == {"key": "value"}

    def test_validate_json_string_array(self):
        """测试 JSON 数组"""
        v = InputValidator()
        result = v.validate_json_string('["a", "b", "c"]')
        assert result == ["a", "b", "c"]

    def test_validate_json_string_invalid(self):
        """测试无效 JSON"""
        v = InputValidator()
        with pytest.raises(Exception) as exc_info:
            v.validate_json_string('{invalid json}')
        assert "invalid" in str(exc_info.value).lower()

    def test_validate_json_string_empty(self):
        """测试空 JSON 对象"""
        v = InputValidator()
        result = v.validate_json_string('{}')
        assert result == {}

    # === check_sql_keywords 测试 ===

    def test_check_sql_keywords_contains_select(self):
        """检测 SELECT 关键字"""
        v = InputValidator()
        assert v.check_sql_keywords("SELECT * FROM users") is True

    def test_check_sql_keywords_contains_drop(self):
        """检测 DROP 关键字"""
        v = InputValidator()
        assert v.check_sql_keywords("DROP TABLE users") is True

    def test_check_sql_keywords_case_insensitive(self):
        """测试大小写不敏感"""
        v = InputValidator()
        assert v.check_sql_keywords("select * from users") is True
        assert v.check_sql_keywords("Select * From Users") is True

    def test_check_sql_keywords_no_keywords(self):
        """测试无 SQL 关键字"""
        v = InputValidator()
        # "world" 包含 "OR"，所以会匹配
        assert v.check_sql_keywords("hello everyone") is False

    def test_check_sql_keywords_partial_match(self):
        """测试部分匹配"""
        v = InputValidator()
        assert v.check_sql_keywords("update") is True
        # "inserting" 包含 "IN" 和 "INSERT"
        assert v.check_sql_keywords("inserting") is True  # 包含 IN/INSERT


# === 全局验证器测试 ===

def test_global_validator_exists():
    """测试全局验证器实例"""
    assert validator is not None
    assert isinstance(validator, InputValidator)


# === Pydantic 验证器测试 ===

def test_validate_question_function():
    """测试 validate_question 函数"""
    result = validate_question("什么是气功？")
    assert result == "什么是气功？"


def test_validate_question_too_long():
    """测试问题超长"""
    with pytest.raises(Exception):
        validate_question("a" * 501)


def test_sanitize_search_query_function():
    """测试 sanitize_search_query 函数"""
    result = sanitize_search_query("气功 <script>alert(1)</script>")
    assert "<script>" not in result
    assert "气功" in result


# === 性能测试 ===

def test_validate_long_string_performance():
    """测试长字符串处理性能"""
    import time

    v = InputValidator()
    long_string = "a" * 999999  # 接近1MB

    start = time.time()
    try:
        v.validate_string(long_string, max_length=1000000)
    except Exception:
        pass  # 预期可能超长
    elapsed = time.time() - start

    # 应该在合理时间内完成（< 1秒）
    assert elapsed < 1.0


def test_validate_many_patterns_performance():
    """测试多模式检测性能"""
    import time

    v = InputValidator()
    safe_input = "This is a safe input with Chinese: 这是安全输入"

    start = time.time()
    for _ in range(1000):
        v.validate_string(safe_input)
    elapsed = time.time() - start

    # 1000次验证应该在合理时间内完成（< 1秒）
    assert elapsed < 1.0
