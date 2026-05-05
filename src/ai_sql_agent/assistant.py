"""Core multi-model SQL assistant."""

import json
import logging
from typing import Any, Dict, List, Optional

from .config import AgentConfig, DBConfig, ModelProvider, build_provider
from .db.connector import DBConnector
from .db.dialects import DialectType
from .models.base import Message
from .models.providers import create_model
from .prompts.templates import (
    AGENT_TASK_DECOMPOSE_PROMPT,
    ANALYZE_RESULT_PROMPT,
    EXPLAIN_SQL_PROMPT,
    NL_TO_SQL_PROMPT,
    OPTIMIZE_SQL_PROMPT,
    SCHEMA_ANALYSIS_PROMPT,
    SYSTEM_PROMPT,
    MULTI_TURN_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class SQLAssistant:
    """Multi-model SQL assistant with NL→SQL, explain, optimize, and analysis."""

    def __init__(
        self,
        provider_name: str = "openai",
        provider: Optional[ModelProvider] = None,
        db_config: Optional[DBConfig] = None,
        dialect: DialectType = DialectType.STANDARD,
        agent_config: Optional[AgentConfig] = None,
    ):
        self.dialect = dialect
        self.agent_config = agent_config or AgentConfig()
        # Build model
        if provider:
            self._provider_config = provider
        else:
            self._provider_config = build_provider(provider_name)
        self._model = create_model(
            provider_name,
            api_key=self._provider_config.api_key,
            base_url=self._provider_config.base_url,
            model=self._provider_config.model,
            max_tokens=self._provider_config.max_tokens,
            temperature=self._provider_config.temperature,
        )
        self._model.validate()
        # Database
        self._db: Optional[DBConnector] = None
        if db_config and db_config.is_configured:
            self._db = DBConnector(db_config)

    def _chat(self, messages: List[Message], **kwargs) -> str:
        return self._model.chat(messages, **kwargs)

    def _system_msg(self, content: str) -> Message:
        return Message("system", content)

    def _user_msg(self, content: str) -> Message:
        return Message("user", content)

    def _schema_context(self, tables: Optional[List[str]] = None) -> str:
        if not self._db:
            return ""
        return self._db.get_schema_context(tables)

    def _parse_json(self, text: str) -> Dict:
        """Parse JSON from LLM response, handling markdown code blocks."""
        content = text.strip()
        if content.startswith("```"):
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    try:
                        return json.loads(part)
                    except json.JSONDecodeError:
                        continue
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw": content}

    # --- Core capabilities ---

    def generate_sql(self, query: str, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Natural language → SQL."""
        prompt = NL_TO_SQL_PROMPT.format(
            dialect=self.dialect.value,
            schema_context=self._schema_context(tables),
            query=query,
        )
        result = self._chat([self._system_msg(SYSTEM_PROMPT), self._user_msg(prompt)])
        parsed = self._parse_json(result)
        parsed.setdefault("sql", result)
        parsed.setdefault("explanation", "")
        return parsed

    def explain_sql(self, sql: str) -> str:
        """Explain a SQL query in plain language."""
        prompt = EXPLAIN_SQL_PROMPT.format(dialect=self.dialect.value, sql=sql)
        return self._chat([self._system_msg(SYSTEM_PROMPT), self._user_msg(prompt)])

    def optimize_sql(self, sql: str) -> Dict[str, Any]:
        """Analyze and optimize a SQL query."""
        prompt = OPTIMIZE_SQL_PROMPT.format(dialect=self.dialect.value, sql=sql)
        result = self._chat([self._system_msg(SYSTEM_PROMPT), self._user_msg(prompt)])
        parsed = self._parse_json(result)
        parsed.setdefault("issues", [])
        parsed.setdefault("optimized_sql", "")
        parsed.setdefault("changes", [])
        return parsed

    def execute_sql(self, sql: str, params: Optional[tuple] = None) -> Dict[str, Any]:
        """Execute SQL and return results."""
        if not self._db:
            return {"error": "Database not configured. Set DB_* environment variables."}
        try:
            rows, columns = self._db.execute(sql, params)
            return {"rows": rows, "columns": columns, "row_count": len(rows)}
        except Exception as e:
            return {"error": str(e), "sql": sql}

    def analyze_result(self, query: str, rows: List[Dict], row_count: int) -> str:
        """Analyze query results and provide insights."""
        import json as _json
        preview = _json.dumps(rows[:10], ensure_ascii=False, default=str)
        prompt = ANALYZE_RESULT_PROMPT.format(
            query=query, dialect=self.dialect.value,
            row_count=row_count, result_preview=preview,
        )
        return self._chat([self._system_msg(SYSTEM_PROMPT), self._user_msg(prompt)])

    def analyze_schema(self, schema_ddl: str) -> str:
        """Analyze database schema."""
        prompt = SCHEMA_ANALYSIS_PROMPT.format(dialect=self.dialect.value, schema=schema_ddl)
        return self._chat([self._system_msg(SYSTEM_PROMPT), self._user_msg(prompt)])

    def chat(self, message: str, history: Optional[List[Dict]] = None) -> str:
        """Free-form conversation."""
        messages = [self._system_msg(SYSTEM_PROMPT)]
        if history:
            for h in history:
                messages.append(Message(h["role"], h["content"]))
        messages.append(self._user_msg(message))
        return self._chat(messages, temperature=0.5)

    def chat_multi_turn(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
        schema_context: str = "",
    ) -> str:
        """
        Multi-turn conversation with schema awareness.

        Args:
            message: User message
            history: Conversation history [{"role": "user"|"assistant", "content": "..."}]
            schema_context: Database schema context for better SQL generation
        """
        ctx = schema_context or ""
        sys_prompt = MULTI_TURN_SYSTEM_PROMPT.format(
            dialect=self.dialect.value,
            schema_context=ctx,
        )
        messages = [self._system_msg(sys_prompt)]
        if history:
            for h in history[-10:]:  # Keep last 10 turns
                messages.append(Message(h["role"], h["content"]))
        messages.append(self._user_msg(message))
        return self._chat(messages, temperature=0.3)

    def close(self):
        if self._db:
            self._db.close()
