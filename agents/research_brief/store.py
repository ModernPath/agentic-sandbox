"""Persistence for research briefs. Plain SQL through SQLAlchemy Core."""

import json

from sqlalchemy import text
from sqlalchemy.engine import Engine


class BriefStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    def save(self, record: dict) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("""INSERT INTO research_brief_briefs
                        (id, topic, summary, sources_json, skipped_json, reason, provider, model, created_at)
                        VALUES (:id, :topic, :summary, :sources_json, :skipped_json, :reason, :provider, :model,
                                :created_at)"""),
                {
                    "id": record["id"], "topic": record["topic"], "summary": record["summary"],
                    "sources_json": json.dumps(record["sources"]), "skipped_json": json.dumps(record["skipped"]),
                    "reason": record["reason"], "provider": record["provider"], "model": record["model"],
                    "created_at": record["created_at"],
                },
            )

    def list_recent(self, limit: int = 50) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM research_brief_briefs ORDER BY created_at DESC LIMIT :limit"),
                {"limit": limit},
            ).mappings().all()
        return [_row_to_record(row) for row in rows]

    def get(self, brief_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM research_brief_briefs WHERE id = :id"), {"id": brief_id}
            ).mappings().first()
        return _row_to_record(row) if row else None


def _row_to_record(row) -> dict:
    return {
        "id": row["id"], "topic": row["topic"], "summary": row["summary"],
        "sources": json.loads(row["sources_json"]), "skipped": json.loads(row["skipped_json"]),
        "reason": row["reason"], "provider": row["provider"], "model": row["model"],
        "created_at": row["created_at"],
    }
