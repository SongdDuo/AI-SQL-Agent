"""Tests for AI SQL Agent."""

import pytest
from unittest.mock import MagicMock, patch

from ai_sql_agent.config import AgentConfig, DBConfig, ModelProvider, build_provider
from ai_sql_agent.db.dialects import Dialect, DialectType, convert_to_dm
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

    def test_build_provider_mimo(self):
        p = build_provider("mimo")
        assert p.name == "mimo"
        assert "xiaomimimo" in p.base_url

    def test_db_config_is_configured(self):
        c = DBConfig()
        assert not c.is_configured

    def test_db_config_configured(self):
        c = DBConfig(db_type="dm", name="test")
        assert c.is_configured


class TestFormatter:
    def test_format_basic(self):
        sql = "SELECT id FROM users WHERE age > 18"
        result = format_sql(sql)
        assert "SELECT" in result
        assert "FROM" in result
