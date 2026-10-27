"""Storage for meeting prep briefs, through the sandbox record helpers (whitelisted names, bound values)."""

import json

from sqlalchemy import text

from sandbox_host.records import fetch_many, fetch_one, insert

TABLE = "meeting_prep_briefs"
JSON_FIELDS = ("attendees", "notes_file", "sources", "signals", "gaps")


class MeetingPrepStore:
    def __init__(self, engine):
        self.engine = engine

    def save(self, record: dict) -> dict:
        row = {key: value for key, value in record.items() if key not in JSON_FIELDS}
        row.update({f"{key}_json": json.dumps(record[key], ensure_ascii=False) for key in JSON_FIELDS})
        insert(self.engine, TABLE, row)
        return record

    def list(self, limit: int = 100) -> list[dict]:
        return [_record(row) for row in fetch_many(self.engine, TABLE, order_by="created_at DESC", limit=limit)]

    def count(self) -> int:
        with self.engine.connect() as conn:
            return conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar_one()

    def get(self, brief_id: str):
        row = fetch_one(self.engine, TABLE, {"id": brief_id})
        return _record(row) if row else None

    def delete(self, brief_id: str) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(text(f"DELETE FROM {TABLE} WHERE id = :id"), {"id": brief_id}).rowcount > 0

    def delete_expired(self, now_iso: str) -> int:
        with self.engine.begin() as conn:
            return conn.execute(text(f"DELETE FROM {TABLE} WHERE expires_at <= :now"), {"now": now_iso}).rowcount


def _record(row: dict) -> dict:
    record = {key: value for key, value in row.items() if not key.endswith("_json")}
    record.update({key: json.loads(row[f"{key}_json"]) for key in JSON_FIELDS})
    return record
