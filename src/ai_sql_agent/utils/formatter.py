"""SQL formatting utilities."""

import re


def format_sql(sql: str) -> str:
    """Basic SQL formatting with proper indentation."""
    keywords = [
        "SELECT", "FROM", "WHERE", "JOIN", "LEFT JOIN", "RIGHT JOIN",
        "INNER JOIN", "OUTER JOIN", "CROSS JOIN", "ON", "GROUP BY",
        "ORDER BY", "HAVING", "LIMIT", "OFFSET", "UNION", "UNION ALL",
        "INSERT INTO", "UPDATE", "DELETE FROM", "SET", "VALUES",
        "CREATE TABLE", "ALTER TABLE", "DROP TABLE",
    ]
    result = sql.strip()
    for kw in keywords:
        pattern = r"\b" + re.escape(kw) + r"\b"
        result = re.sub(pattern, f"\n{kw}", result, flags=re.IGNORECASE)
    result = result.lstrip("\n")
    result = re.sub(r"\n{2,}", "\n", result)
    return result


def truncate_results(rows: list, max_rows: int = 20, max_col_width: int = 50) -> list:
    """Truncate result rows for display."""
    if len(rows) <= max_rows:
        return rows
    return rows[:max_rows]
