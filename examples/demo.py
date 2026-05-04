"""Demo: Using AI SQL Agent programmatically."""

from ai_sql_agent.agent import SQLAgent
from ai_sql_agent.assistant import SQLAssistant
from ai_sql_agent.config import DBConfig
from ai_sql_agent.db.dialects import DialectType


def demo_assistant():
    """Basic assistant usage — no database required."""
    # Supports: openai, glm, mimo, claude, deepseek, qwen
    assistant = SQLAssistant(
        provider_name="openai",
        dialect=DialectType.DM,
    )

    # 1. NL → SQL
    print("=== 1. Natural Language to SQL ===")
    result = assistant.generate_sql("查询2024年每个季度的销售额，同比增长率")
    print(f"SQL: {result.get('sql', '')}")
    print(f"Explanation: {result.get('explanation', '')}")

    # 2. Explain SQL
    print("\n=== 2. Explain SQL ===")
    explanation = assistant.explain_sql("""
        SELECT d.name, COUNT(e.id) AS cnt, AVG(e.salary) AS avg_sal
        FROM department d
        LEFT JOIN employee e ON d.id = e.department_id
        WHERE e.status = 1
        GROUP BY d.name
        HAVING COUNT(e.id) > 5
        ORDER BY avg_sal DESC
        LIMIT 10
    """)
    print(explanation)

    # 3. Optimize SQL
    print("\n=== 3. Optimize SQL ===")
    opt = assistant.optimize_sql("""
        SELECT * FROM orders WHERE user_id IN (
            SELECT user_id FROM users WHERE status = 1
        )
    """)
    print(f"Optimized: {opt.get('optimized_sql', '')}")
    for change in opt.get("changes", []):
        print(f"  - {change.get('what', '')}: {change.get('why', '')}")

    assistant.close()


def demo_agent():
    """Agent workflow — with database connection."""
    # Configure database (optional)
    db_config = DBConfig(
        db_type="dm",
        host="localhost",
        port=5236,
        name="mydb",
        user="SYSDBA",
        password="password",
    )

    agent = SQLAgent(
        provider_name="glm",
        db_config=db_config,
        dialect=DialectType.DM,
    )

    # Run complete workflow: decompose → generate → execute → analyze
    result = agent.run("分析上个月的销售趋势，找出Top10客户及消费金额")
    print(f"Understanding: {result['understanding']}")
    print(f"Sub-tasks: {len(result['sub_tasks'])}")
    print(f"Summary:\n{result['summary']}")

    agent.close()


if __name__ == "__main__":
    demo_assistant()
