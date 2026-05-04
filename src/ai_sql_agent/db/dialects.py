"""Database dialect definitions."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class DialectType(Enum):
    DM = "dm"
    MYSQL = "mysql"
    POSTGRES = "postgres"
    SQLITE = "sqlite"
    STANDARD = "standard"


@dataclass
class Dialect:
    name: str
    quote_char: str
    pagination: str
    current_time: str
    date_format: str
    boolean_type: str
    concat_func: str
    auto_increment: str

    @classmethod
    def get(cls, dialect_type: DialectType) -> "Dialect":
        return DIALECT_MAP[dialect_type]


DIALECT_MAP: Dict[DialectType, "Dialect"] = {
    DialectType.DM: Dialect(
        name="达梦(DM)", quote_char='"', pagination="limit_offset",
        current_time="SYSDATE",
        date_format="TO_CHAR({col}, 'YYYY-MM-DD HH24:MI:SS')",
        boolean_type="NUMBER(1)", concat_func="CONCAT",
        auto_increment="IDENTITY(1,1)",
    ),
    DialectType.MYSQL: Dialect(
        name="MySQL", quote_char="`", pagination="limit_offset",
        current_time="NOW()",
        date_format="DATE_FORMAT({col}, '%Y-%m-%d %H:%i:%s')",
        boolean_type="TINYINT(1)", concat_func="CONCAT",
        auto_increment="AUTO_INCREMENT",
    ),
    DialectType.POSTGRES: Dialect(
        name="PostgreSQL", quote_char='"', pagination="limit_offset",
        current_time="NOW()",
        date_format="TO_CHAR({col}, 'YYYY-MM-DD HH24:MI:SS')",
        boolean_type="BOOLEAN", concat_func="CONCAT",
        auto_increment="SERIAL",
    ),
    DialectType.SQLITE: Dialect(
        name="SQLite", quote_char='"', pagination="limit_offset",
        current_time="DATETIME('now')",
        date_format="STRFTIME('%Y-%m-%d %H:%M:%S', {col})",
        boolean_type="INTEGER", concat_func="||",
        auto_increment="AUTOINCREMENT",
    ),
    DialectType.STANDARD: Dialect(
        name="SQL Standard", quote_char='"', pagination="fetch",
        current_time="CURRENT_TIMESTAMP",
        date_format="CAST({col} AS VARCHAR)",
        boolean_type="BOOLEAN", concat_func="CONCAT",
        auto_increment="GENERATED ALWAYS AS IDENTITY",
    ),
}

# MySQL → 达梦 函数映射
DM_FUNCTION_MAP = {
    "DATE_FORMAT": "TO_CHAR", "STR_TO_DATE": "TO_DATE",
    "IFNULL": "NVL", "GROUP_CONCAT": "WM_CONCAT",
}


def convert_to_dm(sql: str) -> str:
    """Convert standard/MySQL SQL to DM-compatible SQL."""
    result = sql
    for mysql_func, dm_func in DM_FUNCTION_MAP.items():
        result = result.replace(mysql_func + "(", dm_func + "(")
    result = result.replace("`", '"')
    return result
