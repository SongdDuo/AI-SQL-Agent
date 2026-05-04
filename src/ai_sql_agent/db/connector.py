"""Database connector for SQL execution and schema inspection."""

import logging
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
    """Database connector supporting DM, MySQL, PostgreSQL."""

    def __init__(self, config: DBConfig):
        self.config = config
        self.dialect = _resolve_dialect(config.db_type)
        self._connection = None

    def _connect(self):
        if self._connection:
            return self._connection
        db_type = self.config.db_type
        if db_type == "dm":
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
        """Execute SQL and return (rows as dicts, column names)."""
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params or ())
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return rows, columns
            conn.commit()
            return [], []
        except Exception as e:
            conn.rollback()
            raise

    def get_tables(self) -> List[str]:
        conn = self._connect()
        cursor = conn.cursor()
        if self.config.db_type == "dm":
            cursor.execute("SELECT TABLE_NAME FROM ALL_TABLES WHERE OWNER = USER")
        elif self.config.db_type == "mysql":
            cursor.execute("SHOW TABLES")
        elif self.config.db_type in ("postgres", "postgresql"):
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        return [row[0] for row in cursor.fetchall()]

    def get_table_schema(self, table_name: str) -> Dict:
        conn = self._connect()
        cursor = conn.cursor()
        if self.config.db_type == "dm":
            cursor.execute(
                "SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE "
                "FROM ALL_TAB_COLUMNS WHERE TABLE_NAME = :1 AND OWNER = USER",
                (table_name.upper(),),
            )
        elif self.config.db_type == "mysql":
            cursor.execute(f"DESCRIBE `{table_name}`")
        elif self.config.db_type in ("postgres", "postgresql"):
            cursor.execute(
                "SELECT column_name, data_type, character_maximum_length, is_nullable "
                "FROM information_schema.columns WHERE table_name = %s",
                (table_name,),
            )
        columns = []
        for row in cursor.fetchall():
            columns.append({
                "name": row[0], "type": row[1],
                "length": row[2], "nullable": row[3] in ("Y", "YES"),
            })
        return {"table": table_name, "columns": columns}

    def get_schema_context(self, tables: Optional[List[str]] = None) -> str:
        table_list = tables or self.get_tables()
        if not table_list:
            return ""
        parts = ["Database schema:"]
        for t in table_list[:20]:
            schema = self.get_table_schema(t)
            if schema and schema.get("columns"):
                cols = ", ".join(f"{c['name']}({c['type']})" for c in schema["columns"])
                parts.append(f"  {t}: {cols}")
        return "\n".join(parts)

    def close(self):
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None
