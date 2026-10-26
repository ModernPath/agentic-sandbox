"""Storage for $Title, through the sandbox record helpers (whitelisted names, bound values)."""

import uuid
from datetime import datetime, timezone

from sandbox_host.records import fetch_many, fetch_one, insert, update

TABLE = "${table}_items"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class $ClassStore:
    def __init__(self, engine):
        self.engine = engine

    def create(self, title: str, body: str) -> dict:
        row = {"id": str(uuid.uuid4()), "title": title, "body": body, "status": "open", "created_at": _now()}
        return insert(self.engine, TABLE, row)

    def list(self, limit: int = 100) -> list[dict]:
        return fetch_many(self.engine, TABLE, order_by="created_at DESC", limit=limit)

    def get(self, item_id: str):
        return fetch_one(self.engine, TABLE, {"id": item_id})

    def set_status(self, item_id: str, status: str) -> bool:
        return update(self.engine, TABLE, item_id, {"status": status})
