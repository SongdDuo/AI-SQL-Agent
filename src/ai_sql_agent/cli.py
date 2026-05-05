"""CLI interface for AI SQL Agent."""

import json
import sys

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
    "openai", "glm", "mimo", "claude", "deepseek", "qwen",
    "longcat", "longcat-flash", "longcat-thinking", "longcat-omni", "longcat-lite",
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
    task_text = " ".join(task)
    ag = SQLAgent(
        provider_name=ctx.obj["provider_name"],
        db_config=ctx.obj["db_config"],
        dialect=ctx.obj["dialect"],
    )
    with console.status("[bold green]Agent working..."):
        result = ag.run(task_text, list(tables) or None, auto_execute=not no_execute)

    console.print(Panel(
        Markdown(result.get("understanding", "")),
        title="[bold blue]Task Understanding[/]", border_style="blue",
    ))

    # Show sub-tasks
    if result.get("sub_tasks"):
        table = Table(title="Sub-tasks", show_header=True)
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Tool", style="green")
        table.add_column("Purpose")
        for st in result["sub_tasks"]:
            table.add_row(str(st.get("id", "")), st.get("tool", ""), st.get("purpose", ""))
        console.print(table)

    # Show results
    for r in result.get("results", []):
        tool = r.get("tool", "")
        res = r.get("result", "")
        if isinstance(res, dict):
            if res.get("sql"):
                console.print(Panel(
                    Syntax(format_sql(res["sql"]), "sql", theme="monokai", line_numbers=True),
                    title=f"[bold cyan]{tool}[/]", border_style="cyan",
                ))
            if res.get("rows"):
                console.print(f"[green]Executed: {res['row_count']} rows returned[/green]")
            if res.get("error"):
                console.print(f"[red]Error: {res['error']}[/red]")
        elif isinstance(res, str):
            console.print(Panel(Markdown(res), title=f"[bold cyan]{tool}[/]", border_style="cyan"))

    if result.get("summary"):
        console.print(Panel(Markdown(result["summary"]), title="[bold yellow]Summary[/]", border_style="yellow"))


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


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
