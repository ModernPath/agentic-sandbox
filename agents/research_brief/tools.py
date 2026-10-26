"""Model-callable tools for research brief. Each tool calls one service function; errors come back as data."""

from __future__ import annotations

from typing import Callable, Optional

from sandbox_blocks.errors import ProviderError
from sandbox_blocks.tools import Tool, tool_from_function

from . import service


def build_tools(store, search, llm, read_page, on_call: Optional[Callable[[str], None]] = None) -> list[Tool]:
    def research_topic(topic: str) -> dict:
        """Search the web for a topic, read a few pages, and write a short summary with numbered citations. Takes a minute."""
        if search is None or llm is None:
            return {"error": "Search and model must be configured to research a topic."}
        return _safe(lambda: service.run_brief(store, search, llm, read_page, topic))

    def list_briefs() -> dict:
        """List previously written briefs, newest first."""
        return _safe(lambda: {"briefs": service.list_briefs(store)})

    def get_brief(brief_id: str) -> dict:
        """Get one brief by its exact id, with its summary and sources."""
        return _safe(lambda: service.get_brief(store, brief_id))

    functions = [research_topic, list_briefs, get_brief]
    return [tool_from_function(fn, on_call=on_call) for fn in functions]


def _safe(call):
    try:
        return call()
    except ProviderError:  # provider text can echo upstream details; the model gets a fixed message
        return {"error": "The model or search provider failed. Try again later."}
    except (ValueError, LookupError, RuntimeError) as error:
        return {"error": str(error)}
