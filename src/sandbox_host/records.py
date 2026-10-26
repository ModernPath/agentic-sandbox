"""Small, safe record helpers for agent tables.

Table and column names must be simple identifiers (lowercase letters, digits, underscores).
Values are always bound parameters. Agents may use these helpers or write their own SQL,
but the same rules apply to their tables.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
ORDER_BY = re.compile(r"^[a-z_][a-z0-9_]*( DESC| ASC)?$")


def _identifier(name: str) -> str:
    if not isinstance(name, str) or not IDENTIFIER.match(name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return name


def insert(engine: Engine, table: str, row: dict) -> dict:
    table = _identifier(table)
    columns = [_identifier(c) for c in row]
    placeholders = ", ".join(f":{c}" for c in columns)
    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"), row)
    return dict(row)


def fetch_one(engine: Engine, table: str, where: dict) -> Optional[dict]:
    rows = _select(engine, table, where, order_by=None, limit=1)
    return rows[0] if rows else None


def fetch_many(engine: Engine, table: str, where: Optional[dict] = None, order_by: str = "created_at DESC",
               limit: int = 100) -> list[dict]:
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    if not ORDER_BY.match(order_by or ""):
        raise ValueError(f"Invalid order_by: {order_by!r}")
    return _select(engine, table, where or {}, order_by=order_by, limit=limit)


def update(engine: Engine, table: str, id_value: Any, values: dict) -> bool:
    table = _identifier(table)
    if not values:
        raise ValueError("Nothing to update")
    columns = [_identifier(c) for c in values]
    assignments = ", ".join(f"{c} = :v_{c}" for c in columns)
    params = {f"v_{c}": values[c] for c in columns}
    params["id"] = id_value
    with engine.begin() as conn:
        result = conn.execute(text(f"UPDATE {table} SET {assignments} WHERE id = :id"), params)
    return result.rowcount > 0


def _select(engine: Engine, table: str, where: dict, *, order_by: Optional[str], limit: int) -> list[dict]:
    table = _identifier(table)
    columns = [_identifier(c) for c in where]
    clause = " AND ".join(f"{c} = :w_{c}" for c in columns)
    params = {f"w_{c}": where[c] for c in columns}
    sql = f"SELECT * FROM {table}"
    if clause:
        sql += f" WHERE {clause}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    sql += " LIMIT :limit"
    params["limit"] = limit
    with engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(text(sql), params)]
