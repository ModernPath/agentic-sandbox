"""Append-only audit trail for the host and for agents' actions. Details are small JSON objects."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine

MAX_DETAIL_CHARS = 2000


def record(engine: Engine, *, actor: str, action: str, subject: str = "", detail: dict | None = None) -> None:
    encoded = json.dumps(detail or {}, ensure_ascii=False, default=str)[:MAX_DETAIL_CHARS]
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO sandbox_audit (id, actor, action, subject, detail_json, at) "
                          "VALUES (:id, :actor, :action, :subject, :detail, :at)"),
                     {"id": str(uuid.uuid4()), "actor": actor[:120], "action": action[:80],
                      "subject": subject[:200], "detail": encoded,
                      "at": datetime.now(timezone.utc).isoformat()})


def recent(engine: Engine, limit: int = 20) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, actor, action, subject, detail_json, at FROM sandbox_audit "
                                 "ORDER BY at DESC, id DESC LIMIT :limit"), {"limit": limit}).mappings().all()
    return [{"id": r["id"], "actor": r["actor"], "action": r["action"], "subject": r["subject"],
             "detail": json.loads(r["detail_json"] or "{}"), "at": r["at"]} for r in rows]
