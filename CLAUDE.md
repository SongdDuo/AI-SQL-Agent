# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI SQL Agent** is a multi-model collaborative SQL agent that converts natural language to SQL, executes queries, and analyzes results. It supports GPT, GLM, Claude, MiMo, DeepSeek, and Qwen models, with database dialects for 达梦(DM), MySQL, PostgreSQL, and SQLite.

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

# Specify dialect (达梦, MySQL, PostgreSQL, SQLite)
ai-sql -d dm ask "最近30天新增用户统计"

# Use specific model provider
ai-sql -p glm ask "查询销售额Top10的客户"

# Explain SQL
ai-sql explain "SELECT * FROM orders WHERE status = 1"

# Optimize SQL
ai-sql optimize "SELECT * FROM orders WHERE user_id IN (SELECT user_id FROM users)"

# Agent workflow (decompose → generate → execute → analyze)
ai-sql agent "分析上个月的销售趋势，找出Top10客户"

# Interactive mode
ai-sql interactive
```

### Configuration
Create `.env` file:
```bash
AI_DEFAULT_PROVIDER=openai
AI_OPENAI_API_KEY=sk-xxx
AI_GLM_API_KEY=xxx
AI_CLAUDE_API_KEY=sk-ant-xxx
```

## Project Architecture

```
src/ai_sql_agent/
├── agent.py           # Agent workflow (task decomposition, orchestration)
├── assistant.py       # Core engine (NL→SQL, explain, optimize, analyze)
├── cli.py             # CLI interface with Rich output
├── config.py          # Multi-model configuration management
├── models/
│   ├── base.py        # Base model interface
│   └── providers.py   # Provider implementations (OpenAI-compatible, Claude)
├── db/
│   ├── connector.py   # Database connection and SQL execution
│   └── dialects.py    # SQL dialect definitions
├── prompts/
│   └── templates.py   # Prompt templates for all capabilities
└── utils/
    └── formatter.py   # SQL formatting utilities
```

## Key Components

### SQLAssistant (`assistant.py`)
Core capabilities:
- `generate_sql()`: Natural language → SQL with schema context
- `explain_sql()`: Plain language explanation of SQL queries
- `optimize_sql()`: Performance analysis and optimization suggestions
- `execute_sql()`: Direct database execution
- `analyze_result()`: AI interpretation of query results
- `analyze_schema()`: Database schema analysis
- `chat()`: Free-form conversation

### SQLAgent (`agent.py`)
Automated workflow:
1. Task decomposition using LLM
2. Sub-task execution (generate_sql, execute_sql, analyze_result)
3. Result synthesis and reporting
4. Optional auto-execution of generated SQL

### Model Providers (`models/providers.py`)
- **OpenAICompatibleModel**: GPT, GLM, MiMo, DeepSeek, Qwen (OpenAI API compatible)
- **ClaudeModel**: Anthropic Claude API
- Provider registry pattern for easy extension

### Database Support (`db/connector.py`)
- 达梦 (DM) via dmPython
- MySQL via PyMySQL
- PostgreSQL via psycopg2
- Schema introspection and context generation

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

### Package Management
```bash
pip install -e ".[dev]"  # Development dependencies
pip install -e ".[all]"   # All database drivers
```

## Configuration Reference

### Model Providers
| Provider | Default Model | Base URL |
|----------|---------------|----------|
| openai | gpt-4o | https://api.openai.com/v1 |
| glm | glm-4-plus | https://open.bigmodel.cn/api/paas/v4 |
| mimo | mimo-v2.5 | https://api.xiaomimimo.com/v1 |
| claude | claude-sonnet-4-20250514 | https://api.anthropic.com |
| deepseek | deepseek-chat | https://api.deepseek.com/v1 |
| qwen | qwen-plus | https://dashscope.aliyuncs.com/compatible-mode/v1 |

### Database Dialects
- `dm`: 达梦数据库 (SYSDATE, TO_CHAR, NVL)
- `mysql`: MySQL syntax
- `postgres`: PostgreSQL syntax
- `sqlite`: SQLite syntax
- `standard`: Standard SQL

## Python SDK Usage

```python
from ai_sql_agent.assistant import SQLAssistant
from ai_sql_agent.agent import SQLAgent
from ai_sql_agent.db.dialects import DialectType
from ai_sql_agent.config import DBConfig

# Initialize assistant
assistant = SQLAssistant(provider_name="glm", dialect=DialectType.DM)

# Generate SQL
result = assistant.generate_sql("查询2024年每个季度的销售额")
print(result["sql"])
print(result["explanation"])

# Agent workflow
db_config = DBConfig(db_type="dm", host="localhost", port=5236, 
                     name="mydb", user="SYSDBA", password="xxx")
agent = SQLAgent(provider_name="mimo", db_config=db_config, dialect=DialectType.DM)
result = agent.run("分析上个月的销售趋势，找出消费金额Top10的客户")
```

## Common Development Tasks

### Adding New Model Provider
1. Add provider config in `config.py` PROVIDER_PRESETS
2. Update provider registry in `models/providers.py` if needed
3. Add CLI choice in `cli.py` PROVIDER_CHOICES

### Adding Database Dialect
1. Add dialect type in `db/dialects.py`
2. Update dialect resolution in `db/connector.py`
3. Add CLI choice in `cli.py` DIALECT_CHOICES

### Testing
- Unit tests in `tests/` directory
- Test both assistant and agent workflows
- Mock database connections for CI

## Important Notes

- Agent uses JSON parsing for structured outputs with markdown code block handling
- Database connections are lazy-initialized and auto-closed
- Prompt templates are centralized in `prompts/templates.py`
- Rich library used for formatted CLI output (syntax highlighting, tables, panels)
- Schema context is automatically included when database is configured
- All database operations use parameterized queries to prevent SQL injection