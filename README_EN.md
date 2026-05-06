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
    <a href="#problem-statement">💡 Problem</a> •
    <a href="#architecture">🏗️ Architecture</a> •
    <a href="#features">✨ Features</a> •
    <a href="#quick-start">🚀 Quick Start</a> •
    <a href="#usage">📖 Usage</a> •
    <a href="#supported-models">🧠 Models</a> •
    <a href="#contributing">🤝 Contributing</a> •
    <a href="README.md">中文</a>
  </p>
</p>

---

## 💡 Problem Statement

In real-world business scenarios, data querying heavily relies on developers writing SQL manually. Non-technical users cannot perform data analysis directly, resulting in high communication costs and slow response times.

**AI SQL Agent** solves this: users describe needs in natural language, and the system automatically completes the full cycle of SQL generation, execution, and result analysis.

## 🏗️ Core Architecture

The system adopts an **Agent + Tool Calling** design:

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  User    │────▶│  Intent  │────▶│  SQL Gen  │────▶│ Validate  │────▶│  Execute  │
│ (NL)     │     │ (Agent)  │     │(LLM+CoT) │     │(Validator)│     │  (DB)     │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
                       │                │                │                │
                       │                │         ┌──────┴──────┐         │
                       │                │         │  Auto-Fix   │         │
                       │                │         │ (On Failure)│◀────────┘
                       │                │         └──────┬──────┘
                       │                │                │
                       ▼                ▼                ▼                ▼
                  ┌─────────────────────────────────────────────────────────────┐
                  │              Result Analysis & Final Report                  │
                  │         (Multi-turn Context + Schema-Aware Reasoning)        │
                  └─────────────────────────────────────────────────────────────┘
```

### 🔄 Tool Calling Loop

1. 📝 User inputs a natural language question (e.g., "order trends for the last 30 days")
2. 🧠 Agent parses intent and maps fields using database schema
3. 💻 Auto-generates SQL with syntax and logic validation
4. 🔧 If SQL execution fails → auto-fix and retry
5. 🗄️ Execute query against database
6. 📊 Summarize results in natural language

### 🧠 Reasoning Approach

- **Chain of Thought (CoT)**: Agent thinks before acting, decomposing complex tasks step by step
- **SQL Validation Loop**: Generate → Validate → Fix → Retry to ensure correctness
- **Schema-Aware**: Automatically understands table structures when connected to a database
- **Multi-Turn Context**: Supports follow-up questions with conversation history

## ✨ Features

- 💬 **NL to SQL** — Describe needs in natural language, get production-ready SQL
- 🤖 **Agent Workflow** — Automatic task decomposition → SQL generation → execution → analysis
- 🚀 **SQL Execution Engine** — Connect to real databases, execute and return structured results
- 📊 **Smart Result Analysis** — AI interprets query results, finds patterns and anomalies
- ⚡ **SQL Optimization** — Detects performance issues, provides optimization suggestions
- 📝 **SQL Explanation** — Step-by-step plain-language breakdown of complex queries
- 🔧 **Auto SQL Fix** — Automatically diagnoses and fixes SQL errors on execution failure
- 🧠 **Multi-Model** — LongCat / GPT / GLM / Claude / MiMo / DeepSeek / Qwen
- 🗄️ **Multi-Dialect** — DM (达梦), MySQL, PostgreSQL, SQLite
- 🕵️ **Schema-Aware** — Auto-understands table structures for precise SQL generation
- 💬 **Multi-Turn Chat** — Supports follow-up questions with context preservation
- 🛠️ **CLI & SDK** — Command-line tool + Python SDK for flexible integration

## 🚀 Quick Start

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

Create a `.env` file for local testing:

```bash
# Choose default model provider (LongCat recommended)
AI_DEFAULT_PROVIDER=longcat

# Configure API Key
AI_LONGCAT_API_KEY=your_longcat_api_key_here

# Use SQLite for testing (no real database needed)
DB_TYPE=sqlite
DB_NAME=:memory:  # In-memory database
```

## 📖 Usage

### CLI

```bash
# Natural language to SQL
ai-sql ask "Show average salary by department, only those above 10000"

# Specify DM dialect
ai-sql -d dm ask "Daily new user count for the last 30 days"

# Use LongCat model
ai-sql -p longcat ask "Top 10 customers by sales amount"

# Use LongCat Thinking model (stronger reasoning)
ai-sql -p longcat-thinking ask "Analyze sales trends for the past 6 months"

# Explain SQL
ai-sql explain "SELECT * FROM orders WHERE status = 1"

# Optimize SQL
ai-sql optimize "SELECT * FROM orders WHERE user_id IN (SELECT user_id FROM users WHERE status = 1)"

# Agent workflow
ai-sql agent "Analyze last month's sales trends, find Top 10 customers"

# Interactive mode (multi-turn conversation)
ai-sql interactive
```

### Python SDK

```python
from ai_sql_agent.assistant import SQLAssistant
from ai_sql_agent.agent import SQLAgent
from ai_sql_agent.db.dialects import DialectType

# Initialize (choose model + dialect)
assistant = SQLAssistant(provider_name="longcat", dialect=DialectType.MYSQL)

# NL → SQL
result = assistant.generate_sql("Quarterly sales for 2024 with YoY growth rate")
print(result["sql"])
print(result["explanation"])

# Multi-turn conversation
history = []
response = assistant.chat_multi_turn("Average salary by department", history=history)
history.append({"role": "user", "content": "Average salary by department"})
history.append({"role": "assistant", "content": response})

# Follow-up question (context-aware)
response = assistant.chat_multi_turn("Only show above 10000", history=history)
```

### Agent Workflow

```python
from ai_sql_agent.agent import SQLAgent
from ai_sql_agent.config import DBConfig
from ai_sql_agent.db.dialects import DialectType

db_config = DBConfig(db_type="mysql", host="localhost", port=3306,
                     name="mydb", user="root", password="xxx")

agent = SQLAgent(
    provider_name="longcat",
    db_config=db_config,
    dialect=DialectType.MYSQL,
)

# One sentence → decompose → generate → validate → execute → analyze
result = agent.run("Analyze last month's sales trends, find Top 10 customers by spending")

print(f"Understanding: {result['understanding']}")
print(f"Sub-tasks: {len(result['sub_tasks'])}")
print(f"Summary:\n{result['summary']}")
```

## 🧠 Supported Models

| Provider | `provider` param | Notes |
|----------|-----------------|-------|
| 🐱 LongCat | `longcat` | LongCat-2.0-Preview (recommended) |
| ⚡ LongCat Flash | `longcat-flash` | LongCat-Flash-Chat (fast) |
| 🧠 LongCat Thinking | `longcat-thinking` | LongCat-Flash-Thinking-2601 (strong reasoning) |
| 🎭 LongCat Omni | `longcat-omni` | LongCat-Flash-Omni-2603 (multimodal) |
| 🪶 LongCat Lite | `longcat-lite` | LongCat-Flash-Lite (lightweight) |
| OpenAI GPT | `openai` | GPT-4o etc. |
| Zhipu GLM | `glm` | GLM-4-Plus |
| Xiaomi MiMo | `mimo` | MiMo V2.5 |
| Anthropic Claude | `claude` | Claude Sonnet |
| DeepSeek | `deepseek` | DeepSeek Chat |
| Alibaba Qwen | `qwen` | Qwen-Plus |

### LongCat Configuration

```bash
# .env
AI_DEFAULT_PROVIDER=longcat
AI_LONGCAT_API_KEY=your_api_key_here

# Optional: custom base URL and model
AI_LONGCAT_BASE_URL=https://api.longcat.chat/openai
AI_LONGCAT_MODEL=longcat-2.0-preview
```

## 🗄️ Supported Dialects

| Dialect | `-d` param | Notes |
|---------|-----------|-------|
| DM (达梦) | `dm` | DM-specific syntax (SYSDATE/TO_CHAR/NVL etc.) |
| MySQL | `mysql` | MySQL syntax |
| PostgreSQL | `postgres` | PostgreSQL syntax |
| SQLite | `sqlite` | SQLite syntax (recommended for testing) |
| Standard SQL | `standard` | Default |

## 📁 Project Structure

```
src/ai_sql_agent/
├── agent.py           # Agent workflow (Tool Calling + CoT reasoning)
├── assistant.py       # Core engine (NL→SQL, explain, optimize, multi-turn)
├── cli.py             # CLI entry point
├── config.py          # Multi-model configuration (incl. LongCat family)
├── models/
│   ├── base.py        # Model base class (unified interface)
│   └── providers.py   # Model implementations (OpenAI-compatible / Claude)
├── db/
│   ├── connector.py   # DB connection + SQL execution
│   ├── dialects.py    # Dialect definitions + syntax conversion
│   └── validator.py   # SQL validation + auto-fix
├── prompts/
│   └── templates.py   # Prompt templates (incl. Tool Calling / CoT)
└── utils/
    └── formatter.py   # SQL formatting
```

## 📊 Results

- ⚡ **60%~80% improvement** in data query efficiency
- 👥 **Non-technical users** can perform basic analysis tasks directly
- ✅ **Most common analysis problems** can auto-generate correct SQL in test scenarios
- 🔧 **Auto SQL fix** reduces manual intervention
- 💬 **Multi-turn conversation** eliminates repetitive context

## 🔗 Project Links

| Type | URL |
|------|-----|
| 🌟 GitHub Repository | https://github.com/SongdDuo/AI-SQL-Agent |
| 🔄 GitHub Actions | https://github.com/SongdDuo/AI-SQL-Agent/actions |
| 📦 PyPI Package | https://pypi.org/project/ai-sql-agent/ |
| 📄 Documentation | https://github.com/SongdDuo/AI-SQL-Agent#readme |

## 🤝 Contributing

Contributions welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

[MIT License](LICENSE)
