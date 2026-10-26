"""Shared database engine and a safe status check."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def database_status(engine: Optional[Engine]) -> str:
    """Return ok, error, or not_configured. Never returns driver messages."""
    if engine is None:
        return "not_configured"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:  # driver errors can contain credentials or hosts; do not expose them
        return "error"
    return "ok"
