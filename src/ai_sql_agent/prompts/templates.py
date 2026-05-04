"""Prompt templates for SQL generation, analysis and Agent workflow."""

SYSTEM_PROMPT = """\
You are an expert SQL Agent that can understand, generate, optimize and explain SQL queries.
You support multiple database dialects: DM (达梦), MySQL, PostgreSQL, SQLite.

Dialect-specific rules:
- DM (达梦): LIMIT/OFFSET for pagination, NOW()/SYSDATE for current time, TO_CHAR for date formatting, \
TO_DATE for date parsing, NUMBER(1) for booleans, NVL instead of IFNULL, CONCAT for string concat
- MySQL: Standard MySQL syntax, LIMIT offset,count
- PostgreSQL: Standard PostgreSQL syntax
- SQLite: SQLite syntax

Always respond in the user's language.
"""

NL_TO_SQL_PROMPT = """\
Convert the following natural language request to a SQL query.

Dialect: {dialect}
{schema_context}

Request: {query}

Respond with a JSON object:
{{
  "sql": "the SQL query",
  "explanation": "what the query does",
  "dialect_notes": "any dialect-specific considerations"
}}
"""

EXPLAIN_SQL_PROMPT = """\
Explain the following SQL query step by step.

Dialect: {dialect}

SQL:
```sql
{sql}
```

Provide:
1. Step-by-step breakdown
2. Tables and joins involved
3. Performance analysis
4. Potential issues
"""

OPTIMIZE_SQL_PROMPT = """\
Analyze and optimize this SQL query for {dialect}.

SQL:
```sql
{sql}
```

Respond with JSON:
{{
  "issues": ["list of problems found"],
  "optimized_sql": "improved query",
  "changes": [
    {{"what": "description", "why": "reason", "type": "index|rewrite|hint"}}
  ],
  "expected_gain": "estimated improvement"
}}
"""

ANALYZE_RESULT_PROMPT = """\
Analyze the following SQL query result and provide insights.

Original query: {query}
Dialect: {dialect}

Result ({row_count} rows):
{result_preview}

Provide:
1. Key findings summary
2. Data patterns or anomalies
3. Recommendations based on the data
"""

AGENT_TASK_DECOMPOSE_PROMPT = """\
You are a SQL Agent. Decompose the following user task into sub-tasks.

Available tools:
- generate_sql: Convert natural language to SQL
- execute_sql: Execute a SQL query against the database
- explain_sql: Explain a SQL query
- optimize_sql: Optimize a SQL query
- analyze_result: Analyze query results

Database dialect: {dialect}
{schema_context}

User task: {task}

Respond with JSON:
{{
  "understanding": "your understanding of the task",
  "sub_tasks": [
    {{
      "id": 1,
      "tool": "tool_name",
      "input": "input for the tool",
      "purpose": "why this step"
    }}
  ],
  "depends_on": {{}}
}}
"""

SCHEMA_ANALYSIS_PROMPT = """\
Analyze this database schema and suggest improvements.

Dialect: {dialect}

Schema:
{schema}

Provide:
1. Missing indexes
2. Data type improvements
3. Normalization issues
4. Naming conventions
"""
