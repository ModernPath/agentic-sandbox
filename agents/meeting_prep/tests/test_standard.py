"""Standard checks for Meeting Prep: service, tools, CLI, and API must agree (MP-15, MP-16).

These tests are part of the agent standard. Keep them passing when you add actions.
"""

import json

from meeting_prep import service
from meeting_prep.api import make_agent_spec
from meeting_prep.cli import main as cli_main
from meeting_prep.store import MeetingPrepStore
from meeting_prep.tools import build_tools
from meeting_prep_fakes import FakeLLM, FakeSearch, fake_notes, fake_reader, fake_signals

CLIENTS = dict(search=FakeSearch(), read_page=fake_reader(), llm=FakeLLM(), signals=fake_signals(),
               notes=fake_notes())


def tools_for(engine, **overrides):
    clients = dict(CLIENTS, **overrides)
    return {t.name: t for t in build_tools(MeetingPrepStore(engine), **clients)}


def test_tools_cover_the_chat_actions_with_typed_schemas(engine):  # MP-16
    tools = tools_for(engine)
    assert set(tools) == {"prepare_meeting", "list_briefs", "get_brief"}
    props = tools["prepare_meeting"].parameters["properties"]
    assert props["company"]["type"] == "string" and props["attendees"]["type"] == "string"
    assert tools["prepare_meeting"].parameters["required"] == ["company"]


def test_prepare_tool_parses_attendees_and_errors_come_back_as_data(engine):  # MP-16
    tools = tools_for(engine)
    brief = tools["prepare_meeting"].handler({"company": "Acme", "attendees": "Ana Silva (CTO)"})
    assert brief["attendees"] == [{"name": "Ana Silva", "role": "CTO"}]
    assert "error" in tools["prepare_meeting"].handler({"company": "A"})
    assert tools["get_brief"].handler({"brief_id": "missing"}) == {"error": "Brief not found"}


def test_cli_prints_json_and_exit_codes(engine, capsys):  # MP-15
    assert cli_main(["prepare", "--company", "Acme", "--attendees", "Ana Silva (CTO); Ben Ode",
                     "--date", "2026-10-30"], engine=engine, **CLIENTS) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True and envelope["result"]["meeting_date"] == "2026-10-30"
    assert len(envelope["result"]["attendees"]) == 2
    brief_id = envelope["result"]["id"]
    assert cli_main(["prepare", "--company", "A"], engine=engine, **CLIENTS) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
    assert cli_main(["prepare"], engine=engine) == 2
    capsys.readouterr()
    assert cli_main(["get", "--id", brief_id], engine=engine) == 0
    assert json.loads(capsys.readouterr().out)["result"]["id"] == brief_id
    assert cli_main(["purge"], engine=engine) == 0
    assert json.loads(capsys.readouterr().out)["result"] == {"purged": 0}
    assert cli_main(["delete", "--id", brief_id], engine=engine) == 0
    assert json.loads(capsys.readouterr().out)["result"] == {"deleted": True}
    assert cli_main(["delete", "--id", brief_id], engine=engine) == 1


def test_api_tool_and_cli_agree_on_the_same_data(engine, capsys):  # MP-15
    from sandbox_host.app import create_app
    from sandbox_host.config import HostSettings
    from sandbox_host.testing import signed_in_client

    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=engine,
                     services={"meeting_prep": CLIENTS})
    client = signed_in_client(app)
    client.post("/api/agents/meeting-prep/briefs", json={"company": "Shared Oy"})
    api_ids = [b["id"] for b in client.get("/api/agents/meeting-prep/briefs").json()["briefs"]]
    tool_ids = [b["id"] for b in tools_for(engine)["list_briefs"].handler({})["briefs"]]
    cli_main(["list"], engine=engine)
    cli_ids = [b["id"] for b in json.loads(capsys.readouterr().out)["result"]]
    service_ids = [b["id"] for b in service.list_briefs(MeetingPrepStore(engine))]
    assert api_ids == tool_ids == cli_ids == service_ids and len(api_ids) == 1


def test_chat_may_run_only_safe_commands():  # MP-11, M8
    spec = make_agent_spec()
    assert spec.cli.module == "meeting_prep.cli"
    assert spec.cli.commands == ("prepare", "list", "get")
    assert spec.has_panel and spec.chat_tools is not None
