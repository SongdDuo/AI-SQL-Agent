"""SQL validator and auto-fixer for generated SQL queries."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .dialects import DialectType

logger = logging.getLogger(__name__)


class SQLValidationError:
    """Represents a SQL validation issue."""

    def __init__(self, level: str, message: str, suggestion: str = ""):
        self.level = level  # "error" | "warning" | "info"
        self.message = message
        self.suggestion = suggestion

    def __str__(self):
        return f"[{self.level.upper()}] {self.message}"


class SQLValidator:
    """Validates SQL queries for syntax and common issues."""

    # SQL injection patterns to detect
    DANGEROUS_PATTERNS = [
        r";\s*DROP\s+",
        r";\s*DELETE\s+",
        r";\s*UPDATE\s+.*\s+SET\s+",
        r";\s*INSERT\s+INTO\s+",
        r";\s*ALTER\s+",
        r";\s*CREATE\s+",
        r";\s*TRUNCATE\s+",
        r"--\s*$",
        r"/\*.*\*/",
        r"UNION\s+SELECT",
        r"EXEC\s*\(",
        r"xp_cmdshell",
    ]

    def __init__(self, dialect: DialectType = DialectType.STANDARD):
        self.dialect = dialect

    def validate(self, sql: str) -> Tuple[bool, List[SQLValidationError]]:
        """
        Validate a SQL query.

        Returns:
            (is_valid, list of issues)
        """
        issues: List[SQLValidationError] = []

        # 1. Basic syntax checks
        issues.extend(self._check_basic_syntax(sql))

        # 2. Injection detection
        issues.extend(self._check_injection(sql))

        # 3. SELECT-specific checks
        if sql.strip().upper().startswith("SELECT"):
            issues.extend(self._check_select(sql))

        # 4. Dialect-specific checks
        issues.extend(self._check_dialect(sql))

        has_errors = any(i.level == "error" for i in issues)
        return not has_errors, issues

    def _check_basic_syntax(self, sql: str) -> List[SQLValidationError]:
        issues = []
        # Check balanced parentheses
        open_count = sql.count("(")
        close_count = sql.count(")")
        if open_count != close_count:
            issues.append(SQLValidationError(
                "error",
                f"Unbalanced parentheses: {open_count} open, {close_count} close",
                "Check for missing ( or ) in your query"
            ))
        return issues

    def _check_injection(self, sql: str) -> List[SQLValidationError]:
        issues = []
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                issues.append(SQLValidationError(
                    "warning",
                    f"Potentially dangerous pattern detected: {pattern}",
                    "Ensure this is intentional and properly parameterized"
                ))
        return issues

    def _check_select(self, sql: str) -> List[SQLValidationError]:
        issues = []
        upper = sql.upper()

        # SELECT * warning
        if re.search(r"SELECT\s+\*", upper):
            issues.append(SQLValidationError(
                "warning",
                "SELECT * may return unnecessary columns",
                "Specify only the columns you need for better performance"
            ))

        # Missing WHERE on large tables (heuristic)
        if "WHERE" not in upper and "JOIN" not in upper:
            issues.append(SQLValidationError(
                "info",
                "No WHERE clause found — will scan all rows",
                "Add a WHERE clause to filter results if possible"
            ))

        # Check for N+1 pattern hints
        if "IN (SELECT" in upper:
            issues.append(SQLValidationError(
                "info",
                "Subquery IN (SELECT ...) may cause performance issues",
                "Consider using JOIN or EXISTS instead"
            ))

        return issues

    def _check_dialect(self, sql: str) -> List[SQLValidationError]:
        issues = []
        if self.dialect == DialectType.DM:
            # Check MySQL-specific functions in DM — treat as error since they will fail
            mysql_funcs = ["IFNULL", "DATE_FORMAT", "STR_TO_DATE", "GROUP_CONCAT"]
            for func in mysql_funcs:
                if func in sql.upper():
                    dm_map = {
                        "IFNULL": "NVL",
                        "DATE_FORMAT": "TO_CHAR",
                        "STR_TO_DATE": "TO_DATE",
                        "GROUP_CONCAT": "WM_CONCAT",
                    }
                    issues.append(SQLValidationError(
                        "error",
                        f"MySQL function {func} is not compatible with DM",
                        f"Use {dm_map.get(func, 'equivalent')} instead"
                    ))
        return issues


class SQLAutoFixer:
    """Attempts to automatically fix common SQL issues."""

    def __init__(self, dialect: DialectType = DialectType.STANDARD):
        self.dialect = dialect
        self.validator = SQLValidator(dialect)

    def fix(self, sql: str, error_message: str = "") -> Tuple[str, List[str]]:
        """
        Attempt to fix a SQL query.

        Returns:
            (fixed_sql, list of changes made)
        """
        fixed = sql
        changes: List[str] = []

        # Fix 1: Remove trailing semicolons
        if fixed.rstrip().endswith(";"):
            fixed = fixed.rstrip().rstrip(";").rstrip()
            changes.append("Removed trailing semicolon")

        # Fix 2: Fix common keyword casing
        fixed, casing_changes = self._fix_keyword_casing(fixed)
        changes.extend(casing_changes)

        # Fix 3: Fix dialect-specific functions
        fixed, dialect_changes = self._fix_dialect_functions(fixed)
        changes.extend(dialect_changes)

        # Fix 4: Fix unbalanced parentheses
        fixed, paren_changes = self._fix_parentheses(fixed)
        changes.extend(paren_changes)

        # Fix 5: Fix common syntax errors from error messages
        if error_message:
            fixed, err_changes = self._fix_from_error(fixed, error_message)
            changes.extend(err_changes)

        return fixed, changes

    def _fix_keyword_casing(self, sql: str) -> Tuple[str, List[str]]:
        changes = []
        keywords = [
            "select", "from", "where", "join", "left join", "right join",
            "inner join", "on", "group by", "order by", "having", "limit",
            "union", "insert", "update", "delete", "create", "drop", "alter",
        ]
        result = sql
        for kw in keywords:
            pattern = re.compile(r"\b" + kw + r"\b", re.IGNORECASE)
            if pattern.search(result) and not re.search(r"\b" + kw.upper() + r"\b", result):
                result = pattern.sub(kw.upper(), result)
                changes.append(f"Normalized keyword: {kw} → {kw.upper()}")
        return result, changes

    def _fix_dialect_functions(self, sql: str) -> Tuple[str, List[str]]:
        changes = []
        if self.dialect == DialectType.DM:
            func_map = {
                "IFNULL": "NVL",
                "DATE_FORMAT": "TO_CHAR",
                "STR_TO_DATE": "TO_DATE",
            }
            for old_func, new_func in func_map.items():
                if old_func in sql.upper():
                    sql = re.sub(
                        re.escape(old_func) + r"\(",
                        new_func + "(",
                        sql,
                        flags=re.IGNORECASE,
                    )
                    changes.append(f"Replaced {old_func}() with {new_func}() for DM dialect")
        return sql, changes

    def _fix_parentheses(self, sql: str) -> Tuple[str, List[str]]:
        changes = []
        open_count = sql.count("(")
        close_count = sql.count(")")
        if open_count > close_count:
            sql = sql + ")" * (open_count - close_count)
            changes.append(f"Added {open_count - close_count} closing parenthesis")
        elif close_count > open_count:
            # Remove extra closing parens from the end
            while sql.rstrip().endswith(")") and sql.count(")") > sql.count("("):
                sql = sql.rstrip()
                sql = sql[:-1].rstrip()
            changes.append("Removed extra closing parenthesis")
        return sql, changes

    def _fix_from_error(self, sql: str, error_msg: str) -> Tuple[str, List[str]]:
        changes = []
        err_lower = error_msg.lower()

        # "no such column" → suggest quoting
        if "no such column" in err_lower or "unknown column" in err_lower:
            changes.append("Column not found — check table schema for correct column names")

        # "syntax error near"
        if "syntax error" in err_lower:
            changes.append("Syntax error detected — review query structure")

        # "table not found"
        if "no such table" in err_lower or "table" in err_lower and "not found" in err_lower:
            changes.append("Table not found — check table name and schema")

        return sql, changes


def validate_and_fix(
    sql: str,
    dialect: DialectType = DialectType.STANDARD,
    error_message: str = "",
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Validate and auto-fix a SQL query.

    Returns:
        {
            "original_sql": str,
            "fixed_sql": str,
            "is_valid": bool,
            "issues": [str, ...],
            "changes": [str, ...],
            "retry_count": int,
        }
    """
    validator = SQLValidator(dialect)
    fixer = SQLAutoFixer(dialect)

    result = {
        "original_sql": sql,
        "fixed_sql": sql,
        "is_valid": False,
        "issues": [],
        "changes": [],
        "retry_count": 0,
    }

    current_sql = sql

    for attempt in range(max_retries):
        is_valid, issues = validator.validate(current_sql)
        result["issues"] = [str(i) for i in issues]

        if is_valid and not error_message:
            result["is_valid"] = True
            result["fixed_sql"] = current_sql
            result["retry_count"] = attempt
            return result

        # Try to fix
        fixed_sql, changes = fixer.fix(current_sql, error_message if attempt == 0 else "")
        if not changes:
            break  # Nothing to fix

        result["changes"].extend(changes)
        current_sql = fixed_sql
        result["fixed_sql"] = current_sql
        result["retry_count"] = attempt + 1

    # Final validation
    is_valid, issues = validator.validate(current_sql)
    result["is_valid"] = is_valid
    result["issues"] = [str(i) for i in issues]
    result["fixed_sql"] = current_sql

    return result
