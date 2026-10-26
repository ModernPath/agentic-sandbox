"""Command line for competitor watch. Prints one JSON object: {"ok": true, "result": ...} or {"ok": false, "error": ...}.

  python -m competitor_watch.cli add --name "Varex Imaging" [--website URL] [--note TEXT]
  python -m competitor_watch.cli list
  python -m competitor_watch.cli delete --id ID
  python -m competitor_watch.cli check [--id ID]
  python -m competitor_watch.cli signals [--status new|reviewed|dismissed] [--category C] [--importance I] [--competitor-id ID]
  python -m competitor_watch.cli review --id ID --status reviewed|dismissed

Exit codes: 0 success, 1 error, 2 bad usage. The shared database comes from DATABASE_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional, Sequence

from sandbox_blocks.config import Settings
from sandbox_blocks.errors import ConfigurationError
from sandbox_blocks.llm import build_llm
from sandbox_blocks.readers import build_reader
from sandbox_blocks.search import build_search

from . import service
from .store import CompetitorStore


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse would exit 2 after printing to stderr; keep our exit codes
        raise _UsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="competitor_watch.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("--name", required=True)
    add.add_argument("--website", default="")
    add.add_argument("--note", default="")
    commands.add_parser("list")
    delete = commands.add_parser("delete")
    delete.add_argument("--id", required=True)
    check = commands.add_parser("check")
    check.add_argument("--id", default="")
    signals = commands.add_parser("signals")
    signals.add_argument("--status", default="new")
    signals.add_argument("--category", default="")
    signals.add_argument("--importance", default="")
    signals.add_argument("--competitor-id", default="")
    review = commands.add_parser("review")
    review.add_argument("--id", required=True)
    review.add_argument("--status", required=True)
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
    store = CompetitorStore(engine)
    try:
        result = _dispatch(args, store, search, llm, read_page)
    except (ValueError, LookupError, ConfigurationError) as error:
        _emit({"ok": False, "error": str(error)})
        return 1
    except Exception:  # keep details in logs, not on stdout
        _emit({"ok": False, "error": "Unexpected error. Check the agent logs."})
        return 1
    _emit({"ok": True, "result": result})
    return 0


def _dispatch(args, store, search, llm, read_page):
    if args.command == "add":
        return service.add_competitor(store, args.name, args.website or None, args.note)
    if args.command == "list":
        return service.list_competitors(store)
    if args.command == "delete":
        if not service.delete_competitor(store, args.id):
            raise LookupError("Competitor not found")
        return {"deleted": True}
    if args.command == "check":
        if search is None or llm is None or read_page is None:
            settings = Settings.from_env(os.environ)
            search = search or build_search(settings)
            llm = llm or build_llm(settings)
            read_page = read_page or build_reader(settings).read
        return {"checked": service.run_check(store, search, llm, read_page, args.id or None)}
    if args.command == "signals":
        return service.list_signals(store, status=args.status, category=args.category or None,
                                    importance=args.importance or None, competitor_id=args.competitor_id or None)
    if args.command == "review":
        if not service.review_signal(store, args.id, args.status):
            raise LookupError("Signal not found")
        return {"status": args.status}
    raise ValueError(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
