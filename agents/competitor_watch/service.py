"""Competitor watch and sales radar use cases. The API, the chat tools, and the CLI all call these functions."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlsplit

from sandbox_host.panels import panel

from .enrich import CATEGORIES, ENRICH_SYSTEM, IMPORTANCE, build_prompt, parse_signals
from .summarise import safe_sources, search_query

logger = logging.getLogger("competitor_watch")
MAX_PAGES_READ = 3
MAX_RESULTS = 5
CHECK_FAILED = "The check could not run for this competitor. Try again later."
STATUSES = ("new", "reviewed", "dismissed")
REVIEW_STATUSES = ("reviewed", "dismissed")


class DuplicateError(ValueError):
    """A competitor with this name already exists."""


def add_competitor(store, name: str, website: Optional[str], note: str) -> dict:
    name = (name or "").strip()
    if len(name) < 2 or len(name) > 120:
        raise ValueError("Name must be 2-120 characters")
    if len(note or "") > 500:
        raise ValueError("Note must be at most 500 characters")
    website = (website or "").strip() or None
    if website is not None:
        parts = urlsplit(website)
        if parts.scheme not in ("http", "https") or not parts.netloc or len(website) > 300:
            raise ValueError("Website must be an http or https address")
    try:
        return store.add_competitor(name, website, note or "")
    except ValueError as error:
        raise DuplicateError(str(error)) from None


def list_competitors(store) -> list[dict]:
    return store.competitors()


def delete_competitor(store, competitor_id: str) -> bool:
    return store.delete_competitor(competitor_id)


def run_check(store, search, llm, read_page, competitor_id: Optional[str] = None) -> int:
    if search is None or llm is None:
        raise RuntimeError("Search and model must be configured to run a check")
    if competitor_id:
        target = store.competitor(competitor_id)
        if target is None:
            raise LookupError("Competitor not found")
        competitors = [target]
    else:
        competitors = store.competitors()
    for competitor in competitors:
        _check_one(store, search, llm, read_page, competitor)
    return len(competitors)


def _check_one(store, search, llm, read_page, competitor: dict) -> None:
    """One competitor: search, skip seen URLs, read a few pages, enrich, store signals and a check record."""
    competitor_id = competitor["id"]
    try:
        results = list(search.search(search_query(competitor["name"]), max_results=MAX_RESULTS).results)
    except Exception:  # provider text can contain keys or upstream details; never store it
        store.add_check(competitor_id, "error", 0)
        return
    snippets = {r.url: r.snippet for r in results}
    seen = store.seen_urls(competitor_id)
    candidates = [s for s in safe_sources(results) if s["url"] not in seen]
    if not candidates:
        store.add_check(competitor_id, "no_new_sources", 0)
        return
    material = []
    for index, source in enumerate(candidates):
        text = ""
        if index < MAX_PAGES_READ:
            try:
                text = read_page(source["url"]).text
            except Exception:  # a blocked page falls back to the search snippet
                text = ""
        material.append({"title": source["title"], "url": source["url"], "text": text or snippets.get(source["url"], "")})
    try:
        answer = llm.complete(build_prompt(competitor["name"], material), system=ENRICH_SYSTEM)
    except Exception:
        store.add_check(competitor_id, "error", 0)
        return
    parsed = parse_signals(answer.text, len(material))
    if not parsed:
        logger.warning("check competitor=%s results=%d fresh=%d output_chars=%d parsed=0 outcome=no_signals",
                    competitor_id, len(results), len(material), len(answer.text or ""))
        store.add_check(competitor_id, "no_signals", 0)
        return
    rows = []
    for signal in parsed:
        source = material[signal["source"] - 1]
        rows.append({"headline": signal["headline"], "category": signal["category"],
                     "importance": signal["importance"], "summary": signal["summary"],
                     "source_title": source["title"], "source_url": source["url"]})
    stored = store.add_signals(competitor, rows)
    outcome = "signals" if stored else "no_signals"
    logger.warning("check competitor=%s results=%d fresh=%d output_chars=%d parsed=%d stored=%d outcome=%s",
                competitor_id, len(results), len(material), len(answer.text or ""), len(parsed), stored, outcome)
    store.add_check(competitor_id, outcome, stored)


def list_signals(store, status: str = "new", category: Optional[str] = None, importance: Optional[str] = None,
                 competitor_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    if status not in STATUSES:
        raise ValueError("status must be new, reviewed, or dismissed")
    if category and category not in CATEGORIES:
        raise ValueError("Unknown category")
    if importance and importance not in IMPORTANCE:
        raise ValueError("Unknown importance")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    return [_signal(row) for row in store.signals(status=status, category=category, importance=importance,
                                                  competitor_id=competitor_id, limit=limit)]


def review_signal(store, signal_id: str, status: str) -> bool:
    if status not in REVIEW_STATUSES:
        raise ValueError("status must be reviewed or dismissed")
    return store.set_signal_status(signal_id, status)


def competitor_brief(store, competitor_id: str) -> dict:
    competitor = store.competitor(competitor_id)
    if competitor is None:
        raise LookupError("Competitor not found")
    new = [_signal(row) for row in store.signals(status="new", competitor_id=competitor_id, limit=100)]
    return {"competitor": {"id": competitor["id"], "name": competitor["name"]},
            "counts": dict(Counter(s["category"] for s in new)), "newest": new[:5]}


def dashboard(store, today: Optional[date] = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    days = [(today - timedelta(days=offset)).isoformat() for offset in range(13, -1, -1)]
    recent = store.signals_since((today - timedelta(days=29)).isoformat())
    by_day = Counter(row["created_at"][:10] for row in recent)
    week_start = (today - timedelta(days=6)).isoformat()
    last = store.last_checks()
    new_counts = store.new_counts()
    competitors = []
    for competitor in store.competitors():
        counts = new_counts.get(competitor["id"], {"total": 0, "high": 0})
        outcome, checked_at = last.get(competitor["id"], (None, None))
        competitors.append({"id": competitor["id"], "name": competitor["name"], "new_signals": counts["total"],
                            "new_high_signals": counts["high"], "last_outcome": outcome, "last_checked_at": checked_at})
    return {
        "kpis": {
            "watched_competitors": len(competitors),
            "new_signals": store.count_new(),
            "new_high_signals": store.count_new(high_only=True),
            "signals_7d": sum(1 for row in recent if row["created_at"][:10] >= week_start),
            "last_check_at": store.last_check_time(),
        },
        "by_category": dict(Counter(row["category"] for row in recent)),
        "daily": [{"day": day, "count": by_day.get(day, 0)} for day in days],
        "competitors": competitors,
        "latest": [_signal(row) for row in store.signals(status="new", limit=25)],
    }


def summary_panel(store) -> dict:
    latest = [_signal(row) for row in store.signals(status="new", limit=5)]
    return panel(
        "Sales radar",
        metric={"label": "New signals", "value": store.count_new()},
        items=[{"title": s["headline"], "meta": f"{s['competitor_name']} · {s['importance']}",
                "href": "/agents/competitor-watch/"} for s in latest],
        empty="No new signals. Run a check.",
        action={"label": "Open sales radar", "href": "/agents/competitor-watch/"},
    )


def _signal(row: dict) -> dict:
    return {"id": row["id"], "competitor_id": row["competitor_id"], "competitor_name": row["competitor_name"],
            "headline": row["headline"], "category": row["category"], "importance": row["importance"],
            "summary": row["summary"], "source_title": row["source_title"], "source_url": row["source_url"],
            "status": row["status"], "created_at": row["created_at"]}
