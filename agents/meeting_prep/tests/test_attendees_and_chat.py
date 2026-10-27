"""Attendees appear in the brief text, and the chat can prepare a brief with a real tool call. Offline."""

import json

from meeting_prep.api import make_agent_spec
from meeting_prep_fakes import FakeLLM, FakeSearch, fake_notes, fake_reader, fake_signals
from sandbox_blocks.llm import LLMResponse
from sandbox_blocks.tools import ToolCall, ToolRun
from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.testing import memory_engine, signed_in_client
from test_service import NOW, prepare


class ScriptedLLM:
    """A chat model that calls the scripted tools through their real handlers."""
    provider = "fake"
    model = "fake-1"

    def __init__(self, script=(), reply="Done."):
        self.script = script
        self.reply = reply

    def complete(self, prompt, system=None):
        return LLMResponse(text="[]", provider="fake", model="fake-1")

    def complete_with_image(self, prompt, image, mime, system=None):
        raise AssertionError("not used")

    def run_with_tools(self, prompt, *, system=None, history=(), tools=(), max_calls=8):
        by_name = {t.name: t for t in tools}
        calls = []
        for name, args in self.script:
            result = by_name[name].handler(args)
            calls.append(ToolCall(name=name, arguments=args, result=result))
        return ToolRun(text=self.reply, provider="fake", model="fake-1", tool_calls=tuple(calls))


def test_mp20_attendees_are_a_section_of_the_brief(engine):  # MP-20
    brief = prepare(engine, {"company": "Acme", "attendees": [{"name": "Ana Silva", "role": "CTO"},
                                                             {"name": "Jo Lind", "role": ""}]})
    summary = brief["summary"]
    assert summary.startswith("## Company snapshot")
    assert "## Attendees" in summary
    assert "- Ana Silva, CTO" in summary and "- Jo Lind" in summary
    assert "No public background was checked" in summary


def test_mp21_no_attendees_means_no_attendees_section(engine):  # MP-21
    brief = prepare(engine, {"company": "Acme"})
    assert "## Attendees" not in brief["summary"]


def test_mp22_without_a_model_attendees_are_still_kept_and_no_summary_is_invented(engine):  # MP-22
    brief = prepare(engine, {"company": "Acme", "attendees": [{"name": "Ana Silva", "role": "CTO"}]}, llm=None)
    assert brief["summary"] is None and brief["attendees"] == [{"name": "Ana Silva", "role": "CTO"}]


def test_mp23_attendee_text_cannot_add_headings_to_the_brief(engine):  # MP-23
    brief = prepare(engine, {"company": "Acme", "attendees": [{"name": "Ana\n## Injected", "role": "CTO\n# Evil"}]})
    lines = brief["summary"].splitlines()
    assert "## Injected" not in lines and "# Evil" not in lines
    headings = [line for line in lines if line.startswith("#")]
    assert headings == ["## Company snapshot", "## Attendees"]


def test_mp24_chat_prepares_a_brief_through_the_agent_tool():  # MP-24
    llm = ScriptedLLM(script=(("meeting_prep__prepare_meeting", {"company": "Acme"}),), reply="Brief ready.")
    services = {
        "chat": {"llm": llm},
        "meeting_prep": {"search": FakeSearch(), "read_page": fake_reader(), "llm": FakeLLM(),
                         "signals": fake_signals(), "notes": fake_notes(), "now": NOW},
    }
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=memory_engine(),
                     services=services)
    client = signed_in_client(app)
    response = client.post("/api/chat", json={"message": "Prep me for Acme", "history": []})
    assert response.status_code == 200
    assert response.json()["tool_calls"] == ["meeting_prep__prepare_meeting"]
    briefs = client.get("/api/agents/meeting-prep/briefs").json()["briefs"]
    assert [b["company"] for b in briefs] == ["Acme"]
