"""Database connector for SQL execution and schema inspection."""

import logging
import sqlite3
from typing import Dict, List, Optional, Tuple

from ..config import DBConfig
from .dialects import DialectType

logger = logging.getLogger(__name__)


def _resolve_dialect(db_type: Optional[str]) -> DialectType:
    mapping = {
        "dm": DialectType.DM,
        "mysql": DialectType.MYSQL,
        "postgres": DialectType.POSTGRES,
        "postgresql": DialectType.POSTGRES,
        "sqlite": DialectType.SQLITE,
    }
    if not db_type:
        return DialectType.STANDARD
    return mapping.get(db_type.lower(), DialectType.STANDARD)


class DBConnector:
    """Database connector supporting SQLite, DM, MySQL, PostgreSQL."""

    def __init__(self, config: DBConfig):
        self.config = config
        self.dialect = _resolve_dialect(config.db_type)
        self._connection = None

    def _connect(self):
        if self._connection:
            return self._connection
        db_type = self.config.db_type
        if db_type == "sqlite":
            # Use uri mode to support :memory: and file paths
            db_name = self.config.name or ":memory:"
            if db_name == ":memory:":
                # Use shared cache for :memory: so same connection is reused
                self._connection = sqlite3.connect(
                    "file::memory:?cache=shared", uri=True
                )
            else:
                self._connection = sqlite3.connect(db_name)
            self._connection.row_factory = sqlite3.Row
        elif db_type == "dm":
            import dmPython
            self._connection = dmPython.connect(
                user=self.config.user, password=self.config.password,
                server=self.config.host, port=self.config.port,
            )
        elif db_type == "mysql":
            import pymysql
            self._connection = pymysql.connect(
                host=self.config.host, port=self.config.port,
                user=self.config.user, password=self.config.password,
                database=self.config.name,
            )
        elif db_type in ("postgres", "postgresql"):
            import psycopg2
            self._connection = psycopg2.connect(
                host=self.config.host, port=self.config.port,
                user=self.config.user, password=self.config.password,
                dbname=self.config.name,
            )
        return self._connection

    def execute(self, sql: str, params: Optional[tuple] = None) -> Tuple[List[Dict], List[str]]:
        """Execute SQL and return (rows as dicts, column names).
        Supports multiple statements separated by semicolons — executes them sequentially.
        Returns results from the last statement that produces output.
        """
        import re as _re
        conn = self._connect()
        cursor = conn.cursor()
        try:
            # Split into individual statements (ignore empty ones and comments)
            statements = []
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt and not stmt.startswith("--"):
                    statements.append(stmt)

            if not statements:
                return [], []

            rows, columns = [], []
            for stmt in statements:
                cursor.execute(stmt, params or ())
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.commit()
            return rows, columns
        except Exception as e:
            conn.rollback()
            raise

    def get_tables(self) -> List[str]:
        conn = self._connect()
        cursor = conn.cursor()
        if self.config.db_type == "sqlite":
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        elif self.config.db_type == "dm":
            cursor.execute("SELECT TABLE_NAME FROM ALL_TABLES WHERE OWNER = USER")
        elif self.config.db_type == "mysql":
            cursor.execute("SHOW TABLES")
        elif self.config.db_type in ("postgres", "postgresql"):
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        return [row[0] for row in cursor.fetchall()]

    def get_table_schema(self, table_name: str) -> Dict:
        conn = self._connect()
        cursor = conn.cursor()
        if self.config.db_type == "sqlite":
            cursor.execute(f"PRAGMA table_info(\"{table_name}\")")
            columns = []
            for row in cursor.fetchall():
                # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
                columns.append({
                    "name": row[1], "type": row[2],
                    "length": None, "nullable": not row[3],
                })
        elif self.config.db_type == "dm":
            cursor.execute(
                "SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE "
                "FROM ALL_TAB_COLUMNS WHERE TABLE_NAME = :1 AND OWNER = USER",
                (table_name.upper(),),
            )
            columns = [{"name": row[0], "type": row[1], "length": row[2], "nullable": row[3] in ("Y", "YES")} for row in cursor.fetchall()]
        elif self.config.db_type == "mysql":
            cursor.execute(f"DESCRIBE `{table_name}`")
            columns = [{"name": row[0], "type": row[1], "length": None, "nullable": row[3] == "YES"} for row in cursor.fetchall()]
        elif self.config.db_type in ("postgres", "postgresql"):
            cursor.execute(
                "SELECT column_name, data_type, character_maximum_length, is_nullable "
                "FROM information_schema.columns WHERE table_name = %s",
                (table_name,),
            )
            columns = [{"name": row[0], "type": row[1], "length": row[2], "nullable": row[3] in ("YES",)} for row in cursor.fetchall()]
        else:
            columns = []
        return {"table": table_name, "columns": columns}

    def get_schema_context(self, tables: Optional[List[str]] = None) -> str:
        try:
            table_list = tables or self.get_tables()
        except Exception:
            table_list = []
        if not table_list:
            return ""
        parts = ["Database schema:"]
        for t in table_list[:20]:
            try:
                schema = self.get_table_schema(t)
                if schema and schema.get("columns"):
                    cols = ", ".join(f"{c['name']}({c['type']})" for c in schema["columns"])
                    parts.append(f"  {t}: {cols}")
            except Exception:
                pass
        return "\n".join(parts)

    def close(self):
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None
