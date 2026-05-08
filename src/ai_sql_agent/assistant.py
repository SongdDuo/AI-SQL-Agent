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
        import re as _re
        content = text.strip()

        # 1. Try to extract JSON from ```json ... ``` code blocks first
        code_block_match = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, _re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # 2. Try to find the first {...} block in the text
        brace_match = _re.search(r"\{.*\}", content, _re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        # 3. Try raw content
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
        logger.debug(f"[LLM] generate_sql prompt:\n{prompt}")
        result = self._chat([self._system_msg(SYSTEM_PROMPT), self._user_msg(prompt)])
        logger.debug(f"[LLM] generate_sql response:\n{result}")
        parsed = self._parse_json(result)
        # Only set sql from raw response if "sql" key is missing AND parsed is not the raw fallback
        if "sql" not in parsed:
            if "raw" in parsed:
                # LLM didn't return valid JSON — try to extract SQL from raw text
                parsed["sql"] = self._extract_sql_from_text(parsed["raw"])
            else:
                parsed["sql"] = result
        parsed.setdefault("explanation", "")
        return parsed

    def _extract_sql_from_text(self, text: str) -> str:
        """Try to extract a SQL query from free-form text when JSON parsing fails."""
        import re as _re
        # Look for SELECT/INSERT/UPDATE/DELETE ... ; or end of string
        for keyword in ("SELECT", "INSERT", "UPDATE", "DELETE", "WITH"):
            pattern = _re.compile(rf"({keyword}\b.*?)(?:;|$)", _re.IGNORECASE | _re.DOTALL)
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        # Fallback: return first non-empty line
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped:
                return stripped
        return text

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
            return {"error": "数据库未配置。"}
        try:
            rows, columns, affected = self._db.execute(sql, params)
            return {"rows": rows, "columns": columns, "row_count": len(rows), "affected_rows": affected}
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
