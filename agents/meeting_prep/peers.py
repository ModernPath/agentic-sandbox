"""Calls to other agents' command-line tools. Meeting prep never reads their tables.

Each call runs `python -m <module> ...` in a subprocess without a shell, with the environment filtered
the same way as the chat's command tool, a timeout, and JSON on stdout. Errors are fixed messages.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Callable, Mapping

from sandbox_host.cli_bridge import cli_env

TIMEOUT_SECONDS = 30
MAX_OUTPUT_CHARS = 200_000
RADAR_STATUSES = ("new", "reviewed")


class PeerError(RuntimeError):
    """Another agent's command failed. The message is safe to show."""


def run_peer(module: str, args: list, environ: Mapping[str, str]):
    argv = [sys.executable, "-m", module, *args]
    try:
        proc = subprocess.run(argv, env=cli_env(environ), capture_output=True, text=True,
                              timeout=TIMEOUT_SECONDS, shell=False, check=False)
    except subprocess.TimeoutExpired:
        raise PeerError("The other agent's command timed out.") from None
    if len(proc.stdout or "") > MAX_OUTPUT_CHARS:
        raise PeerError("The other agent's command printed too much output.")
    try:
        envelope = json.loads(proc.stdout or "null")
    except ValueError:
        envelope = None
    if not isinstance(envelope, dict):
        raise PeerError("The other agent's command did not return JSON.")
    if not envelope.get("ok"):
        raise PeerError("The other agent's command failed.")
    return envelope.get("result")


def radar_signals(environ: Mapping[str, str]) -> Callable[[], list]:
    """New and reviewed signals from the sales radar (competitor_watch)."""
    def signals() -> list:
        items: list = []
        for status in RADAR_STATUSES:
            items.extend(run_peer("competitor_watch.cli", ["signals", "--status", status], environ) or [])
        return items
    return signals


def read_notes(environ: Mapping[str, str]) -> Callable[[str], dict]:
    """The text of a file uploaded to file_reader."""
    def notes(file_id: str) -> dict:
        result = run_peer("file_reader.cli", ["read", "--id", file_id], environ) or {}
        return {"id": result.get("id", file_id), "filename": result.get("filename", ""), "text": result.get("text", "")}
    return notes
