"""Model-callable tools for the sales radar. Each tool calls one service function and returns data or an error."""

from __future__ import annotations

from typing import Callable, Optional

from sandbox_blocks.errors import ConfigurationError, ProviderError
from sandbox_blocks.tools import Tool, tool_from_function

from . import service


def build_tools(store, search, llm, read_page, on_call: Optional[Callable[[str], None]] = None) -> list[Tool]:

    def list_competitors() -> dict:
        """List the competitors being watched, with their ids."""
        return _safe(lambda: {"competitors": service.list_competitors(store)})

    def add_competitor(name: str, website: str = "", note: str = "") -> dict:
        """Start watching a competitor. Website is optional (http or https). Note is optional."""
        return _safe(lambda: service.add_competitor(store, name, website or None, note))

    def check_competitors(competitor_id: str = "") -> dict:
        """Search recent public news and store new signals. Pass a competitor id, or leave it empty to check all."""
        return _safe(lambda: {"checked": service.run_check(store, search, llm, read_page, competitor_id or None)})

    def list_signals(category: str = "", importance: str = "", competitor_id: str = "") -> dict:
        """List new signals, newest first. Filter by category (pricing, product, hiring, funding, partnership,
        leadership, customers, other), importance (high, medium, low), or competitor id."""
        return _safe(lambda: {"signals": service.list_signals(store, category=category or None,
                                                              importance=importance or None,
                                                              competitor_id=competitor_id or None)})

    def review_signal(signal_id: str, status: str) -> dict:
        """Mark a signal as reviewed or dismissed, by its exact id."""
        return _safe(lambda: {"updated": service.review_signal(store, signal_id, status)})

    def competitor_brief(competitor_id: str) -> dict:
        """What is new for one competitor: counts by category and its five newest new signals."""
        return _safe(lambda: service.competitor_brief(store, competitor_id))

    functions = [list_competitors, add_competitor, check_competitors, list_signals, review_signal, competitor_brief]
    return [tool_from_function(fn, on_call=on_call) for fn in functions]


def _safe(call):
    try:
        return call()
    except ConfigurationError:
        return {"error": "The model or search is not configured."}
    except ProviderError:
        return {"error": "The provider failed. Try again later."}
    except (ValueError, LookupError, RuntimeError) as error:
        return {"error": str(error)}
