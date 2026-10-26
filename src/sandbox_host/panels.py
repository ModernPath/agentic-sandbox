"""Panel contract for the sales home. Agents build panels with this helper so every card has one shape."""

from __future__ import annotations

from typing import Optional, Sequence

MAX_ITEMS = 5
MAX_TEXT = 200


def _text(value, limit: int = MAX_TEXT) -> str:
    return str(value if value is not None else "").strip()[:limit]


def _href(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    if value.startswith("/") and not value.startswith("//") and "\\" not in value and len(value) <= 300:
        return value
    return None


def panel(title: str, *, metric: Optional[dict] = None, items: Sequence[dict] = (),
          empty: str = "Nothing yet.", action: Optional[dict] = None) -> dict:
    cleaned_items = []
    for item in list(items)[:MAX_ITEMS]:
        cleaned_items.append({
            "title": _text(item.get("title")),
            "meta": _text(item.get("meta")),
            "href": _href(item.get("href")),
        })
    cleaned_metric = None
    if metric is not None:
        cleaned_metric = {"label": _text(metric.get("label"), 80), "value": metric.get("value")}
    cleaned_action = None
    if action is not None and _href(action.get("href")):
        cleaned_action = {"label": _text(action.get("label"), 80), "href": _href(action.get("href"))}
    return {
        "title": _text(title, 80),
        "metric": cleaned_metric,
        "items": cleaned_items,
        "empty": _text(empty, 200),
        "action": cleaned_action,
    }
