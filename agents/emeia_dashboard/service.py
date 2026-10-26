"""EMEIA dashboard use cases. The API, the model tools, and the CLI all call these functions.

Validation rules live in models.py; the service applies them and turns failures into ValueError.
Approving a market item is a human step: it exists here and in the API and CLI, never as a model tool.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from pydantic import ValidationError

from sandbox_host.panels import panel

from .models import (MarketItemCreate, TargetCreate, TargetUpdate, ToolLinkCreate, WinCreate, current_period,
                     period_bounds)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validated(model, data: dict) -> dict:
    try:
        return model(**(data or {})).model_dump()
    except ValidationError as error:
        first = error.errors()[0]["msg"] if error.errors() else "Invalid input"
        raise ValueError(first.replace("Value error, ", "")) from None


def overview(store, period: Optional[str] = None) -> dict:
    period = period or current_period()
    start, end = period_bounds(period)
    targets = []
    for row in store.list_targets(period):
        progress = row["current_value"] / row["target_value"] if row["target_value"] > 0 else None
        targets.append({**row, "progress": progress})
    return {
        "period": period,
        "targets": targets,
        "wins": store.list_wins(start, end),
        "market_items": store.list_market_items(reviewed=True),
        "tool_links": store.list_tool_links(),
    }


def add_target(store, data: dict) -> dict:
    values = _validated(TargetCreate, data)
    record = {"id": str(uuid.uuid4()), **values, "created_at": _now(), "updated_at": _now()}
    store.create_target(record)
    return record


def update_target(store, target_id: str, current_value: float) -> dict:
    values = _validated(TargetUpdate, {"current_value": current_value})
    if not store.update_target_current(target_id, values["current_value"], _now()):
        raise LookupError("Target not found")
    return {"id": target_id, "current_value": values["current_value"]}


def add_win(store, data: dict) -> dict:
    values = _validated(WinCreate, data)
    values["won_on"] = values["won_on"].isoformat() if isinstance(values["won_on"], date) else values["won_on"]
    record = {"id": str(uuid.uuid4()), **values, "created_at": _now()}
    store.create_win(record)
    return record


def add_market_item(store, data: dict) -> dict:
    values = _validated(MarketItemCreate, data)
    record = {"id": str(uuid.uuid4()), **values, "reviewed": False, "created_at": _now()}
    store.create_market_item(record)
    return record


def review_queue(store) -> list[dict]:
    return store.list_market_items(reviewed=False)


def approve_market_item(store, item_id: str) -> dict:
    if not store.set_market_item_reviewed(item_id):
        raise LookupError("Market item not found")
    return {"id": item_id, "reviewed": True}


def add_tool_link(store, data: dict) -> dict:
    values = _validated(ToolLinkCreate, data)
    record = {"id": str(uuid.uuid4()), **values, "created_at": _now()}
    store.create_tool_link(record)
    return record


def summary_panel(store) -> dict:
    period = current_period()
    targets = store.list_targets(period)
    items = []
    for row in targets[:5]:
        progress = row["current_value"] / row["target_value"] if row["target_value"] > 0 else 0
        items.append({"title": f"{row['objective']}: {row['key_result']}",
                      "meta": f"{round(progress * 100)}% of target · {period}",
                      "href": "/agents/emeia-dashboard/"})
    return panel(
        "Team targets",
        metric={"label": f"Targets in {period}", "value": len(targets)},
        items=items,
        empty="No targets for this quarter yet.",
        action={"label": "Open dashboard", "href": "/agents/emeia-dashboard/"},
    )
