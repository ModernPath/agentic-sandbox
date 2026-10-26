"""Command line for research brief. Prints one JSON object: {"ok": true, "result": ...} or {"ok": false, "error": ...}.

  python -m research_brief.cli research "solar storage costs 2026"
  python -m research_brief.cli list
  python -m research_brief.cli get --id ID

Exit codes: 0 success, 1 error, 2 bad usage. The shared database comes from DATABASE_URL.
Other agents call this command as a subagent (separate process, JSON on stdout, timeout).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional, Sequence

from sandbox_blocks.config import Settings
from sandbox_blocks.llm import build_llm
from sandbox_blocks.readers import build_reader
from sandbox_blocks.search import build_search

from . import service
from .store import BriefStore


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # keep our exit codes; argparse would exit 2 without JSON
        raise _UsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="research_brief.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    research = commands.add_parser("research")
    research.add_argument("topic")
    commands.add_parser("list")
    get = commands.add_parser("get")
    get.add_argument("--id", required=True)
    return parser


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str))


def main(argv: Optional[Sequence[str]] = None, engine=None, search=None, llm=None, read_page=None) -> int:
    try:
        args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    except _UsageError as error:
        print(f"usage error: {error}", file=sys.stderr)
        return 2
    if engine is None:
        url = os.environ.get("DATABASE_URL", "")
        if not url:
            _emit({"ok": False, "error": "DATABASE_URL is not set"})
            return 1
        from sqlalchemy import create_engine

        engine = create_engine(url, pool_pre_ping=True)
    store = BriefStore(engine)
    try:
        if args.command == "research":
            if search is None or llm is None or read_page is None:
                settings = Settings.from_env(os.environ)
                search = search or build_search(settings)
                llm = llm or build_llm(settings)
                read_page = read_page or build_reader(settings).read
            result = service.run_brief(store, search, llm, read_page, args.topic)
        elif args.command == "list":
            result = service.list_briefs(store)
        else:
            result = service.get_brief(store, args.id)
    except (ValueError, LookupError) as error:
        _emit({"ok": False, "error": str(error)})
        return 1
    except Exception:  # keep details in logs, not on stdout
        _emit({"ok": False, "error": "Unexpected error. Check the agent logs."})
        return 1
    _emit({"ok": True, "result": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
