"""People and company search use cases. The CLI, model tools, and API all call these functions.

Each run is a paid Exa Agent list build with a cost cap. Results are untrusted web text and are cleaned before use.
"""

from __future__ import annotations

from .schemas import COMPANY_SCHEMA, PEOPLE_SCHEMA, clean_text

MAX_QUERY = 500
KINDS = {
    "people": ("people", PEOPLE_SCHEMA),
    "company": ("companies", COMPANY_SCHEMA),
}


def run_search(agent, kind: str, query: str) -> dict:
    if kind not in KINDS:
        raise ValueError("kind must be people or company")
    query = (query or "").strip()
    if not query:
        raise ValueError("query must not be empty")
    if len(query) > MAX_QUERY:
        raise ValueError(f"query must be at most {MAX_QUERY} characters")

    key, schema = KINDS[kind]
    result = agent.run(query, schema)
    raw_items = (result.structured or {}).get(key, [])
    items = [
        _item(kind, item, _citations_for(result.grounding, f"structured.{key}[{index}]"))
        for index, item in enumerate(raw_items)
    ]
    return {"kind": kind, "run_id": clean_text(result.run_id), "cost": result.cost, "items": items}


def _citations_for(grounding: list, field_path: str) -> list[str]:
    """URLs the run cited for one item, from grounding entries keyed by field path."""
    urls = []
    for entry in grounding or []:
        if entry.get("field") == field_path:
            urls.extend(c.get("url", "") for c in entry.get("citations") or [])
    return [u for u in urls if u]


def _item(kind: str, item: dict, citations: list[str]) -> dict:
    if kind == "people":
        fields = {"name": clean_text(item.get("name")), "job_title": clean_text(item.get("job_title")),
                  "company": clean_text(item.get("company"))}
        link = item.get("profile_url")
    else:
        fields = {"name": clean_text(item.get("name")), "industry": clean_text(item.get("industry"))}
        link = item.get("website")
    sources = [clean_text(u) for u in citations] or ([clean_text(link)] if link else [])
    return {**fields, "sources": sources}
