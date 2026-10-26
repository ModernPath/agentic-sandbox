"""Token usage tracking for evals and cost reports.

track_usage() collects totals for every model call made inside the block (context-scoped,
so concurrent work does not mix). Provider usage field names are normalised here.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional

from .transport import JsonTransport

_current: contextvars.ContextVar[Optional["UsageTotals"]] = contextvars.ContextVar("sandbox_usage", default=None)


@dataclass
class UsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, usage: Any) -> None:
        self.calls += 1
        if not isinstance(usage, dict):
            return
        self.input_tokens += _first_int(usage, "input_tokens", "total_input_tokens", "prompt_tokens")
        self.output_tokens += _first_int(usage, "output_tokens", "total_output_tokens", "completion_tokens")


@contextmanager
def track_usage() -> Iterator[UsageTotals]:
    totals = UsageTotals()
    token = _current.set(totals)
    try:
        yield totals
    finally:
        _current.reset(token)


def metered(transport: JsonTransport) -> JsonTransport:
    """Wrap a transport so each response's usage is recorded for the active tracker, if any."""

    def wrapped(url, headers, body, timeout):
        payload = transport(url, headers, body, timeout)
        totals = _current.get()
        if totals is not None:
            totals.add(payload.get("usage") if isinstance(payload, dict) else None)
        return payload

    return wrapped


def _first_int(usage: dict, *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return 0
