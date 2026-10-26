"""Command line for the file reader. Prints one JSON object: {"ok": true, "result": ...} or {"ok": false, "error": ...}.

  python -m file_reader.cli upload --path ./targets.xlsx
  python -m file_reader.cli list
  python -m file_reader.cli read --id ID
  python -m file_reader.cli ask --id ID --question "..."
  python -m file_reader.cli describe --id ID [--prompt "..."]

Exit codes: 0 success, 1 error, 2 bad usage. The shared database comes from DATABASE_URL.
Model calls use the configured provider (SANDBOX_LLM_PROVIDER and its key).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

from sandbox_blocks.config import Settings
from sandbox_blocks.llm import build_llm

from . import service
from .store import FileStore


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # keep our exit codes; argparse would exit 2 without JSON
        raise _UsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="file_reader.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    upload = commands.add_parser("upload")
    upload.add_argument("--path", required=True)
    commands.add_parser("list")
    read = commands.add_parser("read")
    read.add_argument("--id", required=True)
    ask = commands.add_parser("ask")
    ask.add_argument("--id", required=True)
    ask.add_argument("--question", required=True)
    describe = commands.add_parser("describe")
    describe.add_argument("--id", required=True)
    describe.add_argument("--prompt", default="Describe this image.")
    return parser


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str))


def main(argv: Optional[Sequence[str]] = None, engine=None, llm=None) -> int:
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
    store = FileStore(engine)
    try:
        result = _dispatch(args, store, llm)
    except (ValueError, LookupError) as error:
        _emit({"ok": False, "error": str(error)})
        return 1
    except Exception:  # keep details in logs, not on stdout
        _emit({"ok": False, "error": "Unexpected error. Check the agent logs."})
        return 1
    _emit({"ok": True, "result": result})
    return 0


def _dispatch(args, store, llm):
    if args.command == "upload":
        path = Path(args.path)
        if not path.is_file():
            raise ValueError("File not found")
        return service.upload_file(store, path.name, path.read_bytes())
    if args.command == "list":
        return service.list_files(store)
    if args.command == "read":
        return service.read_file(store, args.id)
    if args.command in ("ask", "describe"):
        llm = llm or build_llm(Settings.from_env(os.environ))
        if args.command == "ask":
            return service.ask_file(store, llm, args.id, args.question)
        return service.describe_image(store, llm, args.id, args.prompt)
    raise ValueError(f"unknown command {args.command}")
