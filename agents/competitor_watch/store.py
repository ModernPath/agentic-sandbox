"""Storage for competitor watch: competitors, check runs, and signals in this agent's own tables."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from sandbox_host.records import fetch_many, fetch_one, insert


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CompetitorStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    # competitors
    def add_competitor(self, name: str, website, note: str) -> dict:
        row = {"id": str(uuid.uuid4()), "name": name.strip(), "name_key": name.strip().lower(), "website": website,
               "note": note, "created_at": _now()}
        try:
            return insert(self.engine, "competitor_watch_competitors", row)
        except IntegrityError:
            raise ValueError("A competitor with that name already exists") from None

    def competitors(self) -> list[dict]:
        return fetch_many(self.engine, "competitor_watch_competitors", order_by="name ASC", limit=500)

    def competitor(self, competitor_id: str):
        return fetch_one(self.engine, "competitor_watch_competitors", {"id": competitor_id})

    def delete_competitor(self, competitor_id: str) -> bool:
        with self.engine.begin() as conn:
            result = conn.execute(text("DELETE FROM competitor_watch_competitors WHERE id = :id"), {"id": competitor_id})
        return result.rowcount > 0

    # checks
    def add_check(self, competitor_id: str, outcome: str, new_signals: int) -> None:
        insert(self.engine, "competitor_watch_checks", {"id": str(uuid.uuid4()), "competitor_id": competitor_id,
                                                        "outcome": outcome, "new_signals": new_signals,
                                                        "created_at": _now()})

    def last_checks(self) -> dict:
        """competitor_id -> (outcome, created_at) of its most recent check."""
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT competitor_id, outcome, created_at FROM competitor_watch_checks"
                                     " ORDER BY created_at DESC")).all()
        latest = {}
        for competitor_id, outcome, created_at in rows:
            latest.setdefault(competitor_id, (outcome, created_at))
        return latest

    def last_check_time(self) -> Optional[str]:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT max(created_at) FROM competitor_watch_checks")).scalar()

    # signals
    def seen_urls(self, competitor_id: str) -> set:
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT source_url FROM competitor_watch_signals WHERE competitor_id = :c"),
                                {"c": competitor_id}).all()
        return {row[0] for row in rows}

    def add_signals(self, competitor: dict, signals: list) -> int:
        stored = 0
        for signal in signals:
            row = {"id": str(uuid.uuid4()), "competitor_id": competitor["id"], "competitor_name": competitor["name"],
                   "headline": signal["headline"], "category": signal["category"], "importance": signal["importance"],
                   "summary": signal["summary"], "source_title": signal["source_title"],
                   "source_url": signal["source_url"], "status": "new", "created_at": _now()}
            try:
                insert(self.engine, "competitor_watch_signals", row)
                stored += 1
            except IntegrityError:  # same source already stored for this competitor
                continue
        return stored

    def signals(self, status=None, category=None, importance=None, competitor_id=None, limit: int = 100) -> list:
        clauses, params = [], {"limit": limit}
        for column, value in (("status", status), ("category", category), ("importance", importance),
                              ("competitor_id", competitor_id)):
            if value:
                clauses.append(f"{column} = :{column}")
                params[column] = value
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.engine.connect() as conn:
            rows = conn.execute(text(f"SELECT * FROM competitor_watch_signals{where}"
                                     " ORDER BY created_at DESC LIMIT :limit"), params).mappings().all()
        return [dict(row) for row in rows]

    def signal(self, signal_id: str):
        return fetch_one(self.engine, "competitor_watch_signals", {"id": signal_id})

    def set_signal_status(self, signal_id: str, status: str) -> bool:
        with self.engine.begin() as conn:
            result = conn.execute(text("UPDATE competitor_watch_signals SET status = :status WHERE id = :id"),
                                  {"status": status, "id": signal_id})
        return result.rowcount > 0

    def new_counts(self) -> dict:
        """competitor_id -> {"total": new signals, "high": new high-importance signals}."""
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT competitor_id, count(*), sum(CASE WHEN importance = 'high' THEN 1 ELSE 0 END)"
                " FROM competitor_watch_signals WHERE status = 'new' GROUP BY competitor_id")).all()
        return {row[0]: {"total": int(row[1]), "high": int(row[2] or 0)} for row in rows}

    def signals_since(self, day: str) -> list:
        """(created_at, category) for every signal created on or after this UTC date (YYYY-MM-DD)."""
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT created_at, category FROM competitor_watch_signals"
                                     " WHERE substr(created_at, 1, 10) >= :day"), {"day": day}).all()
        return [{"created_at": row[0], "category": row[1]} for row in rows]

    def count_new(self, high_only: bool = False) -> int:
        sql = "SELECT count(*) FROM competitor_watch_signals WHERE status = 'new'"
        if high_only:
            sql += " AND importance = 'high'"
        with self.engine.connect() as conn:
            return int(conn.execute(text(sql)).scalar())
