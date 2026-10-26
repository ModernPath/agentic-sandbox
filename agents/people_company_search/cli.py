"""Command line for people and company search. Prints one JSON object: {"ok": true, "result": ...} or {"ok": false, "error": ...}.

  python -m people_company_search.cli people "<query>"
  python -m people_company_search.cli company "<query>"

Exit codes: 0 success, 1 error, 2 bad usage. Each run is paid and capped; needs EXA_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from typing import Optional, Sequence

from sandbox_blocks.config import Settings
from sandbox_blocks.errors import ConfigurationError, ProviderError
from sandbox_blocks.exa_agent import ExaAgentClient

from . import service
from .schemas import clean_text


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # keep our exit codes and JSON output
        raise _UsageError(message)


def build_client(environ: Mapping[str, str]) -> ExaAgentClient:
    settings = Settings.from_env(environ)
    if not settings.exa_api_key:
        raise ConfigurationError("EXA_API_KEY is required for people and company search")
    return ExaAgentClient(api_key=settings.exa_api_key, effort=settings.exa_agent_effort,
                          max_cost_dollars=settings.exa_agent_max_cost_dollars,
                          timeout=settings.http_timeout_seconds)


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str))


def main(argv: Optional[Sequence[str]] = None, environ: Mapping[str, str] = os.environ, client=None) -> int:
    parser = _Parser(prog="people_company_search.cli")
    parser.add_argument("kind", choices=sorted(service.KINDS))
    parser.add_argument("query", nargs="+")
    try:
        args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    except _UsageError as error:
        print(f"usage error: {error}", file=sys.stderr)
        return 2
    try:
        agent = client if client is not None else build_client(environ)
        result = service.run_search(agent, args.kind, " ".join(args.query))
    except ValueError as error:
        _emit({"ok": False, "error": str(error)})
        return 1
    except ConfigurationError as error:
        _emit({"ok": False, "error": clean_text(error)})
        return 1
    except ProviderError:
        _emit({"ok": False, "error": "The search provider failed. Try again later."})
        return 1
    except Exception:  # keep details in logs, not on stdout
        _emit({"ok": False, "error": "Unexpected error. Check the agent logs."})
        return 1
    _emit({"ok": True, "result": result})
    return 0
