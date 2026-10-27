"""Command line for meeting prep. Prints one JSON object: {"ok": true, "result": ...} or {"ok": false, "error": ...}.

  python -m meeting_prep.cli prepare --company "Acme" [--website URL] [--date YYYY-MM-DD] [--purpose TEXT]
                                     [--attendees "Ana Silva (CTO); Ben Ode (Buyer)"] [--notes-file-id ID]
  python -m meeting_prep.cli list
  python -m meeting_prep.cli get --id ID
  python -m meeting_prep.cli delete --id ID      (a person deletes; the chat cannot run this)
  python -m meeting_prep.cli purge               (removes briefs older than 30 days)

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
from .store import MeetingPrepStore


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # keep our exit codes; argparse would exit 2 without JSON
        raise _UsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="meeting_prep.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--company", required=True)
    prepare.add_argument("--website", default="")
    prepare.add_argument("--date", default="")
    prepare.add_argument("--purpose", default="")
    prepare.add_argument("--attendees", default="")
    prepare.add_argument("--notes-file-id", default="")
    commands.add_parser("list")
    get = commands.add_parser("get")
    get.add_argument("--id", required=True)
    delete = commands.add_parser("delete")
    delete.add_argument("--id", required=True)
    commands.add_parser("purge")
    return parser


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str))


def main(argv: Optional[Sequence[str]] = None, engine=None, **clients) -> int:
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
    store = MeetingPrepStore(engine)
    try:
        result = _dispatch(args, store, engine, clients)
    except (ValueError, LookupError) as error:
        _emit({"ok": False, "error": str(error)})
        return 1
    except Exception:  # keep details in logs, not on stdout
        _emit({"ok": False, "error": "Unexpected error. Check the agent logs."})
        return 1
    _emit({"ok": True, "result": result})
    return 0


def _dispatch(args, store, engine, clients):
    if args.command == "prepare":
        from .wiring import build_clients

        built = clients or build_clients(os.environ, engine)
        request = {"company": args.company, "website": args.website, "meeting_date": args.date,
                   "purpose": args.purpose, "attendees": args.attendees, "notes_file_id": args.notes_file_id}
        return service.prepare_brief(store, request, **built)
    if args.command == "list":
        return service.list_briefs(store)
    if args.command == "get":
        return service.get_brief(store, args.id)
    if args.command == "delete":
        return {"deleted": service.delete_brief(store, args.id)}
    if args.command == "purge":
        return {"purged": service.purge_expired(store)}
    raise ValueError(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
