import pytest

from sandbox_blocks.config import Settings
from sandbox_blocks.errors import ConfigurationError, ProviderError
from sandbox_blocks.exa_agent import ExaAgentClient

SCHEMA = {"type": "object", "properties": {"people": {"type": "array", "maxItems": 25}}}


class ScriptedTransport:
    """Returns scripted responses in order and records every call."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": body})
        return self.responses.pop(0)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def monotonic(self):
        return self.now


def run_object(status, **extra):
    return {"id": "agent_run_01", "status": status, **extra}


def completed(output=None):
    default = {"structured": {"people": []}, "text": "", "grounding": []}
    return run_object("completed", output=output or default, costDollars=0.4, stopReason="schema_satisfied")


def client(transport, clock=None, **kwargs):
    clock = clock or FakeClock()
    return ExaAgentClient(api_key="ex-secret-key", transport=transport, sleep=clock.sleep,
                          clock=clock.monotonic, poll_seconds=4, max_wait_seconds=60, **kwargs)


def test_create_request_has_effort_schema_and_budget():  # X-1
    transport = ScriptedTransport(completed())
    client(transport).run("engineering leaders at AI infra companies", SCHEMA)
    call = transport.calls[0]
    assert call["url"] == "https://api.exa.ai/agent/runs"
    assert call["headers"]["x-api-key"] == "ex-secret-key"
    assert call["body"]["query"] == "engineering leaders at AI infra companies"
    assert call["body"]["effort"] == "auto"
    assert call["body"]["outputSchema"] == SCHEMA
    assert call["body"]["budget"] == {"maxCostDollars": 2}


def test_fixed_effort_sends_no_budget():  # X-2
    transport = ScriptedTransport(completed())
    client(transport, effort="high").run("q", SCHEMA)
    assert "budget" not in transport.calls[0]["body"]


def test_polls_until_completed_and_sleeps_between_polls():  # X-4
    transport = ScriptedTransport(run_object("running"), run_object("running"), completed())
    clock = FakeClock()
    result = client(transport, clock).run("q", SCHEMA)
    assert result.status == "completed"
    assert [c["url"] for c in transport.calls[1:]] == ["https://api.exa.ai/agent/runs/agent_run_01"] * 2
    assert clock.sleeps == [4, 4]


def test_never_terminal_times_out_with_provider_error():  # X-5
    transport = ScriptedTransport(*[run_object("running") for _ in range(100)])
    with pytest.raises(ProviderError, match="did not finish"):
        client(transport).run("q", SCHEMA)


def test_completed_run_returns_structured_output_cost_and_stop_reason():  # X-6
    response = completed(output={"structured": {"people": [{"name": "A"}]}, "text": "Two leads",
                                 "grounding": [{"url": "https://src.example/a"}]})
    result = client(ScriptedTransport(response)).run("q", SCHEMA)
    assert result.structured == {"people": [{"name": "A"}]}
    assert result.text == "Two leads"
    assert result.grounding == [{"url": "https://src.example/a"}]
    assert result.cost == 0.4 and result.stop_reason == "schema_satisfied"


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_failed_or_cancelled_run_raises_and_reads_no_output(status):  # X-7, X-8
    response = run_object(status, stopReason="error", output=None)
    with pytest.raises(ProviderError, match=f"{status}.*error"):
        client(ScriptedTransport(response)).run("q", SCHEMA)


def test_provider_error_never_contains_the_key():  # X-13
    response = run_object("failed", stopReason="error", error="upstream rejected ex-secret-key")
    with pytest.raises(ProviderError) as error:
        client(ScriptedTransport(response)).run("q", SCHEMA)
    assert "ex-secret-key" not in str(error.value)


@pytest.mark.parametrize("env", [
    {"SANDBOX_EXA_AGENT_EFFORT": "turbo"},
    {"SANDBOX_EXA_AGENT_MAX_COST_DOLLARS": "0"},
    {"SANDBOX_EXA_AGENT_MAX_COST_DOLLARS": "500"},
])
def test_invalid_agent_settings_are_rejected(env):  # X-3
    with pytest.raises(ConfigurationError):
        Settings.from_env(env)


def test_valid_agent_settings_load():
    settings = Settings.from_env({"SANDBOX_EXA_AGENT_EFFORT": "high", "SANDBOX_EXA_AGENT_MAX_COST_DOLLARS": "5"})
    assert settings.exa_agent_effort == "high"
    assert settings.exa_agent_max_cost_dollars == 5


def test_cost_breakdown_object_yields_total_and_keeps_breakdown():  # X-6 (breakdown form)
    response = completed()
    response["costDollars"] = {"total": 0.42, "search": 0.3, "llm": 0.12}
    result = client(ScriptedTransport(response)).run("q", SCHEMA)
    assert result.cost == 0.42
    assert result.cost_breakdown == {"total": 0.42, "search": 0.3, "llm": 0.12}


def test_cost_breakdown_without_total_sums_numeric_parts():  # X-6 (no total key)
    response = completed()
    response["costDollars"] = {"search": 0.3, "llm": 0.12, "note": "x"}
    result = client(ScriptedTransport(response)).run("q", SCHEMA)
    assert result.cost == pytest.approx(0.42)


def test_missing_cost_is_none_not_an_error():
    response = completed()
    del response["costDollars"]
    assert client(ScriptedTransport(response)).run("q", SCHEMA).cost is None
