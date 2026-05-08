"""Tests for AI SQL Agent."""

import pytest
from unittest.mock import MagicMock, patch

from ai_sql_agent.config import AgentConfig, DBConfig, ModelProvider, build_provider
from ai_sql_agent.db.connector import DBConnector
from ai_sql_agent.db.dialects import Dialect, DialectType, convert_to_dm
from ai_sql_agent.db.validator import SQLValidator, SQLAutoFixer, validate_and_fix
from ai_sql_agent.utils.formatter import format_sql


class TestDialect:
    def test_get_dm(self):
        d = Dialect.get(DialectType.DM)
        assert d.name == "达梦(DM)"
        assert d.current_time == "SYSDATE"

    def test_get_mysql(self):
        d = Dialect.get(DialectType.MYSQL)
        assert d.name == "MySQL"
        assert d.quote_char == "`"

    def test_get_sqlite(self):
        d = Dialect.get(DialectType.SQLITE)
        assert d.name == "SQLite"
        assert d.current_time == "DATETIME('now')"

    def test_convert_to_dm(self):
        sql = "SELECT IFNULL(name, 'x') FROM `users`"
        result = convert_to_dm(sql)
        assert "NVL" in result
        assert "`" not in result


class TestConfig:
    def test_build_provider_openai(self):
        p = build_provider("openai")
        assert p.name == "openai"
        assert "openai.com" in p.base_url

    def test_build_provider_longcat(self):
        p = build_provider("longcat")
        assert p.name == "longcat"
        assert "longcat" in p.base_url

    def test_build_provider_longcat_thinking(self):
        p = build_provider("longcat-thinking")
        assert p.name == "longcat-thinking"
        assert "Thinking" in p.model

    def test_build_provider_longcat_omni(self):
        p = build_provider("longcat-omni")
        assert p.name == "longcat-omni"
        assert "Omni" in p.model

    def test_build_provider_longcat_lite(self):
        p = build_provider("longcat-lite")
        assert p.name == "longcat-lite"
        assert "Lite" in p.model

    def test_build_provider_mimo(self):
        p = build_provider("mimo")
        assert p.name == "mimo"
        assert "xiaomimimo" in p.base_url

    def test_db_config_is_configured(self):
        c = DBConfig()
        assert not c.is_configured

    def test_db_config_configured(self):
        c = DBConfig(db_type="sqlite", name=":memory:")
        assert c.is_configured

    def test_db_config_sqlite(self):
        c = DBConfig(db_type="sqlite", name=":memory:")
        assert c.is_configured
        assert c.db_type == "sqlite"


class TestFormatter:
    def test_format_basic(self):
        sql = "SELECT id FROM users WHERE age > 18"
        result = format_sql(sql)
        assert "SELECT" in result
        assert "FROM" in result

    def test_format_with_join(self):
        sql = "SELECT u.name FROM users u JOIN orders o ON u.id = o.user_id"
        result = format_sql(sql)
        assert "JOIN" in result


class TestSQLValidator:
    def test_valid_select(self):
        v = SQLValidator(DialectType.MYSQL)
        is_valid, issues = v.validate("SELECT id FROM users WHERE age > 18")
        assert is_valid

    def test_unbalanced_parentheses(self):
        v = SQLValidator(DialectType.MYSQL)
        is_valid, issues = v.validate("SELECT id FROM users WHERE (age > 18")
        assert not is_valid
        assert any("parenthes" in str(i).lower() for i in issues)

    def test_select_star_warning(self):
        v = SQLValidator(DialectType.MYSQL)
        is_valid, issues = v.validate("SELECT * FROM users")
        assert any("SELECT *" in str(i) for i in issues)

    def test_dialect_mysql_func_in_dm(self):
        v = SQLValidator(DialectType.DM)
        is_valid, issues = v.validate("SELECT IFNULL(name, 'x') FROM users")
        assert any("IFNULL" in str(i) for i in issues)

    def test_injection_detection(self):
        v = SQLValidator(DialectType.MYSQL)
        is_valid, issues = v.validate("SELECT * FROM users; DROP TABLE users")
        assert any("dangerous" in str(i).lower() for i in issues)


class TestSQLAutoFixer:
    def test_fix_trailing_semicolon(self):
        fixer = SQLAutoFixer(DialectType.MYSQL)
        fixed, changes = fixer.fix("SELECT id FROM users;")
        assert "semicolon" in str(changes).lower()

    def test_fix_dialect_functions(self):
        fixer = SQLAutoFixer(DialectType.DM)
        fixed, changes = fixer.fix("SELECT IFNULL(name, 'x') FROM users")
        assert "NVL" in fixed

    def test_fix_parentheses(self):
        fixer = SQLAutoFixer(DialectType.MYSQL)
        fixed, changes = fixer.fix("SELECT id FROM users WHERE (age > 18")
        assert fixed.count("(") == fixed.count(")")


class TestValidateAndFix:
    def test_valid_sql(self):
        result = validate_and_fix("SELECT id FROM users", DialectType.MYSQL)
        assert result["is_valid"]
        assert result["retry_count"] == 0

    def test_auto_fix(self):
        result = validate_and_fix("SELECT IFNULL(name, 'x') FROM users", DialectType.DM)
        assert "NVL" in result["fixed_sql"]

    def test_preserves_original(self):
        original = "SELECT id FROM users"
        result = validate_and_fix(original, DialectType.MYSQL)
        assert result["original_sql"] == original


class TestDBConnector:
    def test_execute_multiple_statements_with_semicolon_in_string(self):
        db = DBConnector(DBConfig(db_type="sqlite", name=":memory:"))
        try:
            rows, columns, affected = db.execute(
                """
                CREATE TABLE note (id INTEGER PRIMARY KEY, content TEXT);
                INSERT INTO note (id, content) VALUES (1, 'a;b');
                SELECT content FROM note WHERE id = 1;
                """
            )
            assert columns == ["content"]
            assert rows == [{"content": "a;b"}]
            assert affected == 1
        finally:
            db.close()


class TestWebTemplate:
    def test_session_list_script_uses_safe_event_binding(self):
        from ai_sql_agent.web import HTML_TEMPLATE

        assert "loadSession(\\'\" + s.id" not in HTML_TEMPLATE
        assert "deleteSession(\\'\" + s.id" not in HTML_TEMPLATE
        assert "addEventListener('click'" in HTML_TEMPLATE
