"""Apply each agent's plain SQL migrations once, in order, with checksums."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from sqlalchemy import text
from sqlalchemy.engine import Engine

TRACKER_DDL = """
CREATE TABLE IF NOT EXISTS sandbox_schema_migrations (
  agent TEXT NOT NULL,
  name TEXT NOT NULL,
  checksum TEXT NOT NULL,
  applied_at TEXT NOT NULL,
  PRIMARY KEY (agent, name)
)
"""
# Fixed key so concurrent hosts serialize their migration runs on PostgreSQL (decision D2).
ADVISORY_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtext('sandbox_schema_migrations'))"


class MigrationError(RuntimeError):
    """A migration file is missing, altered, or failed to apply."""


def apply_agent_migrations(engine: Engine, agent: str, directory: Union[str, Path]) -> list[str]:
    files = sorted(p for p in Path(directory).glob("*.sql") if not p.name.endswith(".down.sql"))
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            # Lock before creating the tracker: concurrent CREATE TABLE IF NOT EXISTS can race on PostgreSQL.
            conn.execute(text(ADVISORY_LOCK_SQL))
        conn.execute(text(TRACKER_DDL))

    pending = []
    for path in files:
        checksum = _checksum(path)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT checksum FROM sandbox_schema_migrations WHERE agent = :agent AND name = :name"),
                {"agent": agent, "name": path.name},
            ).first()
        if row is None:
            pending.append((path, checksum))
        elif row[0] != checksum:
            raise MigrationError(f"{agent}: {path.name} changed after it was applied; create a new migration instead")

    applied: list[str] = []
    for path, checksum in pending:
        if _apply_one(engine, agent, path, checksum):
            applied.append(path.name)
    return applied


def _apply_one(engine: Engine, agent: str, path: Path, checksum: str) -> bool:
    """Run one file in a transaction. Returns False when another host applied it first."""
    sql = path.read_text(encoding="utf-8")
    try:
        with engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                conn.execute(text(ADVISORY_LOCK_SQL))
                already = conn.execute(
                    text("SELECT 1 FROM sandbox_schema_migrations WHERE agent = :agent AND name = :name"),
                    {"agent": agent, "name": path.name},
                ).first()
                if already is not None:
                    return False  # another host applied it while we waited for the lock
            _execute_script(conn, sql)
            conn.execute(
                text("INSERT INTO sandbox_schema_migrations (agent, name, checksum, applied_at) "
                     "VALUES (:agent, :name, :checksum, :applied_at)"),
                {"agent": agent, "name": path.name, "checksum": checksum,
                 "applied_at": datetime.now(timezone.utc).isoformat()},
            )
        return True
    except Exception:  # SQLAlchemy or raw driver errors; generic reason only
        # The driver message can contain SQL fragments with data; keep the reason generic.
        raise MigrationError(f"{agent}: {path.name} failed to apply and was rolled back") from None


def _execute_script(conn, sql: str) -> None:
    if conn.dialect.name == "sqlite":
        conn.connection.dbapi_connection.executescript(sql)
    else:
        conn.exec_driver_sql(sql)


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
