"""Model-callable tools for people and company search. Each call starts a paid, capped Exa Agent run."""

from __future__ import annotations

from typing import Callable, Optional

from sandbox_blocks.errors import ConfigurationError, ProviderError
from sandbox_blocks.tools import Tool, tool_from_function

from . import service


def build_tools(agent, on_call: Optional[Callable[[str], None]] = None) -> list[Tool]:
    def find_people(query: str) -> dict:
        """Find people by role, company, or topic. Each call is a paid web research run. Returns name, title, company, sources."""
        return _safe(lambda: service.run_search(agent, "people", query))

    def find_companies(query: str) -> dict:
        """Find companies by market, industry, or criteria. Each call is a paid web research run. Returns name, industry, sources."""
        return _safe(lambda: service.run_search(agent, "company", query))

    return [tool_from_function(fn, on_call=on_call) for fn in (find_people, find_companies)]


def _safe(call):
    try:
        return call()
    except ConfigurationError:
        return {"error": "People and company search is not configured."}
    except ProviderError:
        return {"error": "The search provider failed. Try again later."}
    except ValueError as error:
        return {"error": str(error)}
