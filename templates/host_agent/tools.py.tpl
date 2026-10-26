"""Model-callable tools for $Title. Each tool calls one service function.

Parameter types come from the signatures and descriptions from the docstrings (tool_from_function).
Errors are returned as data ({"error": ...}), never raised into the model loop.
"""

from __future__ import annotations

from typing import Callable, Optional

from sandbox_blocks.tools import Tool, tool_from_function

from . import service


def build_tools(store, on_call: Optional[Callable[[str], None]] = None) -> list[Tool]:
    def create_item(title: str, body: str = "") -> dict:
        """Create an item with a title and optional details."""
        return _safe(lambda: service.create_item(store, title, body))

    def list_items() -> dict:
        """List items, newest first."""
        return _safe(lambda: {"items": service.list_items(store)})

    def set_status(item_id: str, status: str) -> dict:
        """Set an item's status to open or done, using its exact id."""
        return _safe(lambda: {"updated": service.set_status(store, item_id, status)})

    functions = [create_item, list_items, set_status]
    return [tool_from_function(fn, on_call=on_call) for fn in functions]


def _safe(call):
    try:
        return call()
    except (ValueError, LookupError, RuntimeError) as error:
        return {"error": str(error)}
