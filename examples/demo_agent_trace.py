"""
AI SQL Agent — 完整执行过程演示脚本
====================================
运行此脚本可看到 Agent 的每一步 Tool Calling 过程，包括：
  1. 任务理解与拆解（CoT 推理）
  2. SQL 生成
  3. SQL 校验
  4. SQL 执行
  5. 结果分析
  6. 综合报告

使用方法：
  1. 确保已配置 .env 文件（设置 AI_LONGCAT_API_KEY）
  2. 运行: python examples/demo_agent_trace.py
  3. 观察每步输出，适合截图作为案例展示素材

依赖：ai-sql-agent, rich
"""

import json
import logging
import os
import sqlite3
import sys
import tempfile
import warnings
from datetime import datetime

# Suppress harmless trio warning on Windows
warnings.filterwarnings("ignore", category=RuntimeWarning, module="trio")

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table

from ai_sql_agent.agent import SQLAgent
from ai_sql_agent.assistant import SQLAssistant
from ai_sql_agent.config import DBConfig
from ai_sql_agent.db.dialects import DialectType
from ai_sql_agent.utils.formatter import format_sql

console = Console()


# ── 日志记录器 ────────────────────────────────────────────────────────────────

class TraceLogger:
    """记录每次 LLM 调用的输入/输出，实时写入日志文件。"""

    def __init__(self, log_file: str = None):
        self.entries = []
        self.log_file = log_file
        self._fh = None
        if log_file:
            os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
            self._fh = open(log_file, "w", encoding="utf-8")
            self._fh.write(f"# AI SQL Agent — 执行日志\n")
            self._fh.write(f"# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self._fh.write(f"{'=' * 80}\n\n")
            self._fh.flush()

    def log(self, phase: str, direction: str, content: str):
        """记录一次 LLM 交互，实时写入文件。"""
        entry = {
            "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "phase": phase,
            "direction": direction,
            "content": content,
        }
        self.entries.append(entry)
        if self._fh:
            self._fh.write(f"[{entry['time']}] [{phase}] {direction}\n")
            self._fh.write(f"{'─' * 60}\n")
            self._fh.write(content.rstrip())
            self._fh.write(f"\n{'=' * 80}\n\n")
            self._fh.flush()

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None

    def print_entry(self, entry: dict, max_content_len: int = 800):
        """在终端中打印一条 trace 记录（折叠显示）"""
        phase = entry["phase"]
        direction = entry["direction"]
        content = entry["content"]
        if len(content) > max_content_len:
            content = content[:max_content_len] + f"\n  ... (共 {len(entry['content'])} 字符，已截断)"
        icon = "📥" if direction == "input" else "📤"
        color = "blue" if direction == "input" else "green"
        console.print(f"  [{color}]{icon} [{direction}] {phase}[/]")
        for line in content.split("\n")[:20]:
            console.print(f"     [dim]{line}[/]")
        if content.count("\n") > 20:
            console.print(f"     [dim]... (还有 {content.count(chr(10)) - 20} 行)[/]")

    def summary(self, log_file: str = None):
        """打印 trace 摘要，从 log 文件读取"""
        console.print()
        console.rule("[bold white]📋 LLM 调用日志摘要[/]", style="white")
        # 优先从 log 文件读取
        if log_file and os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
            # 按 ==== 分隔符拆分各条记录
            records = [r.strip() for r in content.split("=" * 80) if r.strip()]
            # 过滤掉头部注释
            records = [r for r in records if not r.startswith("#")]
            console.print(f"  共 {len(records)} 条日志记录\n")
            for i, record in enumerate(records):
                lines = record.split("\n")
                # 第一行是时间戳和 logger 名
                header = lines[0] if lines else ""
                # 找内容预览
                content_lines = [l for l in lines[1:] if l.strip() and not l.startswith("─")]
                content_preview = " ".join(content_lines)[:100] if content_lines else header
                console.print(f"  [{i+1:02d}] {content_preview}...")
            console.print()
            console.print(f"  [dim]完整日志见: {log_file}[/]")
        elif self.entries:
            console.print(f"  共 {len(self.entries)} 条记录\n")
            for i, entry in enumerate(self.entries):
                icon = "📥" if entry["direction"] == "input" else "📤"
                color = "blue" if entry["direction"] == "input" else "green"
                content_preview = entry["content"].replace("\n", " ")[:80]
                console.print(f"  [{i+1:02d}] [{color}]{icon} {entry['phase']:20s} {entry['direction']:6s}[/]  {content_preview}...")
        else:
            console.print("  暂无日志记录")


# ── 示例数据库 ────────────────────────────────────────────────────────────────

SAMPLE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS department (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(200),
    budget DECIMAL(15,2)
);
CREATE TABLE IF NOT EXISTS employee (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(200),
    salary DECIMAL(12,2),
    hire_date DATE,
    department_id INTEGER,
    status INTEGER DEFAULT 1,
    FOREIGN KEY (department_id) REFERENCES department(id)
);
CREATE TABLE IF NOT EXISTS customer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(200),
    city VARCHAR(100),
    register_date DATE
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    total_amount DECIMAL(15,2),
    status INTEGER DEFAULT 1,
    create_time DATETIME,
    FOREIGN KEY (customer_id) REFERENCES customer(id)
);
CREATE TABLE IF NOT EXISTS product (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(10,2),
    stock INTEGER DEFAULT 0
);
"""

SAMPLE_DATA_SQL = """
INSERT OR IGNORE INTO department (id, name, location, budget) VALUES
(1, '技术部', '北京', 5000000),
(2, '销售部', '上海', 3000000),
(3, '市场部', '广州', 2000000),
(4, '人事部', '深圳', 1500000),
(5, '财务部', '北京', 1800000);
INSERT OR IGNORE INTO employee (id, name, email, salary, hire_date, department_id, status) VALUES
(1, '张三', 'zhangsan@example.com', 25000, '2022-03-15', 1, 1),
(2, '李四', 'lisi@example.com', 18000, '2023-01-10', 1, 1),
(3, '王五', 'wangwu@example.com', 30000, '2021-06-20', 1, 1),
(4, '赵六', 'zhaoliu@example.com', 15000, '2023-07-01', 2, 1),
(5, '钱七', 'qianqi@example.com', 22000, '2022-09-15', 2, 1),
(6, '孙八', 'sunba@example.com', 16000, '2024-02-20', 3, 1),
(7, '周九', 'zhoujiu@example.com', 28000, '2020-11-05', 1, 1),
(8, '吴十', 'wushi@example.com', 12000, '2024-06-10', 4, 1),
(9, '郑十一', 'zhengshiyi@example.com', 19000, '2023-03-25', 5, 1),
(10, '王十二', 'wangshier@example.com', 35000, '2019-08-12', 1, 1);
INSERT OR IGNORE INTO customer (id, name, email, city, register_date) VALUES
(1, '客户A', 'a@example.com', '北京', '2024-01-15'),
(2, '客户B', 'b@example.com', '上海', '2024-03-20'),
(3, '客户C', 'c@example.com', '广州', '2024-05-10'),
(4, '客户D', 'd@example.com', '深圳', '2024-06-01'),
(5, '客户E', 'e@example.com', '杭州', '2024-08-15');
INSERT OR IGNORE INTO orders (id, customer_id, total_amount, status, create_time) VALUES
(1, 1, 15800, 1, '2025-04-01 10:30:00'),
(2, 2, 23500, 1, '2025-04-05 14:20:00'),
(3, 1, 8900, 1, '2025-04-10 09:15:00'),
(4, 3, 45600, 1, '2025-04-15 16:45:00'),
(5, 4, 12300, 0, '2025-04-18 11:00:00'),
(6, 5, 67800, 1, '2025-04-20 13:30:00'),
(7, 2, 34200, 1, '2025-04-22 10:00:00'),
(8, 3, 19500, 1, '2025-04-25 15:20:00'),
(9, 1, 52100, 1, '2025-04-28 08:45:00'),
(10, 5, 28700, 1, '2025-05-01 12:10:00'),
(11, 4, 41300, 1, '2025-05-03 14:00:00'),
(12, 2, 16800, 1, '2025-05-05 09:30:00');
INSERT OR IGNORE INTO product (id, name, category, price, stock) VALUES
(1, '笔记本电脑', '电子产品', 6999, 120),
(2, '机械键盘', '电子产品', 599, 300),
(3, '显示器', '电子产品', 2499, 80),
(4, '办公椅', '办公用品', 1299, 200),
(5, '打印机', '办公用品', 3599, 45),
(6, '鼠标', '电子产品', 199, 500),
(7, '耳机', '电子产品', 899, 250),
(8, '白板', '办公用品', 399, 150);
"""


def init_sample_db():
    """创建临时示例数据库，返回 DBConfig"""
    tmp = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(tmp)
    conn.executescript(SAMPLE_SCHEMA_SQL)
    conn.executescript(SAMPLE_DATA_SQL)
    conn.commit()
    conn.close()
    db_config = DBConfig(db_type="sqlite", name=tmp)
    db_config._tmp_path = tmp
    return db_config


def print_sql_block(sql: str, dialect: str = "sql"):
    """打印 SQL 代码块"""
    console.print(Panel(
        Syntax(format_sql(sql), dialect, theme="monokai", line_numbers=True),
        title="[bold cyan]SQL[/]", border_style="cyan", padding=(1, 2)
    ))


def print_result_table(columns: list, rows: list, max_rows: int = 20):
    """打印查询结果表格"""
    if not rows:
        console.print("  [dim]查询返回 0 行[/]")
        return
    table = Table(show_header=True, header_style="bold", border_style="green")
    for col in columns:
        table.add_column(col, style="cyan", max_width=30)
    for row in rows[:max_rows]:
        table.add_row(*[str(row.get(c, "")) for c in columns])
    console.print(table)
    console.print(f"  [green]共 {len(rows)} 行结果[/]")


def print_step_header(step_num: str, total: int, tool_name: str, purpose: str = ""):
    """打印步骤分隔线"""
    console.print(Rule(
        f"[bold gold1]▶ 步骤 {step_num}/{total}: {tool_name} — {purpose}[/]",
        style="gold1"
    ))


# ── 主演示流程 ────────────────────────────────────────────────────────────────

def demo_full_agent_workflow():
    """
    演示完整的 Agent 工作流 — 实时逐步输出版本
    - 每调用一个工具就立即显示结果
    - 自动跳过 generate_sql 已执行的重复子任务
    - 记录每次 LLM 调用的输入/输出日志
    """
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "agent_trace.log")

    # 给 agent 和 assistant 的 logger 加文件 handler，实时记录所有 LLM 交互
    _log_handler = logging.FileHandler(log_file, encoding="utf-8", mode="w")
    _log_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s\n%(message)s\n" + "─" * 60
    ))
    _log_handler.setLevel(logging.DEBUG)
    for _logger_name in ("ai_sql_agent.agent", "ai_sql_agent.assistant"):
        _lg = logging.getLogger(_logger_name)
        _lg.setLevel(logging.DEBUG)
        _lg.addHandler(_log_handler)

    # trace 记录器（用于终端摘要展示）
    trace = TraceLogger(log_file=None)

    # ── 初始化 ──
    console.print()
    console.rule("[bold white on dark_green] 🤖 AI SQL Agent — 完整执行过程演示 [/]", style="dark_green")
    console.print()

    console.print(Panel(
        "[bold]模型:[/] LongCat-2.0-Preview  "
        "[bold]方言:[/] SQLite  "
        "[bold]数据库[/]: 示例数据库 (5张表, 约40条记录)",
        title="[bold]📋 演示配置[/]", border_style="blue"
    ))

    db_config = init_sample_db()

    try:
        # ═══════════════════════════════════════════════════════════════════
        # 演示 1: 简单聚合查询
        # ═══════════════════════════════════════════════════════════════════
        console.print()
        console.rule("[bold white] 演示 1: 简单聚合查询 [/]", style="white")
        task1 = "查询每个部门的平均工资，只显示平均工资大于18000的部门"
        console.print(f"\n  [bold]📝 用户输入:[/] [italic]{task1}[/]\n")

        agent = SQLAgent(provider_name="longcat", db_config=db_config, dialect=DialectType.SQLITE)

        # Step 1: CoT 拆解
        with Progress(SpinnerColumn(), TextColumn("[bold green]{task.description}"), console=console, transient=False) as progress:
            progress.add_task("🧠 Agent 正在理解任务...", total=None)
            plan = agent._decompose_task(task1)

        sub_tasks = plan.get("sub_tasks", [])
        if not sub_tasks:
            sub_tasks = [
                {"id": 1, "tool": "generate_sql", "input": task1, "purpose": "生成 SQL"},
                {"id": 2, "tool": "final_answer", "input": "汇总结果", "purpose": "生成报告"},
            ]

        # 显示理解
        if plan.get("understanding"):
            console.print(Panel(plan["understanding"], title="[bold blue]🧠 任务理解 (CoT)[/]", border_style="blue"))

        # 显示子任务列表
        console.print()
        table = Table(title="📋 子任务列表", show_header=True, header_style="bold", border_style="gold1")
        table.add_column("ID", style="cyan", width=4, justify="center")
        table.add_column("工具调用", style="yellow", width=18)
        table.add_column("目的")
        for st in sub_tasks:
            table.add_row(str(st.get("id", "")), st.get("tool", ""), st.get("purpose", ""))
        console.print(table)
        console.print()

        # 逐步执行子任务
        results = []
        last_sql = ""
        last_exec_result = None
        # 追踪 generate_sql 已自动执行的工具，避免重复
        auto_executed = set()
        total = len(sub_tasks[:agent.config.max_sub_tasks])

        for idx, st in enumerate(sub_tasks[:agent.config.max_sub_tasks]):
            tool_name = st.get("tool", "final_answer")
            tool_input = st.get("input", "")
            purpose = st.get("purpose", "")

            print_step_header(idx + 1, total, tool_name, purpose)

            with Progress(SpinnerColumn(), TextColumn("[bold green]{task.description}"), console=console, transient=False) as progress:
                progress.add_task(f"调用 {tool_name} 中...", total=None)

                if tool_name == "generate_sql":
                    gen_result = agent._tool_generate_sql(tool_input)
                    results.append({"tool": "generate_sql", "result": gen_result})
                    last_sql = gen_result.get("sql", "")

                    if last_sql:
                        print_sql_block(last_sql)
                    if gen_result.get("explanation"):
                        console.print(Panel(gen_result["explanation"], title="[bold yellow]💡 SQL 解释[/]", border_style="yellow"))
                    if gen_result.get("auto_fixed"):
                        console.print(f"  [bold orange]🔧 自动修复: {', '.join(gen_result.get('fix_changes', []))}[/]")

                    # 自动生成后自动执行 + 分析
                    if last_sql and agent.assistant._db:
                        progress.add_task("🗄️ 执行 SQL 中...", total=None)
                        exec_result = agent._tool_execute_sql(last_sql)
                        last_exec_result = exec_result
                        results.append({"tool": "execute_sql", "result": exec_result})
                        auto_executed.add("execute_sql")

                        if exec_result.get("rows"):
                            print_result_table(exec_result["columns"], exec_result["rows"])
                        if exec_result.get("error"):
                            console.print(f"[red]❌ 执行错误: {exec_result['error']}[/red]")

                        if exec_result.get("rows"):
                            progress.add_task("📊 AI 分析中...", total=None)
                            analysis = agent._tool_analyze_result(task1, exec_result["rows"], exec_result["row_count"])
                            results.append({"tool": "analyze_result", "result": analysis})
                            auto_executed.add("analyze_result")
                            console.print(Panel(analysis, title="[bold green]📊 分析结论[/]", border_style="green"))

                elif tool_name == "execute_sql":
                    # 如果 generate_sql 已自动执行过，跳过重复
                    if "execute_sql" in auto_executed:
                        console.print("  [dim]⏭️  generate_sql 已自动执行，跳过重复步骤[/]")
                        if last_exec_result:
                            if last_exec_result.get("rows"):
                                print_result_table(last_exec_result["columns"], last_exec_result["rows"])
                            if last_exec_result.get("error"):
                                console.print(f"[red]❌ 执行错误: {last_exec_result['error']}[/red]")
                        continue
                    sql_to_run = agent._resolve_sql(tool_input, last_sql)
                    exec_result = agent._tool_execute_sql(sql_to_run)
                    last_exec_result = exec_result
                    results.append({"tool": "execute_sql", "result": exec_result})
                    if exec_result.get("rows"):
                        print_result_table(exec_result["columns"], exec_result["rows"])
                    if exec_result.get("error"):
                        console.print(f"[red]❌ 执行错误: {exec_result['error']}[/red]")

                elif tool_name == "analyze_result":
                    # 如果 generate_sql 已自动分析过，跳过重复
                    if "analyze_result" in auto_executed:
                        console.print("  [dim]⏭️  generate_sql 已自动分析，跳过重复步骤[/]")
                        # 显示上一次的分析结论
                        for prev_r in reversed(results):
                            if prev_r.get("tool") == "analyze_result" and isinstance(prev_r.get("result"), str):
                                console.print(Panel(prev_r["result"], title="[bold green]📊 分析结论[/]", border_style="green"))
                                break
                        continue
                    if last_exec_result and last_exec_result.get("rows"):
                        analysis = agent._tool_analyze_result(task1, last_exec_result["rows"], last_exec_result["row_count"])
                        results.append({"tool": "analyze_result", "result": analysis})
                        console.print(Panel(analysis, title="[bold green]📊 分析结论[/]", border_style="green"))

                elif tool_name == "validate_sql":
                    sql_to_val = agent._resolve_sql(tool_input, last_sql)
                    validation = agent._tool_validate_sql(sql_to_val)
                    results.append({"tool": "validate_sql", "result": validation})
                    status = "✅ 通过" if validation.get("is_valid") else "❌ 有问题"
                    console.print(f"  校验结果: {status}")
                    if validation.get("issues"):
                        for issue in validation["issues"]:
                            console.print(f"    [yellow]- {issue}[/]")

                elif tool_name == "fix_sql":
                    sql_to_fix = agent._resolve_sql(tool_input, last_sql)
                    fix_result = agent._tool_fix_sql(sql_to_fix, st.get("error_message", ""))
                    results.append({"tool": "fix_sql", "result": fix_result})
                    if fix_result.get("changes"):
                        console.print(f"  [orange]🔧 修复: {', '.join(fix_result['changes'])}[/]")

                elif tool_name == "explain_sql":
                    sql_to_exp = agent._resolve_sql(tool_input, last_sql)
                    explanation = agent._tool_explain_sql(sql_to_exp)
                    results.append({"tool": "explain_sql", "result": explanation})
                    console.print(Panel(Markdown(explanation), title="[bold cyan]📖 SQL 解释[/]", border_style="cyan"))

                elif tool_name == "optimize_sql":
                    sql_to_opt = agent._resolve_sql(tool_input, last_sql)
                    opt_result = agent._tool_optimize_sql(sql_to_opt)
                    results.append({"tool": "optimize_sql", "result": opt_result})
                    if opt_result.get("issues"):
                        console.print(Panel(
                            "\n".join(f"- {i}" for i in opt_result["issues"]),
                            title="[bold red]发现的问题[/]", border_style="red",
                        ))
                    if opt_result.get("optimized_sql"):
                        print_sql_block(opt_result["optimized_sql"])

                elif tool_name == "final_answer":
                    summary = agent._synthesize(task1, results)
                    results.append({"tool": "final_answer", "result": summary})
                    console.print(Panel(Markdown(summary), title="[bold gold1]📝 综合报告[/]", border_style="gold1"))

            agent._tool_results.append(results[-1])
            console.print()

        agent._history.append({"role": "user", "content": task1})
        agent.close()

        # ═══════════════════════════════════════════════════════════════════
        # 演示 2: 复杂多表 JOIN 查询
        # ═══════════════════════════════════════════════════════════════════
        console.print()
        console.rule("[bold white] 演示 2: 复杂多表 JOIN 查询 [/]", style="white")
        task2 = "查询工资最高的5名员工，显示姓名、工资、部门和入职日期"
        console.print(f"\n  [bold]📝 用户输入:[/] [italic]{task2}[/]\n")

        agent2 = SQLAgent(provider_name="longcat", db_config=db_config, dialect=DialectType.SQLITE)

        with Progress(SpinnerColumn(), TextColumn("[bold green]{task.description}"), console=console, transient=False) as progress:
            progress.add_task("🧠 Agent 正在理解任务...", total=None)
            plan2 = agent2._decompose_task(task2)

        sub_tasks2 = plan2.get("sub_tasks", [])
        if not sub_tasks2:
            sub_tasks2 = [
                {"id": 1, "tool": "generate_sql", "input": task2, "purpose": "生成 SQL"},
                {"id": 2, "tool": "final_answer", "input": "汇总结果", "purpose": "生成报告"},
            ]

        if plan2.get("understanding"):
            console.print(Panel(plan2["understanding"], title="[bold blue]🧠 任务理解 (CoT)[/]", border_style="blue"))

        console.print()
        table2 = Table(title="📋 子任务列表", show_header=True, header_style="bold", border_style="gold1")
        table2.add_column("ID", style="cyan", width=4, justify="center")
        table2.add_column("工具调用", style="yellow", width=18)
        table2.add_column("目的")
        for st in sub_tasks2:
            table2.add_row(str(st.get("id", "")), st.get("tool", ""), st.get("purpose", ""))
        console.print(table2)
        console.print()

        results2 = []
        last_sql2 = ""
        last_exec2 = None
        auto_executed2 = set()
        total2 = len(sub_tasks2[:agent2.config.max_sub_tasks])

        for idx, st in enumerate(sub_tasks2[:agent2.config.max_sub_tasks]):
            tool_name = st.get("tool", "")
            tool_input = st.get("input", "")
            purpose = st.get("purpose", "")

            print_step_header(idx + 1, total2, tool_name, purpose)

            with Progress(SpinnerColumn(), TextColumn("[bold green]{task.description}"), console=console, transient=False) as progress:
                progress.add_task(f"调用 {tool_name} 中...", total=None)

                if tool_name == "generate_sql":
                    gen_result = agent2._tool_generate_sql(tool_input)
                    results2.append({"tool": "generate_sql", "result": gen_result})
                    last_sql2 = gen_result.get("sql", "")

                    if last_sql2:
                        print_sql_block(last_sql2)
                    if gen_result.get("explanation"):
                        console.print(Panel(gen_result["explanation"], title="[bold yellow]💡 SQL 解释[/]", border_style="yellow"))

                    if last_sql2 and agent2.assistant._db:
                        progress.add_task("🗄️ 执行 SQL 中...", total=None)
                        exec_result = agent2._tool_execute_sql(last_sql2)
                        last_exec2 = exec_result
                        results2.append({"tool": "execute_sql", "result": exec_result})
                        auto_executed2.add("execute_sql")

                        if exec_result.get("rows"):
                            print_result_table(exec_result["columns"], exec_result["rows"])
                        if exec_result.get("error"):
                            console.print(f"[red]❌ 执行错误: {exec_result['error']}[/red]")

                        if exec_result.get("rows"):
                            progress.add_task("📊 AI 分析中...", total=None)
                            analysis = agent2._tool_analyze_result(task2, exec_result["rows"], exec_result["row_count"])
                            results2.append({"tool": "analyze_result", "result": analysis})
                            auto_executed2.add("analyze_result")
                            console.print(Panel(analysis, title="[bold green]📊 分析结论[/]", border_style="green"))

                elif tool_name == "execute_sql":
                    if "execute_sql" in auto_executed2:
                        console.print("  [dim]⏭️  已自动执行，跳过重复步骤[/]")
                        if last_exec2:
                            if last_exec2.get("rows"):
                                print_result_table(last_exec2["columns"], last_exec2["rows"])
                            if last_exec2.get("error"):
                                console.print(f"[red]❌ 执行错误: {last_exec2['error']}[/red]")
                        continue
                    sql_to_run = agent2._resolve_sql(tool_input, last_sql2)
                    exec_result = agent2._tool_execute_sql(sql_to_run)
                    last_exec2 = exec_result
                    results2.append({"tool": "execute_sql", "result": exec_result})
                    if exec_result.get("rows"):
                        print_result_table(exec_result["columns"], exec_result["rows"])

                elif tool_name == "analyze_result":
                    if "analyze_result" in auto_executed2:
                        console.print("  [dim]⏭️  已自动分析，跳过重复步骤[/]")
                        for prev_r in reversed(results2):
                            if prev_r.get("tool") == "analyze_result" and isinstance(prev_r.get("result"), str):
                                console.print(Panel(prev_r["result"], title="[bold green]📊 分析结论[/]", border_style="green"))
                                break
                        continue
                    if last_exec2 and last_exec2.get("rows"):
                        analysis = agent2._tool_analyze_result(task2, last_exec2["rows"], last_exec2["row_count"])
                        results2.append({"tool": "analyze_result", "result": analysis})
                        console.print(Panel(analysis, title="[bold green]📊 分析结论[/]", border_style="green"))

                elif tool_name == "validate_sql":
                    sql_to_val = agent2._resolve_sql(tool_input, last_sql2)
                    validation = agent2._tool_validate_sql(sql_to_val)
                    results2.append({"tool": "validate_sql", "result": validation})
                    status = "✅ 通过" if validation.get("is_valid") else "❌ 有问题"
                    console.print(f"  校验结果: {status}")
                    if validation.get("issues"):
                        for issue in validation["issues"]:
                            console.print(f"    [yellow]- {issue}[/]")

                elif tool_name == "fix_sql":
                    sql_to_fix = agent2._resolve_sql(tool_input, last_sql2)
                    fix_result = agent2._tool_fix_sql(sql_to_fix, st.get("error_message", ""))
                    results2.append({"tool": "fix_sql", "result": fix_result})
                    if fix_result.get("changes"):
                        console.print(f"  [orange]🔧 修复: {', '.join(fix_result['changes'])}[/]")

                elif tool_name == "explain_sql":
                    sql_to_exp = agent2._resolve_sql(tool_input, last_sql2)
                    explanation = agent2._tool_explain_sql(sql_to_exp)
                    results2.append({"tool": "explain_sql", "result": explanation})
                    console.print(Panel(Markdown(explanation), title="[bold cyan]📖 SQL 解释[/]", border_style="cyan"))

                elif tool_name == "optimize_sql":
                    sql_to_opt = agent2._resolve_sql(tool_input, last_sql2)
                    opt_result = agent2._tool_optimize_sql(sql_to_opt)
                    results2.append({"tool": "optimize_sql", "result": opt_result})
                    if opt_result.get("optimized_sql"):
                        print_sql_block(opt_result["optimized_sql"])

                elif tool_name == "final_answer":
                    summary = agent2._synthesize(task2, results2)
                    results2.append({"tool": "final_answer", "result": summary})
                    console.print(Panel(Markdown(summary), title="[bold gold1]📝 综合报告[/]", border_style="gold1"))

            agent2._tool_results.append(results2[-1])
            console.print()

        agent2.close()

        # ═══════════════════════════════════════════════════════════════════
        # 演示 3: 达梦方言 SQL 生成
        # ═══════════════════════════════════════════════════════════════════
        console.print()
        console.rule("[bold white] 演示 3: 达梦(DM) 方言 SQL 生成 [/]", style="white")
        task3 = "查询最近30天的订单，按天统计订单数量和总金额"
        console.print(f"\n  [bold]📝 用户输入:[/] [italic]{task3}[/]\n")

        assistant_dm = SQLAssistant(provider_name="longcat", dialect=DialectType.DM)

        with Progress(SpinnerColumn(), TextColumn("[bold green]{task.description}"), console=console, transient=False) as progress:
            progress.add_task("🐉 正在生成达梦方言 SQL...", total=None)
            result3 = assistant_dm.generate_sql(task3)

        if result3.get("sql"):
            print_sql_block(result3["sql"], "sql")
            if result3.get("explanation"):
                console.print(Panel(result3["explanation"], title="[bold yellow]💡 SQL 解释[/]", border_style="yellow"))
            if result3.get("dialect_notes"):
                console.print(Panel(result3["dialect_notes"], title="[bold yellow]🐉 方言注意事项[/]", border_style="yellow"))

        assistant_dm.close()

        # ── 结束 ──
        console.print()
        console.rule("[bold white on dark_green] 演示结束 [/]", style="dark_green")
        console.print()
        console.print(Panel(
            "[bold]本演示展示了 AI SQL Agent 的核心能力：[/]\n\n"
            "  1. [cyan]CoT 推理[/] — Agent 自动理解并拆解任务\n"
            "  2. [cyan]Tool Calling[/] — 8个工具自动协作完成工作流\n"
            "  3. [cyan]SQL 校验[/] — 语法检查 + 自动修复\n"
            "  4. [cyan]多方言支持[/] — 达梦/MySQL/PostgreSQL/SQLite\n"
            "  5. [cyan]结果分析[/] — AI 自动解读数据并给出建议",
            title="[bold]✨ 核心能力总结[/]", border_style="gold1"
        ))

        # ── 打印 LLM 调用日志摘要 ──
        trace.summary(log_file=log_file)

    finally:
        try:
            os.unlink(db_config._tmp_path)
        except Exception:
            pass


if __name__ == "__main__":
    demo_full_agent_workflow()
