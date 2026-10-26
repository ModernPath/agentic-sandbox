"""Command line for the EMEIA dashboard. Prints one JSON object: {"ok": true, "result": ...} or {"ok": false, "error": ...}.

  python -m emeia_dashboard.cli overview [--period 2026-Q4]
  python -m emeia_dashboard.cli target-add --period 2026-Q4 --objective "..." --key-result "..." --target 10 [--current 0] [--unit deals] [--owner "..."]
  python -m emeia_dashboard.cli target-update --id ID --current 4
  python -m emeia_dashboard.cli win-add --customer "..." --won-on 2026-10-05 [--description "..."] [--value 1200 --currency EUR]
  python -m emeia_dashboard.cli market-add --kind market|competitor --title "..." [--summary "..."] [--source-url URL]
  python -m emeia_dashboard.cli market-queue
  python -m emeia_dashboard.cli market-approve --id ID          (a person approves; agents do not run this)
  python -m emeia_dashboard.cli link-add --label "..." --url URL

Exit codes: 0 success, 1 error, 2 bad usage. The shared database comes from DATABASE_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional, Sequence

from sqlalchemy.engine import Engine

from . import service
from .store import DashboardStore


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # keep our exit codes; argparse would exit 2 without JSON
        raise _UsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="emeia_dashboard.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    overview = commands.add_parser("overview")
    overview.add_argument("--period", default=None)
    target = commands.add_parser("target-add")
    for name in ("--period", "--objective", "--key-result"):
        target.add_argument(name, required=True)
    target.add_argument("--target", type=float, required=True, dest="target_value")
    target.add_argument("--current", type=float, default=0, dest="current_value")
    target.add_argument("--unit", default="")
    target.add_argument("--owner", default="")
    update = commands.add_parser("target-update")
    update.add_argument("--id", required=True)
    update.add_argument("--current", type=float, required=True, dest="current_value")
    win = commands.add_parser("win-add")
    win.add_argument("--customer", required=True)
    win.add_argument("--won-on", required=True, dest="won_on")
    win.add_argument("--description", default="")
    win.add_argument("--value", type=float, default=None)
    win.add_argument("--currency", default="")
    market = commands.add_parser("market-add")
    market.add_argument("--kind", required=True, choices=["market", "competitor"])
    market.add_argument("--title", required=True)
    market.add_argument("--summary", default="")
    market.add_argument("--source-url", default=None)
    commands.add_parser("market-queue")
    approve = commands.add_parser("market-approve")
    approve.add_argument("--id", required=True)
    link = commands.add_parser("link-add")
    link.add_argument("--label", required=True)
    link.add_argument("--url", required=True)
    return parser


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str))


def main(argv: Optional[Sequence[str]] = None, engine: Optional[Engine] = None) -> int:
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
    store = DashboardStore(engine)
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
    if args.command == "overview":
        return service.overview(store, args.period)
    if args.command == "target-add":
        return service.add_target(store, {"period": args.period, "objective": args.objective,
                                          "key_result": args.key_result, "target_value": args.target_value,
                                          "current_value": args.current_value, "unit": args.unit,
                                          "owner": args.owner})
    if args.command == "target-update":
        return service.update_target(store, args.id, args.current_value)
    if args.command == "win-add":
        data = {"customer": args.customer, "won_on": args.won_on, "description": args.description,
                "currency": args.currency}
        if args.value is not None:
            data["value"] = args.value
        return service.add_win(store, data)
    if args.command == "market-add":
        return service.add_market_item(store, {"kind": args.kind, "title": args.title, "summary": args.summary,
                                               "source_url": args.source_url})
    if args.command == "market-queue":
        return {"items": service.review_queue(store)}
    if args.command == "market-approve":
        return service.approve_market_item(store, args.id)
    if args.command == "link-add":
        return service.add_tool_link(store, {"label": args.label, "url": args.url})
    raise ValueError(f"unknown command {args.command}")
