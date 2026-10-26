"""Research brief use cases. The API, the model tools, and the CLI all call these functions."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sandbox_host.panels import panel

from .brief import build_brief

MAX_SOURCES = 3
MAX_TOPIC = 300


def run_brief(store, search, llm, read_page, topic: str) -> dict:
    topic = (topic or "").strip()
    if not 1 <= len(topic) <= MAX_TOPIC:
        raise ValueError("Topic must be 1-300 characters")
    brief = build_brief(topic, search=search, read_page=read_page, llm=llm, max_sources=MAX_SOURCES)
    record = {
        "id": str(uuid4()),
        "topic": brief.topic,
        "summary": brief.summary,
        "sources": [{"number": s.number, "title": s.title, "url": s.url} for s in brief.sources],
        "skipped": list(brief.skipped),
        "reason": brief.reason,
        "provider": brief.provider,
        "model": brief.model,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    store.save(record)
    return record


def list_briefs(store, limit: int = 50) -> list[dict]:
    return store.list_recent(limit=limit)


def get_brief(store, brief_id: str) -> dict:
    record = store.get(brief_id)
    if record is None:
        raise LookupError("Brief not found")
    return record


def summary_panel(store) -> dict:
    recent = store.list_recent(limit=5)
    return panel(
        "Research briefs",
        metric={"label": "Briefs written", "value": len(store.list_recent(limit=500))},
        items=[{"title": b["topic"], "meta": b["created_at"][:10], "href": "/agents/research-brief/"} for b in recent],
        empty="No briefs yet.",
        action={"label": "Write a brief", "href": "/agents/research-brief/"},
    )
