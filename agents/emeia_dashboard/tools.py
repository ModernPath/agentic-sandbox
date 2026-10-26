"""Model-callable tools for the EMEIA dashboard. Each tool calls one service function.

Market items created by a model are always unreviewed. Approval is a human action and is not a tool.
"""

from __future__ import annotations

from typing import Callable, Optional

from sandbox_blocks.errors import ProviderError
from sandbox_blocks.tools import Tool, tool_from_function

from . import service


def build_tools(store, on_call: Optional[Callable[[str], None]] = None) -> list[Tool]:
    def show_overview(period: str = "") -> dict:
        """Show team targets, wins, approved market items, and tool links for a quarter such as 2026-Q4 (empty means this quarter)."""
        return _safe(lambda: service.overview(store, period or None))

    def add_target(period: str, objective: str, key_result: str, target_value: float, current_value: float = 0,
                   unit: str = "", owner: str = "") -> dict:
        """Add a team target (OKR key result) for a quarter such as 2026-Q4. Target value must be positive."""
        return _safe(lambda: service.add_target(store, {
            "period": period, "objective": objective, "key_result": key_result, "target_value": target_value,
            "current_value": current_value, "unit": unit, "owner": owner}))

    def update_target(target_id: str, current_value: float) -> dict:
        """Update the current value of a target by its exact id."""
        return _safe(lambda: service.update_target(store, target_id, current_value))

    def add_win(customer: str, won_on: str, description: str = "", value: float = -1, currency: str = "") -> dict:
        """Record a new customer or sales win. Date is ISO (YYYY-MM-DD). Value is optional: pass -1 when unknown."""
        data = {"customer": customer, "won_on": won_on, "description": description, "currency": currency}
        if value >= 0:
            data["value"] = value
        return _safe(lambda: service.add_win(store, data))

    def add_market_item(title: str, kind: str, summary: str = "", source_url: str = "") -> dict:
        """Add a market or competitor finding for human review. kind is market or competitor. It is not shown until a person approves it."""
        data = {"title": title, "kind": kind, "summary": summary, "source_url": source_url or None}
        return _safe(lambda: service.add_market_item(store, data))

    def list_review_queue() -> dict:
        """List market items waiting for a person to review."""
        return _safe(lambda: {"items": service.review_queue(store)})

    functions = [show_overview, add_target, update_target, add_win, add_market_item, list_review_queue]
    return [tool_from_function(fn, on_call=on_call) for fn in functions]


def _safe(call):
    try:
        return call()
    except ProviderError:
        return {"error": "The provider failed. Try again later."}
    except (ValueError, LookupError, RuntimeError) as error:
        return {"error": str(error)}
