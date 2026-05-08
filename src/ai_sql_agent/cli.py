"""CLI interface for AI SQL Agent."""

import json
import sys

# Fix Windows encoding
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .agent import SQLAgent
from .assistant import SQLAssistant
from .config import DBConfig, build_provider
from .db.dialects import DialectType
from .utils.formatter import format_sql

console = Console()

DIALECT_CHOICES = click.Choice(["dm", "mysql", "postgres", "sqlite", "standard"])
PROVIDER_CHOICES = click.Choice([
    # LongCat 系列（默认推荐）
    "longcat", "longcat-flash", "longcat-thinking", "longcat-omni", "longcat-lite",
    # 国际主流
    "openai", "claude", "grok",
    # 国产主流
    "glm", "mimo", "deepseek", "qwen",
    "kimi", "doubao", "yuanbao",
    # 通用中转站
    "openai-proxy", "claude-proxy",
])


def _get_dialect(dialect_str: str) -> DialectType:
    return {
        "dm": DialectType.DM, "mysql": DialectType.MYSQL,
        "postgres": DialectType.POSTGRES, "sqlite": DialectType.SQLITE,
        "standard": DialectType.STANDARD,
    }.get(dialect_str, DialectType.STANDARD)


@click.group()
@click.option("--provider", "-p", type=PROVIDER_CHOICES, default="openai",
              envvar="AI_DEFAULT_PROVIDER", help="LLM provider")
@click.option("--dialect", "-d", type=DIALECT_CHOICES, default="standard",
              help="Target SQL dialect")
@click.pass_context
def cli(ctx, provider, dialect):
    """AI SQL Agent — Multi-model SQL Agent powered by GPT/GLM/Claude/MiMo."""
    ctx.ensure_object(dict)
    ctx.obj["provider_name"] = provider
    ctx.obj["dialect"] = _get_dialect(dialect)
    ctx.obj["db_config"] = DBConfig()


@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--tables", "-t", multiple=True, help="Tables for schema context")
@click.pass_context
def ask(ctx, query, tables):
    """Convert natural language to SQL.

    \b
    Examples:
      ai-sql ask "查询每个部门的员工数量"
      ai-sql -d dm ask "最近30天的订单统计"
    """
    query_text = " ".join(query)
    assistant = SQLAssistant(
        provider_name=ctx.obj["provider_name"],
        db_config=ctx.obj["db_config"],
        dialect=ctx.obj["dialect"],
    )
    with console.status("[bold green]Generating SQL..."):
        result = assistant.generate_sql(query_text, list(tables) or None)
    if result.get("sql"):
        sql = format_sql(result["sql"])
        console.print(Panel(
            Syntax(sql, "sql", theme="monokai", line_numbers=True),
            title="[bold cyan]Generated SQL[/]", border_style="cyan",
        ))
    if result.get("explanation"):
        console.print(Panel(
            Markdown(result["explanation"]),
            title="[bold yellow]Explanation[/]", border_style="yellow",
        ))


@cli.command()
@click.argument("sql", nargs=-1, required=True)
@click.pass_context
def explain(ctx, sql):
    """Explain a SQL query.

    \b
    Example:
      ai-sql explain "SELECT * FROM users WHERE age > 18"
    """
    sql_text = " ".join(sql)
    assistant = SQLAssistant(
        provider_name=ctx.obj["provider_name"],
        dialect=ctx.obj["dialect"],
    )
    with console.status("[bold green]Analyzing..."):
        result = assistant.explain_sql(sql_text)
    console.print(Panel(Markdown(result), title="[bold cyan]Explanation[/]", border_style="cyan"))


@cli.command()
@click.argument("sql", nargs=-1, required=True)
@click.pass_context
def optimize(ctx, sql):
    """Optimize a SQL query.

    \b
    Example:
      ai-sql optimize "SELECT * FROM orders WHERE status = 1"
    """
    sql_text = " ".join(sql)
    assistant = SQLAssistant(
        provider_name=ctx.obj["provider_name"],
        dialect=ctx.obj["dialect"],
    )
    with console.status("[bold green]Optimizing..."):
        result = assistant.optimize_sql(sql_text)
    if result.get("issues"):
        console.print(Panel(
            "\n".join(f"- {i}" for i in result["issues"]),
            title="[bold red]Issues Found[/]", border_style="red",
        ))
    if result.get("optimized_sql"):
        sql = format_sql(result["optimized_sql"])
        console.print(Panel(
            Syntax(sql, "sql", theme="monokai", line_numbers=True),
            title="[bold green]Optimized SQL[/]", border_style="green",
        ))
    if result.get("changes"):
        for c in result["changes"]:
            console.print(f"  [bold]{c.get('type', '').upper()}[/]: {c.get('what', c.get('description', ''))}")
            if c.get("why"):
                console.print(f"  [dim]Reason: {c['why']}[/dim]")


@cli.command()
@click.argument("task", nargs=-1, required=True)
@click.option("--tables", "-t", multiple=True, help="Tables for schema context")
@click.option("--no-execute", is_flag=True, help="Do not auto-execute SQL")
@click.pass_context
def agent(ctx, task, tables, no_execute):
    """Run agent workflow: decompose → generate → execute → analyze.

    \b
    Examples:
      ai-sql agent "分析上个月的销售趋势并找出Top10客户"
      ai-sql agent -d dm "优化慢查询并给出索引建议"
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.rule import Rule

    task_text = " ".join(task)
    ag = SQLAgent(
        provider_name=ctx.obj["provider_name"],
        db_config=ctx.obj["db_config"],
        dialect=ctx.obj["dialect"],
    )

    # Step 1: Show task understanding (with spinner while waiting)
    with Progress(
        SpinnerColumn(), TextColumn("[bold green]{task.description}"),
        console=console, transient=False,
    ) as progress:
        progress.add_task("Agent 正在理解任务...", total=None)
        plan = ag._decompose_task(task_text, list(tables) or None)

    understanding = plan.get("understanding", "")
    if understanding:
        console.print(Panel(
            Markdown(understanding),
            title="[bold blue]🧠 任务理解 (CoT)[/]", border_style="blue",
        ))

    # Show sub-tasks
    sub_tasks = plan.get("sub_tasks", [])
    if not sub_tasks:
        sub_tasks = [
            {"id": 1, "tool": "generate_sql", "input": task_text, "purpose": "generate SQL"},
            {"id": 2, "tool": "final_answer", "input": "Summarize", "purpose": "final output"},
        ]

    table = Table(title="📋 子任务列表", show_header=True)
    table.add_column("ID", style="cyan", width=4)
    table.add_column("工具调用", style="yellow", width=18)
    table.add_column("目的")
    for st in sub_tasks:
        table.add_row(str(st.get("id", "")), st.get("tool", ""), st.get("purpose", ""))
    console.print(table)
    console.print()

    # Step 2: Execute sub-tasks one by one, showing progress in real-time
    results = []
    last_sql = ""
    last_execution_result = None

    for idx, st in enumerate(sub_tasks[:ag.config.max_sub_tasks]):
        tool_name = st.get("tool", "final_answer")
        tool_input = st.get("input", "")
        purpose = st.get("purpose", "")

        console.print(Rule(f"[bold gold1]▶ 步骤 {idx + 1}/{len(sub_tasks)}: {tool_name} — {purpose}[/]", style="gold1"))

        with Progress(
            SpinnerColumn(), TextColumn("[bold green]{task.description}"),
            console=console, transient=False,
        ) as progress:
            progress.add_task(f"调用 {tool_name} 中...", total=None)

            if tool_name == "generate_sql" and not no_execute and ag.assistant._db:
                gen_result = ag._tool_generate_sql(tool_input, tables=list(tables) or None)
                results.append({"tool": "generate_sql", "result": gen_result})
                sql = gen_result.get("sql", "")

                if sql:
                    console.print(Panel(
                        Syntax(format_sql(sql), "sql", theme="monokai", line_numbers=True),
                        title="[bold cyan]💻 生成的 SQL[/]", border_style="cyan",
                    ))
                    last_sql = sql

                    if gen_result.get("auto_fixed"):
                        console.print(f"  [bold orange]🔧 自动修复: {', '.join(gen_result.get('fix_changes', []))}[/]")

                    # Auto-execute
                    progress.add_task("执行 SQL 中...", total=None)
                    exec_result = ag._tool_execute_sql(sql)
                    last_execution_result = exec_result
                    results.append({"tool": "execute_sql", "result": exec_result})

                    if exec_result.get("rows"):
                        _print_result_table(console, exec_result)
                    if exec_result.get("error"):
                        console.print(f"[red]❌ 执行错误: {exec_result['error']}[/red]")

                    # Auto-analyze
                    if exec_result.get("rows"):
                        progress.add_task("AI 分析结果中...", total=None)
                        analysis = ag._tool_analyze_result(
                            task_text, exec_result["rows"], exec_result["row_count"]
                        )
                        results.append({"tool": "analyze_result", "result": analysis})
                        console.print(Panel(
                            Markdown(analysis),
                            title="[bold green]📊 分析结论[/]", border_style="green",
                        ))

            elif tool_name == "generate_sql":
                gen_result = ag._tool_generate_sql(tool_input, tables=list(tables) or None)
                results.append({"tool": "generate_sql", "result": gen_result})
                if gen_result.get("sql"):
                    console.print(Panel(
                        Syntax(format_sql(gen_result["sql"]), "sql", theme="monokai", line_numbers=True),
                        title="[bold cyan]💻 生成的 SQL[/]", border_style="cyan",
                    ))

            elif tool_name == "execute_sql":
                sql_to_run = ag._resolve_sql(tool_input, last_sql)
                exec_result = ag._tool_execute_sql(sql_to_run)
                last_execution_result = exec_result
                results.append({"tool": "execute_sql", "result": exec_result})
                if exec_result.get("rows"):
                    _print_result_table(console, exec_result)
                if exec_result.get("error"):
                    console.print(f"[red]❌ 执行错误: {exec_result['error']}[/red]")

            elif tool_name == "validate_sql":
                sql_to_val = ag._resolve_sql(tool_input, last_sql)
                validation = ag._tool_validate_sql(sql_to_val)
                results.append({"tool": "validate_sql", "result": validation})
                status = "✅ 通过" if validation.get("is_valid") else "❌ 有问题"
                console.print(f"  校验结果: {status}")
                if validation.get("issues"):
                    for issue in validation["issues"]:
                        console.print(f"    [yellow]- {issue}[/]")

            elif tool_name == "fix_sql":
                sql_to_fix = ag._resolve_sql(tool_input, last_sql)
                fix_result = ag._tool_fix_sql(sql_to_fix, st.get("error_message", ""))
                results.append({"tool": "fix_sql", "result": fix_result})
                if fix_result.get("changes"):
                    console.print(f"  [orange]修复: {', '.join(fix_result['changes'])}[/]")

            elif tool_name == "explain_sql":
                sql_to_exp = ag._resolve_sql(tool_input, last_sql)
                explanation = ag._tool_explain_sql(sql_to_exp)
                results.append({"tool": "explain_sql", "result": explanation})
                console.print(Panel(Markdown(explanation), title="[bold cyan]📖 SQL 解释[/]", border_style="cyan"))

            elif tool_name == "optimize_sql":
                sql_to_opt = ag._resolve_sql(tool_input, last_sql)
                opt_result = ag._tool_optimize_sql(sql_to_opt)
                results.append({"tool": "optimize_sql", "result": opt_result})
                if opt_result.get("issues"):
                    console.print(Panel(
                        "\n".join(f"- {i}" for i in opt_result["issues"]),
                        title="[bold red]发现的问题[/]", border_style="red",
                    ))
                if opt_result.get("optimized_sql"):
                    console.print(Panel(
                        Syntax(format_sql(opt_result["optimized_sql"]), "sql", theme="monokai", line_numbers=True),
                        title="[bold green]优化后的 SQL[/]", border_style="green",
                    ))

            elif tool_name == "analyze_result" and last_execution_result and last_execution_result.get("rows"):
                analysis = ag._tool_analyze_result(
                    task_text, last_execution_result["rows"], last_execution_result["row_count"]
                )
                results.append({"tool": "analyze_result", "result": analysis})
                console.print(Panel(
                    Markdown(analysis),
                    title="[bold green]📊 分析结论[/]", border_style="green",
                ))

            elif tool_name == "final_answer":
                summary = ag._synthesize(task_text, results)
                results.append({"tool": "final_answer", "result": summary})
                console.print(Panel(
                    Markdown(summary),
                    title="[bold gold1]📝 综合报告[/]", border_style="gold1",
                ))

        ag._tool_results.append(results[-1])
        console.print()

    ag._history.append({"role": "user", "content": task_text})
    ag._history = ag._history[-20:]

    ag.close()


def _print_result_table(console, exec_result):
    """Helper to print query result as Rich table."""
    from rich.table import Table
    columns = exec_result["columns"]
    rows = exec_result["rows"]
    table = Table(show_header=True, header_style="bold", border_style="green")
    for col in columns:
        table.add_column(col, style="cyan", max_width=30)
    for row in rows[:50]:
        table.add_row(*[str(row.get(c, "")) for c in columns])
    console.print(table)
    console.print(f"[green]共 {len(rows)} 行结果[/]")


@cli.command()
@click.pass_context
def interactive(ctx):
    """Start interactive SQL Agent session."""
    console.print("[bold cyan]AI SQL Agent — Interactive Mode[/]")
    console.print("[dim]Commands: 'exit' to quit, 'dialect <name>' to switch, 'provider <name>' to change model[/dim]\n")

    provider_name = ctx.obj["provider_name"]
    dialect = ctx.obj["dialect"]
    db_config = ctx.obj["db_config"]

    assistant = SQLAssistant(
        provider_name=provider_name,
        db_config=db_config,
        dialect=dialect,
    )
    history = []

    while True:
        try:
            user_input = console.input("[bold green]sql-agent> [/]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/dim]")
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            console.print("[dim]Bye![/dim]")
            break
        if user_input.lower().startswith("dialect "):
            d = user_input.split(" ", 1)[1].strip()
            dialect = _get_dialect(d)
            assistant.dialect = dialect
            console.print(f"[dim]Dialect → {d}[/dim]")
            continue
        if user_input.lower().startswith("provider "):
            p = user_input.split(" ", 1)[1].strip()
            provider_name = p
            assistant = SQLAssistant(provider_name=p, db_config=db_config, dialect=dialect)
            console.print(f"[dim]Provider → {p}[/dim]")
            continue

        with console.status("[bold green]Thinking..."):
            response = assistant.chat(user_input, history)
        console.print(Panel(Markdown(response), border_style="blue"))
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})
        if len(history) > 20:
            history = history[-20:]

    assistant.close()


@cli.command()
@click.option("--host", default="127.0.0.1", help="监听地址")
@click.option("--port", "-p", default=8080, help="监听端口")
def web(host, port):
    """启动 Web UI 界面（内置示例数据库）"""
    from .web import start_web
    start_web(host=host, port=port)


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
