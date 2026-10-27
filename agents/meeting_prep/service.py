"""Use cases for meeting prep. The API, the model tools, and the CLI all call these functions.

Business rules live here and only here. Raise ValueError (bad input) or LookupError (missing item)
with a message that is safe to show.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sandbox_host.panels import panel

from . import prep
from .prep import MAX_SUMMARY, SECTIONS  # noqa: F401  (part of the service contract)

RETENTION_DAYS = 30
MAX_ATTENDEES = 10
MAX_NAME = 120
MAX_PURPOSE = 500
FILE_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")
RADAR_FAILED = "The sales radar could not be read."
NOTES_FAILED = "The notes file could not be read."
AGENT_PAGE = "/agents/meeting-prep/"


def prepare_brief(store, request: dict, *, search, read_page, llm, signals, notes,
                  now: Optional[datetime] = None) -> dict:
    """Research the company, gather radar signals and notes, and save a drafted brief."""
    details = _validate(request)
    now = now or datetime.now(timezone.utc)
    purge_expired(store, now=now)

    sources, gaps = prep.research(details["company"], search, read_page)
    try:
        found = prep.matching_signals(details["company"], signals(), first_number=len(sources) + 1)
    except Exception:  # the radar is optional; its error text stays out of the brief
        found, gaps = [], gaps + [RADAR_FAILED]
    notes_file, notes_text = None, None
    if details["notes_file_id"]:
        try:
            loaded = notes(details["notes_file_id"])
            notes_file = {"id": details["notes_file_id"], "filename": str(loaded.get("filename") or "")}
            notes_text = str(loaded.get("text") or "")
        except Exception:
            gaps.append(NOTES_FAILED)

    written = prep.draft(llm, details, sources, found, notes_text)
    record = {
        "id": str(uuid4()),
        "company": details["company"], "website": details["website"], "meeting_date": details["meeting_date"],
        "purpose": details["purpose"], "attendees": details["attendees"], "notes_file": notes_file,
        "summary": written["summary"], "reason": written["reason"],
        "sources": [{k: s[k] for k in ("number", "kind", "title", "url")} for s in sources]
        + [{"number": s["number"], "kind": "signal", "title": f"{s['competitor_name']}: {s['headline']}",
            "url": s["source_url"]} for s in found],
        "signals": found,
        "gaps": gaps,
        "provider": written["provider"], "model": written["model"],
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=RETENTION_DAYS)).isoformat(),
    }
    return store.save(record)


def list_briefs(store, limit: int = 50, now: Optional[datetime] = None) -> list[dict]:
    purge_expired(store, now=now)
    return store.list(limit=limit)


def get_brief(store, brief_id: str) -> dict:
    record = store.get(brief_id)
    if record is None:
        raise LookupError("Brief not found")
    return record


def delete_brief(store, brief_id: str) -> bool:
    """A person deletes a brief. Not offered to the chat."""
    if not store.delete(brief_id):
        raise LookupError("Brief not found")
    return True


def purge_expired(store, now: Optional[datetime] = None) -> int:
    return store.delete_expired((now or datetime.now(timezone.utc)).isoformat())


def summary_panel(store, now: Optional[datetime] = None) -> dict:
    recent = list_briefs(store, limit=5, now=now)
    return panel(
        "Meeting prep",
        metric={"label": "Briefs kept", "value": store.count()},
        items=[{"title": b["company"],
                "meta": f"Meeting {b['meeting_date']}" if b["meeting_date"] else b["created_at"][:10],
                "href": AGENT_PAGE} for b in recent],
        empty="No briefs yet.",
        action={"label": "Prepare a meeting", "href": AGENT_PAGE},
    )


def parse_attendees(text: str) -> list[dict]:
    """'Ana Silva (CTO); Ben Ode' -> [{'name': 'Ana Silva', 'role': 'CTO'}, {'name': 'Ben Ode', 'role': ''}]."""
    attendees = []
    for entry in re.split(r"[;\n]", text or ""):
        entry = entry.strip()
        if not entry:
            continue
        match = re.fullmatch(r"(.*?)\s*\(([^()]*)\)", entry)
        name, role = (match.group(1), match.group(2)) if match else (entry, "")
        attendees.append({"name": name.strip(), "role": role.strip()})
    return attendees


def _validate(request: dict) -> dict:
    company = str(request.get("company") or "").strip()
    if not 2 <= len(company) <= 120:
        raise ValueError("Company must be 2-120 characters")
    website = str(request.get("website") or "").strip() or None
    if website and (not re.match(r"^https?://[^\s]+$", website, re.IGNORECASE) or len(website) > 500):
        raise ValueError("Website must be an http(s) address")
    meeting_date = str(request.get("meeting_date") or "").strip() or None
    if meeting_date:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meeting_date):
                raise ValueError
            date.fromisoformat(meeting_date)
        except ValueError:
            raise ValueError("Meeting date must be YYYY-MM-DD") from None
    purpose = str(request.get("purpose") or "").strip()
    if len(purpose) > MAX_PURPOSE:
        raise ValueError("Purpose must be at most 500 characters")
    attendees = request.get("attendees") or []
    if isinstance(attendees, str):
        attendees = parse_attendees(attendees)
    if len(attendees) > MAX_ATTENDEES:
        raise ValueError("At most 10 attendees")
    cleaned = []
    for attendee in attendees:
        name = str(attendee.get("name") or "").strip()
        role = str(attendee.get("role") or "").strip()
        if not 1 <= len(name) <= MAX_NAME or len(role) > MAX_NAME:
            raise ValueError("Attendee name must be 1-120 characters and role at most 120")
        cleaned.append({"name": name, "role": role})
    notes_file_id = str(request.get("notes_file_id") or "").strip() or None
    if notes_file_id and not FILE_ID.match(notes_file_id):
        raise ValueError("Notes file id must be an id returned by the file upload")
    return {"company": company, "website": website, "meeting_date": meeting_date, "purpose": purpose,
            "attendees": cleaned, "notes_file_id": notes_file_id}
