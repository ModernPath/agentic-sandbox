"""Exa Agent API client: create a run, poll to a terminal status, return its output.

Only a completed run yields output. Failed and cancelled runs raise ProviderError
with their status and stop reason, never with upstream error text.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .errors import ProviderError
from .transport import JsonTransport, urllib_transport

EXA_AGENT_RUNS_URL = "https://api.exa.ai/agent/runs"
TERMINAL_STATUSES = ("completed", "failed", "cancelled")
BUDGETED_EFFORTS = ("auto", "ultra")


@dataclass(frozen=True)
class AgentResult:
    run_id: str
    status: str
    structured: Optional[dict] = None
    text: str = ""
    grounding: list = field(default_factory=list)
    cost: Optional[float] = None
    stop_reason: Optional[str] = None
    cost_breakdown: Any = None


class ExaAgentClient:
    def __init__(self, *, api_key: str, transport: JsonTransport = urllib_transport, effort: str = "auto",
                 max_cost_dollars: float = 2.0, poll_seconds: float = 4, max_wait_seconds: float = 600,
                 timeout: float = 30, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        self.api_key = api_key
        self.transport = transport
        self.effort = effort
        self.max_cost_dollars = max_cost_dollars
        self.poll_seconds = poll_seconds
        self.max_wait_seconds = max_wait_seconds
        self.timeout = timeout
        self.sleep = sleep
        self.clock = clock

    def run(self, query: str, output_schema: dict) -> AgentResult:
        body: dict[str, Any] = {"query": query, "effort": self.effort, "outputSchema": output_schema}
        if self.effort in BUDGETED_EFFORTS:
            body["budget"] = {"maxCostDollars": self.max_cost_dollars}
        headers = {"x-api-key": self.api_key}
        run = self.transport(EXA_AGENT_RUNS_URL, headers, body, self.timeout)
        run_id = run["id"]
        started = self.clock()
        while run.get("status") not in TERMINAL_STATUSES:
            if self.clock() - started > self.max_wait_seconds:
                raise ProviderError(f"Exa agent run did not finish within {int(self.max_wait_seconds)} seconds")
            self.sleep(self.poll_seconds)
            run = self.transport(f"{EXA_AGENT_RUNS_URL}/{run_id}", headers, None, self.timeout)
        return _to_result(run_id, run)


def _to_result(run_id: str, run: dict) -> AgentResult:
    status = run["status"]
    stop_reason = run.get("stopReason")
    if status != "completed":
        raise ProviderError(f"Exa agent run {status}: stop reason {stop_reason or 'unknown'}")
    output = run.get("output") or {}
    return AgentResult(run_id=run_id, status=status, structured=output.get("structured"),
                       text=output.get("text") or "", grounding=list(output.get("grounding") or []),
                       cost=_total_cost(run.get("costDollars")), stop_reason=stop_reason,
                       cost_breakdown=run.get("costDollars"))


def _total_cost(value: Any) -> Optional[float]:
    """Exa reports costDollars as a breakdown; use its total, or sum its numeric parts."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        if isinstance(value.get("total"), (int, float)) and not isinstance(value.get("total"), bool):
            return float(value["total"])
        parts = [v for v in value.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        return float(sum(parts)) if parts else None
    return None
