# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI SQL Agent** is a multi-model collaborative SQL agent built on **LongCat-2.0-Preview**. It converts natural language to SQL, executes queries, and analyzes results using an **Agent + Tool Calling** architecture with Chain-of-Thought reasoning.

## Architecture

The system uses a **Tool Calling loop** with SQL validation and auto-fix:

1. User inputs natural language → Agent decomposes task (CoT)
2. Tool call: `generate_sql` → LLM generates SQL with schema context
3. Tool call: `validate_sql` → Syntax/semantic validation
4. Tool call: `execute_sql` → Database execution
5. On failure → `fix_sql` auto-fixes and retries
6. Tool call: `analyze_result` → Natural language summary
7. Tool call: `final_answer` → Synthesized report

## Quick Start Commands

### Installation
```bash
pip install ai-sql-agent
pip install ai-sql-agent[all]  # All database drivers and Claude support
```

### CLI Usage
```bash
# Natural language to SQL
ai-sql ask "查询每个部门的平均工资"

# Use LongCat model (recommended)
ai-sql -p longcat ask "查询销售额Top10的客户"

# Agent workflow with Tool Calling
ai-sql agent "分析上个月的销售趋势，找出Top10客户"

# Interactive mode (multi-turn)
ai-sql interactive
```

### Configuration
Create `.env` file:
```bash
AI_DEFAULT_PROVIDER=longcat
AI_LONGCAT_API_KEY=your_api_key
DB_TYPE=sqlite
DB_NAME=:memory:
```

## Project Architecture

```
src/ai_sql_agent/
├── agent.py           # Agent workflow (Tool Calling + CoT + auto-fix loop)
├── assistant.py       # Core engine (NL→SQL, explain, optimize, multi-turn)
├── cli.py             # CLI interface with Rich output
├── config.py          # Multi-model config (LongCat family + 10 providers)
├── models/
│   ├── base.py        # Base model interface (Message, BaseModel)
│   └── providers.py   # Provider implementations (OpenAI-compatible, Claude)
├── db/
│   ├── connector.py   # Database connection and SQL execution
│   ├── dialects.py    # SQL dialect definitions (DM, MySQL, PG, SQLite)
│   └── validator.py   # SQL validation + auto-fix (NEW)
├── prompts/
│   └── templates.py   # Prompt templates (Tool Calling, CoT, multi-turn)
└── utils/
    └── formatter.py   # SQL formatting utilities
```

## Key Components

### SQLAgent (`agent.py`) — Tool Calling Architecture
- **Tool registry**: generate_sql, execute_sql, validate_sql, fix_sql, explain_sql, optimize_sql, analyze_result, final_answer
- **CoT reasoning**: Agent thinks step-by-step before tool calls
- **Auto-fix loop**: On SQL execution failure → validate → fix → retry (max 3 retries)
- **Multi-turn context**: Maintains conversation history and tool results
- **Schema-aware**: Auto-includes database schema in context

### SQLAssistant (`assistant.py`) — Core Engine
- `generate_sql()`: NL → SQL with schema context
- `explain_sql()`: Plain language SQL explanation
- `optimize_sql()`: Performance optimization
- `execute_sql()`: Database execution
- `analyze_result()`: Result interpretation
- `chat()`: Free-form conversation
- `chat_multi_turn()`: Multi-turn conversation with schema awareness (NEW)

### SQLValidator & SQLAutoFixer (`db/validator.py`) — NEW
- Syntax validation (parentheses, keywords)
- SQL injection detection
- Dialect-specific checks (e.g., MySQL functions in DM)
- Auto-fix: keyword casing, dialect functions, parentheses, trailing semicolons
- Error-message-based fixing suggestions

### Model Providers (`models/providers.py`)
- **OpenAICompatibleModel**: LongCat family, GPT, GLM, MiMo, DeepSeek, Qwen
- **ClaudeModel**: Anthropic Claude API
- LongCat models: `longcat`, `longcat-flash`, `longcat-thinking`, `longcat-omni`, `longcat-lite`

## Development Commands

### Testing
```bash
pytest tests/
pytest tests/test_agent.py -v
```

### Code Quality
```bash
ruff check .
ruff format .
```

## Configuration Reference

### LongCat Models
| Provider | param | Model |
|----------|-------|-------|
| LongCat | `longcat` | longcat-2.0-preview |
| LongCat Flash | `longcat-flash` | LongCat-Flash-Chat |
| LongCat Thinking | `longcat-thinking` | LongCat-Flash-Thinking-2601 |
| LongCat Omni | `longcat-omni` | LongCat-Flash-Omni-2603 |
| LongCat Lite | `longcat-lite` | LongCat-Flash-Lite |

### All Model Providers (16)
**LongCat 系列**: `longcat`, `longcat-flash`, `longcat-thinking`, `longcat-omni`, `longcat-lite`
**国际**: `openai`, `claude`, `grok`
**国产**: `glm`, `mimo`, `deepseek`, `qwen`, `kimi`, `doubao`, `yuanbao`
**中转站**: `openai-proxy`, `claude-proxy`

### Database Dialects
- `dm`: 达梦数据库 (SYSDATE, TO_CHAR, NVL)
- `mysql`: MySQL syntax
- `postgres`: PostgreSQL syntax
- `sqlite`: SQLite syntax (recommended for testing)
- `standard`: Standard SQL

## Common Development Tasks

### Adding New Model Provider
1. Add provider config in `config.py` PROVIDER_PRESETS
2. If OpenAI-compatible, just add to PROVIDER_REGISTRY in `models/providers.py`
3. Add CLI choice in `cli.py` PROVIDER_CHOICES

### Adding New Tool to Agent
1. Define tool method in `agent.py` (e.g., `_tool_custom()`)
2. Register in `self._tools` dict in `__init__`
3. Update `_get_tool_descriptions()` for prompt

### Adding Database Dialect
1. Add dialect type in `db/dialects.py`
2. Update dialect resolution in `db/connector.py`
3. Add CLI choice in `cli.py` DIALECT_CHOICES

## Web UI (`src/ai_sql_agent/web.py`)

### 启动
```bash
ai-sql web --port 8080
```

### 关键功能
- **多轮对话**：对话历史通过 localStorage 存储，按会话分组，支持切换/删除/新建
- **写操作支持**：统一走 `generate_sql`，LLM 根据上下文判断 SELECT/INSERT/UPDATE/DELETE/CREATE
- **多语句 SQL**：`connector.execute()` 支持按 `;` 拆分逐条执行
- **中文输出**：`SYSTEM_PROMPT` 和 `NL_TO_SQL_PROMPT` 均为中文，强制 LLM 中文回复
- **暗色主题**：theme-btn/menu-toggle 使用 `var(--bg2)` 背景 + `var(--text2)` 文字
- **日志**：按天写入 `logs/web_YYYY-MM-DD.log`，记录用户消息、AI 回复、错误异常

### 示例数据库（13 张表）
department, employee, customer, orders, product, order_detail, attendance, customer_feedback, project, employee_skill, salary_history

### JS 开发注意事项
- HTML 模板是 Python 多行字符串，JS 代码中的引号必须正确转义
- 用 `node -c` 检查提取后的 JS 语法：`python -c "import re; content=open('web.py').read(); scripts=re.findall(r'<script[^>]*>([\s\S]*?)</script>', content[content.find('HTML_TEMPLATE'):]); open('check.js','w').write(scripts[1])"` 然后 `node -c check.js`
- 浏览器缓存可能导致旧 JS 代码残留，测试时建议强制刷新（Ctrl+Shift+R）

## Important Notes

- Agent uses JSON parsing for structured outputs with markdown code block handling
- Database connections are lazy-initialized and auto-closed
- All database operations use parameterized queries to prevent SQL injection
- SQL validator checks for injection patterns, unbalanced parentheses, dialect mismatches
- Auto-fix retries up to 3 times with progressive fixes
- Multi-turn chat keeps last 10 turns of history
- Tool results are accumulated and fed back into agent context for next iteration
