"""Command line for $Title. Prints one JSON object: {"ok": true, "result": ...} or {"ok": false, "error": ...}.

  python -m $module.cli create --title "..." [--body "..."]
  python -m $module.cli list
  python -m $module.cli status --id ID --value open|done

Exit codes: 0 success, 1 error, 2 bad usage. The shared database comes from DATABASE_URL.
Other agents can call this command as a subagent (separate process, JSON on stdout, timeout).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional, Sequence

from . import service
from .store import $ClassStore


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # keep our exit codes; argparse would exit 2 without JSON
        raise _UsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="$module.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--body", default="")
    commands.add_parser("list")
    status = commands.add_parser("status")
    status.add_argument("--id", required=True)
    status.add_argument("--value", required=True, choices=["open", "done"])
    return parser


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str))


def main(argv: Optional[Sequence[str]] = None, engine=None) -> int:
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
    store = $ClassStore(engine)
    try:
        result = _dispatch(args, store)
    except (ValueError, LookupError) as error:
        _emit({"ok": False, "error": str(error)})
        return 1
    except Exception:  # keep details in logs, not on stdout
        _emit({"ok": False, "error": "Unexpected error. Check the agent logs."})
        return 1
    _emit({"ok": True, "result": result})
    return 0


def _dispatch(args, store):
    if args.command == "create":
        return service.create_item(store, args.title, args.body)
    if args.command == "list":
        return service.list_items(store)
    if args.command == "status":
        return {"updated": service.set_status(store, args.id, args.value)}
    raise ValueError(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
