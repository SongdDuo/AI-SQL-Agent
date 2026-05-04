"""Agent workflow — automatic task decomposition and execution."""

import json
import logging
from typing import Any, Dict, List, Optional

from .assistant import SQLAssistant
from .config import AgentConfig, DBConfig, ModelProvider, build_provider
from .db.dialects import DialectType
from .models.base import Message
from .prompts.templates import AGENT_TASK_DECOMPOSE_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class SQLAgent:
    """
    AI SQL Agent with automatic task decomposition.

    Workflow:
        User task → Decompose → Execute sub-tasks → Synthesize → Report
    """

    def __init__(
        self,
        provider_name: str = "openai",
        provider: Optional[ModelProvider] = None,
        db_config: Optional[DBConfig] = None,
        dialect: DialectType = DialectType.STANDARD,
        agent_config: Optional[AgentConfig] = None,
    ):
        self.assistant = SQLAssistant(
            provider_name=provider_name,
            provider=provider,
            db_config=db_config,
            dialect=dialect,
            agent_config=agent_config,
        )
        self.config = agent_config or AgentConfig()
        self._history: List[Dict] = []

    def _decompose_task(self, task: str, tables: Optional[List[str]] = None) -> Dict:
        """Decompose a complex task into sub-tasks."""
        schema_ctx = self.assistant._schema_context(tables)
        prompt = AGENT_TASK_DECOMPOSE_PROMPT.format(
            dialect=self.assistant.dialect.value,
            schema_context=schema_ctx,
            task=task,
        )
        result = self.assistant._chat([
            Message("system", SYSTEM_PROMPT),
            Message("user", prompt),
        ])
        try:
            content = result.strip()
            if content.startswith("```"):
                parts = content.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        return json.loads(part)
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            return {"understanding": task, "sub_tasks": [{"id": 1, "tool": "chat", "input": task, "purpose": "direct query"}]}

    def _execute_sub_task(self, sub_task: Dict) -> Dict[str, Any]:
        """Execute a single sub-task using the appropriate tool."""
        tool = sub_task.get("tool", "chat")
        input_data = sub_task.get("input", "")

        if tool == "generate_sql":
            return {"tool": tool, "result": self.assistant.generate_sql(input_data)}
        elif tool == "execute_sql":
            return {"tool": tool, "result": self.assistant.execute_sql(input_data)}
        elif tool == "explain_sql":
            return {"tool": tool, "result": self.assistant.explain_sql(input_data)}
        elif tool == "optimize_sql":
            return {"tool": tool, "result": self.assistant.optimize_sql(input_data)}
        elif tool == "analyze_result":
            # This needs previous execution results — handled in run()
            return {"tool": tool, "result": input_data}
        else:
            return {"tool": "chat", "result": self.assistant.chat(input_data, self._history)}

    def run(self, task: str, tables: Optional[List[str]] = None, auto_execute: bool = True) -> Dict[str, Any]:
        """
        Run a complete agent workflow.

        Args:
            task: Natural language task description
            tables: Optional table list for schema context
            auto_execute: Whether to auto-execute generated SQL

        Returns:
            Complete workflow result with all sub-task outputs
        """
        logger.info(f"Agent received task: {task}")

        # Step 1: Decompose
        plan = self._decompose_task(task, tables)
        sub_tasks = plan.get("sub_tasks", [])

        if not sub_tasks:
            sub_tasks = [{"id": 1, "tool": "generate_sql", "input": task, "purpose": "generate SQL directly"}]

        logger.info(f"Decomposed into {len(sub_tasks)} sub-tasks")

        # Step 2: Execute sub-tasks
        results = []
        last_sql = ""
        last_execution_result = None

        for st in sub_tasks[:self.config.max_sub_tasks]:
            # If auto_execute and we generated SQL, also execute it
            if st.get("tool") == "generate_sql" and auto_execute and self.assistant._db:
                gen_result = self._execute_sub_task(st)
                results.append(gen_result)
                sql = gen_result.get("result", {}).get("sql", "")
                if sql:
                    last_sql = sql
                    exec_result = self.assistant.execute_sql(sql)
                    last_execution_result = exec_result
                    results.append({"tool": "execute_sql", "result": exec_result})
                    # Auto-analyze if we have results
                    if exec_result.get("rows"):
                        analysis = self.assistant.analyze_result(
                            task, exec_result["rows"], exec_result["row_count"]
                        )
                        results.append({"tool": "analyze_result", "result": analysis})
            elif st.get("tool") == "analyze_result" and last_execution_result and last_execution_result.get("rows"):
                analysis = self.assistant.analyze_result(
                    task, last_execution_result["rows"], last_execution_result["row_count"]
                )
                results.append({"tool": "analyze_result", "result": analysis})
            else:
                results.append(self._execute_sub_task(st))

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
            elif isinstance(result, str):
                summary_parts.append(result)
        return "\n\n".join(summary_parts) if summary_parts else "No results"

    def close(self):
        self.assistant.close()
