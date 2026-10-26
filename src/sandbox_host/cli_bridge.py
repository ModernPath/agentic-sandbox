"""Run an agent's command-line tool from the chat: an allowlist, literal arguments, a timeout, and JSON out."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

MAX_ARGS = 12
MAX_ARG_CHARS = 200
TIMEOUT_SECONDS = 60
MAX_OUTPUT_CHARS = 20_000
ALLOWED_NAMES = ("PATH", "PYTHONPATH", "DATABASE_URL")
ALLOWED_PREFIXES = ("SANDBOX_", "GEMINI_", "OPENAI_", "AZURE_", "ANTHROPIC_", "EXA_", "XAIGROK_")
NOT_JSON = "The command did not return JSON."
TOO_LARGE = "The command printed too much output."


class CommandError(ValueError):
    """The command was refused before it ran."""


def cli_env(environ) -> dict:
    """Only the variables the agents need. Everything else stays out of the subprocess."""
    return {key: value for key, value in environ.items()
            if key in ALLOWED_NAMES or key.startswith(ALLOWED_PREFIXES)}


def default_pythonpath() -> str:
    src = Path(__file__).resolve().parents[1]
    return os.pathsep.join([str(src), str(src.parent / "agents")])


def run_command(spec, command: str, args: list, environ) -> dict:
    if spec.cli is None:
        raise CommandError("This agent has no command-line tool.")
    if command not in spec.cli.commands:
        raise CommandError(f"The command {command!r} is not allowed for {spec.name}.")
    if len(args) > MAX_ARGS or any(len(arg) > MAX_ARG_CHARS for arg in args):
        raise CommandError("Too many arguments, or an argument is too long.")
    argv = [sys.executable, "-m", spec.cli.module, command, *args]
    try:
        proc = subprocess.run(argv, env=cli_env(environ), capture_output=True, text=True,
                              timeout=TIMEOUT_SECONDS, shell=False, check=False)
    except subprocess.TimeoutExpired:
        raise CommandError("The command timed out.") from None
    if len(proc.stdout) > MAX_OUTPUT_CHARS:
        return {"ok": False, "error": TOO_LARGE}
    try:
        return json.loads(proc.stdout or "null") or {"ok": False, "error": NOT_JSON}
    except ValueError:
        return {"ok": False, "error": NOT_JSON}
