<p align="center">
  <h1 align="center">AI SQL Agent</h1>
  <p align="center">
    <strong>基于多模型协同的 AI SQL Agent</strong>
  </p>
  <p align="center">
    自然语言 → SQL 生成 → 执行 → 结果分析，一站式智能数据查询
  </p>
  <p align="center">
    <a href="#功能特性">功能</a> •
    <a href="#快速开始">快速开始</a> •
    <a href="#使用方式">使用</a> •
    <a href="#agent-工作流">Agent 工作流</a> •
    <a href="#支持的模型">模型</a> •
    <a href="#贡献指南">贡献</a> •
    <a href="README_EN.md">English</a>
  </p>
</p>

---

## 项目简介

本项目是一个基于多模型协同的 AI SQL Agent，支持从自然语言到 SQL 生成、执行与结果分析的完整工作流。

系统通过集成 **GPT、GLM、Claude、MiMo、DeepSeek、Qwen** 等大模型，实现复杂查询理解、多轮推理与自动化数据分析，适用于真实开发与数据分析场景。

与传统 SQL 工具不同，本项目引入 **Agent 工作流**，可自动拆解用户任务、生成查询、执行数据库操作，并对结果进行结构化分析与解释。

## 功能特性

- **自然语言转 SQL** — 用中文描述需求，自动生成生产级 SQL
- **Agent 自动工作流** — 任务自动拆解 → SQL 生成 → 执行 → 结果分析
- **SQL 执行引擎** — 连接真实数据库，直接执行并返回结构化结果
- **智能结果分析** — AI 自动解读查询结果，发现数据规律和异常
- **SQL 优化建议** — 检测性能问题，给出优化方案和索引建议
- **SQL 解释** — 将复杂 SQL 逐步拆解为自然语言说明
- **多模型支持** — GPT / GLM / Claude / MiMo / DeepSeek / Qwen 一键切换
- **多方言支持** — 达梦(DM)、MySQL、PostgreSQL、SQLite
- **Schema 感知** — 连接数据库后，AI 自动理解表结构生成精准 SQL
- **CLI & SDK** — 命令行工具 + Python SDK，灵活集成

## 快速开始

### 安装

```bash
pip install ai-sql-agent
```

按需安装数据库驱动：

```bash
pip install ai-sql-agent[dm]       # 达梦
pip install ai-sql-agent[mysql]    # MySQL
pip install ai-sql-agent[postgres] # PostgreSQL
pip install ai-sql-agent[claude]   # Claude 支持
pip install ai-sql-agent[all]      # 全部
```

### 配置

创建 `.env` 文件（或设置环境变量）：

```bash
# 选择默认模型提供商
AI_DEFAULT_PROVIDER=openai

# 配置 API Key（按需填写，至少配一个）
AI_OPENAI_API_KEY=sk-xxx
AI_GLM_API_KEY=xxx
AI_MIMO_API_KEY=xxx
AI_CLAUDE_API_KEY=sk-ant-xxx
```

## 使用方式

### CLI 命令行

```bash
# 自然语言转 SQL
ai-sql ask "查询每个部门的平均工资，只显示大于10000的"

# 指定达梦方言
ai-sql -d dm ask "最近30天新增用户按天统计"

# 使用 GLM 模型
ai-sql -p glm ask "查询销售额Top10的客户"

# 解释 SQL
ai-sql explain "SELECT * FROM orders WHERE status = 1"

# 优化 SQL
ai-sql optimize "SELECT * FROM orders WHERE user_id IN (SELECT user_id FROM users WHERE status = 1)"

# Agent 工作流（自动拆解、生成、执行、分析）
ai-sql agent "分析上个月的销售趋势，找出Top10客户"

# 交互模式
ai-sql interactive
```

### Python SDK

```python
from ai_sql_agent.assistant import SQLAssistant
from ai_sql_agent.agent import SQLAgent
from ai_sql_agent.db.dialects import DialectType

# 初始化（选择模型 + 方言）
assistant = SQLAssistant(provider_name="glm", dialect=DialectType.DM)

# 自然语言 → SQL
result = assistant.generate_sql("查询2024年每个季度的销售额，同比增长率")
print(result["sql"])
print(result["explanation"])

# 解释 SQL
print(assistant.explain_sql("SELECT ..."))

# 优化 SQL
opt = assistant.optimize_sql("SELECT ...")
print(opt["optimized_sql"])

# 自由对话
print(assistant.chat("达梦数据库分页语法是什么？"))
```

### Agent 工作流

```python
from ai_sql_agent.agent import SQLAgent
from ai_sql_agent.config import DBConfig
from ai_sql_agent.db.dialects import DialectType

# 可选：连接数据库实现自动执行
db_config = DBConfig(db_type="dm", host="localhost", port=5236,
                     name="mydb", user="SYSDBA", password="xxx")

agent = SQLAgent(
    provider_name="mimo",
    db_config=db_config,
    dialect=DialectType.DM,
)

# 一句话完成：拆解 → 生成 → 执行 → 分析
result = agent.run("分析上个月的销售趋势，找出消费金额Top10的客户")

print(f"理解: {result['understanding']}")
print(f"子任务: {len(result['sub_tasks'])} 个")
print(f"摘要:\n{result['summary']}")
```

## Agent 工作流

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  用户任务  │────▶│  任务拆解  │────▶│  SQL 生成  │────▶│  SQL 执行  │────▶│  结果分析  │
│ (自然语言) │     │ (Agent)   │     │ (LLM)     │     │ (DB)      │     │ (LLM)     │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
                       │                                                  │
                       │          ┌──────────────────────────┐            │
                       └─────────▶│    综合报告输出             │◀───────────┘
                                  └──────────────────────────┘
```

Agent 自动将复杂任务拆分为子任务，逐步执行：
1. **理解** — 分析用户意图
2. **拆解** — 分解为 generate_sql / execute_sql / analyze_result 等子任务
3. **执行** — 按序执行各子任务
4. **分析** — AI 解读执行结果
5. **综合** — 生成最终报告

## 支持的模型

| 提供商 | provider 参数 | 说明 |
|--------|-------------|------|
| OpenAI GPT | `openai` | GPT-4o 等 |
| 智谱 GLM | `glm` | GLM-4-Plus |
| 小米 MiMo | `mimo` | MiMo V2.5 |
| Anthropic Claude | `claude` | Claude Sonnet |
| DeepSeek | `deepseek` | DeepSeek Chat |
| 阿里通义 | `qwen` | Qwen-Plus |

## 支持的数据库方言

| 方言 | `-d` 参数 | 说明 |
|------|---------|------|
| 达梦(DM) | `dm` | 达梦数据库语法（SYSDATE/TO_CHAR/NVL 等） |
| MySQL | `mysql` | MySQL 语法 |
| PostgreSQL | `postgres` | PostgreSQL 语法 |
| SQLite | `sqlite` | SQLite 语法 |
| 标准 SQL | `standard` | 默认 |

## 项目架构

```
src/ai_sql_agent/
├── agent.py           # Agent 工作流（任务拆解、编排、综合）
├── assistant.py       # 核心引擎（NL→SQL、解释、优化、分析）
├── cli.py             # CLI 命令行入口
├── config.py          # 多模型配置管理
├── models/
│   ├── base.py        # 模型基类（统一接口）
│   └── providers.py   # 各模型实现（OpenAI兼容 / Claude）
├── db/
│   ├── connector.py   # 数据库连接 + SQL 执行
│   └── dialects.py    # 方言定义 + 语法转换
├── prompts/
│   └── templates.py   # 提示词模板
└── utils/
    └── formatter.py   # SQL 格式化
```

## 贡献指南

欢迎贡献！步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

## License

[MIT License](LICENSE)
