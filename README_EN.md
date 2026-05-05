<p align="center">
  <h1 align="center">🤖 AI SQL Agent</h1>
  <p align="center">
    <strong>Multi-Model Collaborative AI SQL Agent</strong>
  </p>
  <p align="center">
    🚀 Natural Language → SQL Generation → Execution → Result Analysis
  </p>
  <p align="center">
    <a href="https://github.com/SongdDuo/AI-SQL-Agent" target="_blank">🌟 GitHub</a> •
    <a href="https://github.com/SongdDuo/AI-SQL-Agent/actions" target="_blank">🔄 Actions</a> •
    <a href="#features">✨ Features</a> •
    <a href="#quick-start">🚀 Quick Start</a> •
    <a href="#usage">📖 Usage</a> •
    <a href="#agent-workflow">🤖 Agent Workflow</a> •
    <a href="#supported-models">🧠 Models</a> •
    <a href="#contributing">🤝 Contributing</a> •
    <a href="README.md">中文</a>
  </p>
</p>

---

## Overview

AI SQL Agent is a multi-model collaborative SQL agent that supports the complete workflow from natural language to SQL generation, execution, and result analysis.

By integrating **GPT, GLM, Claude, MiMo, DeepSeek, and Qwen** LLMs, it enables complex query understanding, multi-turn reasoning, and automated data analysis for real-world development and analytics scenarios.

Unlike traditional SQL tools, this project introduces an **Agent workflow** that automatically decomposes user tasks, generates queries, executes database operations, and provides structured analysis and explanations of results.

## Features

- **NL to SQL** — Describe what you need in natural language, get production-ready SQL
- **Agent Workflow** — Automatic task decomposition → SQL generation → execution → result analysis
- **SQL Execution Engine** — Connect to real databases, execute SQL and return structured results
- **Smart Result Analysis** — AI-powered interpretation of query results with pattern detection
- **SQL Optimization** — Detect performance issues, provide optimization suggestions and index recommendations
- **SQL Explanation** — Step-by-step plain-language breakdown of complex queries
- **Multi-Model** — Switch between GPT / GLM / Claude / MiMo / DeepSeek / Qwen instantly
- **Multi-Dialect** — DM (达梦), MySQL, PostgreSQL, SQLite
- **Schema-Aware** — Connect your database for context-aware, precise SQL generation
- **CLI & SDK** — Command-line tool + Python SDK for flexible integration

## Quick Start

### Installation

```bash
pip install ai-sql-agent
```

Install database drivers as needed:

```bash
pip install ai-sql-agent[dm]       # DM (达梦)
pip install ai-sql-agent[mysql]    # MySQL
pip install ai-sql-agent[postgres] # PostgreSQL
pip install ai-sql-agent[claude]   # Claude support
pip install ai-sql-agent[all]      # All
```

### Configuration

Create a `.env` file (or set environment variables):

```bash
# Choose default model provider
AI_DEFAULT_PROVIDER=openai

# Configure API keys (fill at least one)
AI_OPENAI_API_KEY=sk-xxx
AI_GLM_API_KEY=xxx
AI_MIMO_API_KEY=xxx
AI_CLAUDE_API_KEY=sk-ant-xxx
```

## Usage

### CLI

```bash
# Natural language to SQL
ai-sql ask "Show average salary by department, only those above 10000"

# Specify DM dialect
ai-sql -d dm ask "Daily new user count for the last 30 days"

# Use GLM model
ai-sql -p glm ask "Top 10 customers by sales amount"

# Explain SQL
ai-sql explain "SELECT * FROM orders WHERE status = 1"

# Optimize SQL
ai-sql optimize "SELECT * FROM orders WHERE user_id IN (SELECT user_id FROM users WHERE status = 1)"

# Agent workflow (auto decompose, generate, execute, analyze)
ai-sql agent "Analyze last month's sales trends, find Top 10 customers"

# Interactive mode
ai-sql interactive
```

### Python SDK

```python
from ai_sql_agent.assistant import SQLAssistant
from ai_sql_agent.agent import SQLAgent
from ai_sql_agent.db.dialects import DialectType

# Initialize (choose model + dialect)
assistant = SQLAssistant(provider_name="glm", dialect=DialectType.DM)

# NL → SQL
result = assistant.generate_sql("Quarterly sales for 2024 with YoY growth rate")
print(result["sql"])
print(result["explanation"])

# Explain SQL
print(assistant.explain_sql("SELECT ..."))

# Optimize SQL
opt = assistant.optimize_sql("SELECT ...")
print(opt["optimized_sql"])

# Free-form chat
print(assistant.chat("What's the pagination syntax for DM database?"))
```

### Agent Workflow

```python
from ai_sql_agent.agent import SQLAgent
from ai_sql_agent.config import DBConfig
from ai_sql_agent.db.dialects import DialectType

# Optional: connect database for auto-execution
db_config = DBConfig(db_type="dm", host="localhost", port=5236,
                     name="mydb", user="SYSDBA", password="xxx")

agent = SQLAgent(
    provider_name="mimo",
    db_config=db_config,
    dialect=DialectType.DM,
)

# One sentence → decompose → generate → execute → analyze
result = agent.run("Analyze last month's sales trends, find Top 10 customers by spending")

print(f"Understanding: {result['understanding']}")
print(f"Sub-tasks: {len(result['sub_tasks'])}")
print(f"Summary:\n{result['summary']}")
```

## Agent Workflow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ User Task │────▶│ Decompose │────▶│ SQL Gen   │────▶│ Execute   │────▶│ Analyze   │
│ (NL)      │     │ (Agent)   │     │ (LLM)     │     │ (DB)      │     │ (LLM)     │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
                       │                                                  │
                       │          ┌──────────────────────────┐            │
                       └─────────▶│    Final Report           │◀───────────┘
                                  └──────────────────────────┘
```

The Agent automatically decomposes complex tasks into sub-tasks:
1. **Understand** — Analyze user intent
2. **Decompose** — Break into generate_sql / execute_sql / analyze_result sub-tasks
3. **Execute** — Run sub-tasks in sequence
4. **Analyze** — AI interprets execution results
5. **Synthesize** — Generate final report

## Supported Models

| Provider | `provider` param | Notes |
|----------|-----------------|-------|
| OpenAI GPT | `openai` | GPT-4o etc. |
| Zhipu GLM | `glm` | GLM-4-Plus |
| Xiaomi MiMo | `mimo` | MiMo V2.5 |
| Anthropic Claude | `claude` | Claude Sonnet |
| DeepSeek | `deepseek` | DeepSeek Chat |
| Alibaba Qwen | `qwen` | Qwen-Plus |

## Supported Dialects

| Dialect | `-d` param | Notes |
|---------|-----------|-------|
| DM (达梦) | `dm` | DM-specific syntax (SYSDATE/TO_CHAR/NVL etc.) |
| MySQL | `mysql` | MySQL syntax |
| PostgreSQL | `postgres` | PostgreSQL syntax |
| SQLite | `sqlite` | SQLite syntax |
| Standard SQL | `standard` | Default |

## Architecture

```
src/ai_sql_agent/
├── agent.py           # Agent workflow (decompose, orchestrate, synthesize)
├── assistant.py       # Core engine (NL→SQL, explain, optimize, analyze)
├── cli.py             # CLI entry point
├── config.py          # Multi-model configuration
├── models/
│   ├── base.py        # Model base class (unified interface)
│   └── providers.py   # Model implementations (OpenAI-compatible / Claude)
├── db/
│   ├── connector.py   # DB connection + SQL execution
│   └── dialects.py    # Dialect definitions + syntax conversion
├── prompts/
│   └── templates.py   # Prompt templates
└── utils/
    └── formatter.py   # SQL formatting
```

## Contributing

Contributions welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

[MIT License](LICENSE)
