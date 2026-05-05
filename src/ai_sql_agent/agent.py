"""Agent workflow — Tool Calling based SQL Agent with validation and auto-fix."""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from .assistant import SQLAssistant
from .config import AgentConfig, DBConfig, ModelProvider, build_provider
from .db.dialects import DialectType
from .db.validator import validate_and_fix
from .models.base import Message
from .prompts.templates import (
    AGENT_TASK_DECOMPOSE_PROMPT,
    AGENT_TOOL_CALLING_PROMPT,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


# --- Tool definitions ---

class Tool:
    """Agent tool definition."""

    def __init__(self, name: str, description: str, func: Callable):
        self.name = name
        self.description = description
        self.func = func

    def execute(self, **kwargs) -> Dict[str, Any]:
        try:
            result = self.func(**kwargs)
            return {"success": True, "tool": self.name, "result": result}
        except Exception as e:
            logger.warning(f"Tool {self.name} failed: {e}")
            return {"success": False, "tool": self.name, "error": str(e)}


class SQLAgent:
    """
    AI SQL Agent with Tool Calling architecture.

    Workflow:
        User task → Decompose → Tool Call Loop → Validate & Fix → Synthesize → Report

    Tool Calling Loop:
        1. Agent decides which tool to call
        2. Execute tool (generate_sql, execute_sql, etc.)
        3. Validate result
        4. If SQL execution fails → auto-fix and retry
        5. Feed result back to Agent for next decision
    """

    def __init__(
        self,
        provider_name: str = "longcat",
        provider: Optional[ModelProvider] = None,
        db_config: Optional[DBConfig] = None,
        dialect: DialectType = DialectType.STANDARD,
        agent_config: Optional[AgentConfig] = None,
        max_tool_iterations: int = 10,
        max_fix_retries: int = 3,
    ):
        self.assistant = SQLAssistant(
            provider_name=provider_name,
            provider=provider,
            db_config=db_config,
            dialect=dialect,
            agent_config=agent_config,
        )
        self.config = agent_config or AgentConfig()
        self.dialect = dialect
        self.max_tool_iterations = max_tool_iterations
        self.max_fix_retries = max_fix_retries
        self._history: List[Dict] = []
        self._tool_results: List[Dict] = []

        # Register tools
        self._tools: Dict[str, Tool] = {
            "generate_sql": Tool(
                "generate_sql",
                "Convert natural language to SQL query",
                self._tool_generate_sql,
            ),
            "execute_sql": Tool(
                "execute_sql",
                "Execute a SQL query and return results",
                self._tool_execute_sql,
            ),
            "validate_sql": Tool(
                "validate_sql",
                "Validate SQL syntax and semantics",
                self._tool_validate_sql,
            ),
            "fix_sql": Tool(
                "fix_sql",
                "Auto-fix a SQL query based on error message",
                self._tool_fix_sql,
            ),
            "explain_sql": Tool(
                "explain_sql",
                "Explain a SQL query in plain language",
                self._tool_explain_sql,
            ),
            "optimize_sql": Tool(
                "optimize_sql",
                "Optimize a SQL query for better performance",
                self._tool_optimize_sql,
            ),
            "analyze_result": Tool(
                "analyze_result",
                "Analyze query results and provide insights",
                self._tool_analyze_result,
            ),
            "final_answer": Tool(
                "final_answer",
                "Generate the final answer for the user",
                self._tool_final_answer,
            ),
        }

    def _get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for the prompt."""
        lines = []
        for name, tool in self._tools.items():
            lines.append(f"  - {name}: {tool.description}")
        return "\n".join(lines)

    def _build_context(self, task: str, tables: Optional[List[str]] = None) -> str:
        """Build schema + history context."""
        parts = []
        schema_ctx = self.assistant._schema_context(tables)
        if schema_ctx:
            parts.append(schema_ctx)
        if self._history:
            parts.append("\nConversation history:")
            for h in self._history[-10:]:
                parts.append(f"  [{h['role']}]: {h['content'][:200]}")
        if self._tool_results:
            parts.append("\nPrevious tool results:")
            for tr in self._tool_results[-5:]:
                tool_name = tr.get("tool", "unknown")
                result = tr.get("result", tr.get("error", ""))
                if isinstance(result, dict):
                    result_str = json.dumps(result, ensure_ascii=False, default=str)[:300]
                else:
                    result_str = str(result)[:300]
                parts.append(f"  [{tool_name}]: {result_str}")
        return "\n".join(parts)

    # --- Tool implementations ---

    def _tool_generate_sql(self, query: str, **kwargs) -> Dict[str, Any]:
        """Generate SQL from natural language."""
        result = self.assistant.generate_sql(query, kwargs.get("tables"))
        # Auto-validate generated sql
        sql = result.get("sql", "")
        if sql:
            validation = validate_and_fix(sql, self.dialect)
            result["validation"] = validation
            if not validation["is_valid"]:
                result["sql"] = validation["fixed_sql"]
                result["auto_fixed"] = True
                result["fix_changes"] = validation["changes"]
        return result

    def _tool_execute_sql(self, sql: str, **kwargs) -> Dict[str, Any]:
        """Execute SQL with auto-fix on failure."""
        result = self.assistant.execute_sql(sql)
        if result.get("error"):
            # Auto-fix and retry
            fix_result = validate_and_fix(sql, self.dialect, result["error"], self.max_fix_retries)
            if fix_result["changes"] and fix_result["fixed_sql"] != sql:
                logger.info(f"Auto-fixing SQL: {fix_result['changes']}")
                retry = self.assistant.execute_sql(fix_result["fixed_sql"])
                retry["original_sql"] = sql
                retry["fixed_sql"] = fix_result["fixed_sql"]
                retry["fix_changes"] = fix_result["changes"]
                return retry
        return result

    def _tool_validate_sql(self, sql: str, **kwargs) -> Dict[str, Any]:
        """Validate SQL syntax and semantics."""
        return validate_and_fix(sql, self.dialect)

    def _tool_fix_sql(self, sql: str, error_message: str = "", **kwargs) -> Dict[str, Any]:
        """Auto-fix SQL based on error."""
        return validate_and_fix(sql, self.dialect, error_message, self.max_fix_retries)

    def _tool_explain_sql(self, sql: str, **kwargs) -> str:
        """Explain SQL."""
        return self.assistant.explain_sql(sql)

    def _tool_optimize_sql(self, sql: str, **kwargs) -> Dict[str, Any]:
        """Optimize SQL."""
        return self.assistant.optimize_sql(sql)

    def _tool_analyze_result(self, query: str, rows: List[Dict], row_count: int, **kwargs) -> str:
        """Analyze query results."""
        return self.assistant.analyze_result(query, rows, row_count)

    def _tool_final_answer(self, answer: str, **kwargs) -> str:
        """Final answer."""
        return answer

    # --- Agent loop ---

    def _decompose_task(self, task: str, tables: Optional[List[str]] = None) -> Dict:
        """Decompose a complex task into sub-tasks (CoT reasoning)."""
        context = self._build_context(task, tables)
        prompt = AGENT_TOOL_CALLING_PROMPT.format(
            dialect=self.dialect.value,
            schema_context=context,
            tools=self._get_tool_descriptions(),
            task=task,
        )
        result = self.assistant._chat([
            Message("system", SYSTEM_PROMPT),
            Message("user", prompt),
        ])
        return self._parse_json(result)

    def _parse_json(self, text: str) -> Dict:
        """Parse JSON from LLM response."""
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
            return {"action": "final_answer", "answer": content}

    def run(
        self,
        task: str,
        tables: Optional[List[str]] = None,
        auto_execute: bool = True,
    ) -> Dict[str, Any]:
        """
        Run the complete Agent workflow with Tool Calling.

        Args:
            task: Natural language task description
            tables: Optional table list for schema context
            auto_execute: Whether to auto-execute generated SQL

        Returns:
            Complete workflow result
        """
        logger.info(f"Agent received task: {task}")

        # Step 1: Initial decomposition (CoT)
        plan = self._decompose_task(task, tables)
        sub_tasks = plan.get("sub_tasks", [])

        if not sub_tasks:
            sub_tasks = [
                {"id": 1, "tool": "generate_sql", "input": task, "purpose": "generate SQL"},
                {"id": 2, "tool": "final_answer", "input": "Summarize results", "purpose": "final output"},
            ]

        logger.info(f"Decomposed into {len(sub_tasks)} sub-tasks")

        # Step 2: Execute sub-tasks with tool calling loop
        results = []
        last_sql = ""
        last_execution_result = None
        iteration = 0

        for st in sub_tasks[:self.config.max_sub_tasks]:
            if iteration >= self.max_tool_iterations:
                logger.warning("Max tool iterations reached")
                break

            tool_name = st.get("tool", "final_answer")
            tool_input = st.get("input", "")

            # Handle generate_sql with auto-execute
            if tool_name == "generate_sql" and auto_execute and self.assistant._db:
                gen_result = self._tool_generate_sql(tool_input, tables=tables)
                results.append({"tool": "generate_sql", "result": gen_result})

                sql = gen_result.get("sql", "")
                if sql:
                    last_sql = sql
                    exec_result = self._tool_execute_sql(sql)
                    last_execution_result = exec_result
                    results.append({"tool": "execute_sql", "result": exec_result})

                    # Auto-analyze if we have results
                    if exec_result.get("rows"):
                        analysis = self._tool_analyze_result(
                            task, exec_result["rows"], exec_result["row_count"]
                        )
                        results.append({"tool": "analyze_result", "result": analysis})

            elif tool_name == "execute_sql":
                exec_result = self._tool_execute_sql(tool_input)
                last_execution_result = exec_result
                results.append({"tool": "execute_sql", "result": exec_result})

            elif tool_name == "analyze_result" and last_execution_result and last_execution_result.get("rows"):
                analysis = self._tool_analyze_result(
                    task, last_execution_result["rows"], last_execution_result["row_count"]
                )
                results.append({"tool": "analyze_result", "result": analysis})

            elif tool_name == "validate_sql":
                validation = self._tool_validate_sql(tool_input)
                results.append({"tool": "validate_sql", "result": validation})

            elif tool_name == "fix_sql":
                fix_result = self._tool_fix_sql(tool_input, st.get("error_message", ""))
                results.append({"tool": "fix_sql", "result": fix_result})

            elif tool_name == "explain_sql":
                explanation = self._tool_explain_sql(tool_input)
                results.append({"tool": "explain_sql", "result": explanation})

            elif tool_name == "optimize_sql":
                opt_result = self._tool_optimize_sql(tool_input)
                results.append({"tool": "optimize_sql", "result": opt_result})

            elif tool_name == "final_answer":
                summary = self._synthesize(task, results)
                results.append({"tool": "final_answer", "result": summary})

            # Store tool results for context
            self._tool_results.append(results[-1])
            iteration += 1

        # Update history
        self._history.append({"role": "user", "content": task})
        self._history = self._history[-20:]

        return {
            "understanding": plan.get("understanding", ""),
            "sub_tasks": sub_tasks,
            "results": results,
            "summary": self._synthesize(task, results),
        }

    def _synthesize(self, task: str, results: List[Dict]) -> str:
        """Synthesize results into a coherent summary."""
        summary_parts = []
        for r in results:
            tool = r.get("tool", "")
            result = r.get("result", "")
            if isinstance(result, dict):
                if result.get("sql"):
                    summary_parts.append(f"Generated SQL:\n{result['sql']}")
                if result.get("explanation"):
                    summary_parts.append(f"Explanation: {result['explanation']}")
                if result.get("rows"):
                    summary_parts.append(f"Execution returned {result['row_count']} rows")
                if result.get("optimized_sql"):
                    summary_parts.append(f"Optimized SQL:\n{result['optimized_sql']}")
                if result.get("error"):
                    summary_parts.append(f"Error: {result['error']}")
                if result.get("auto_fixed"):
                    summary_parts.append(f"Auto-fixed: {', '.join(result.get('fix_changes', []))}")
            elif isinstance(result, str) and result:
                summary_parts.append(result)
        return "\n\n".join(summary_parts) if summary_parts else "No results"

    def close(self):
        self.assistant.close()
