"""Standard checks for $Title: service, tools, CLI, and API must agree.

These tests are part of the agent standard. Keep them passing when you add actions.
"""

import json
from pathlib import Path

import pytest

from $module import service
from $module.cli import main as cli_main
from $module.store import $ClassStore
from $module.tools import build_tools
from sandbox_host.migrations import apply_agent_migrations
from sandbox_host.testing import memory_engine

AGENT_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def engine():
    engine = memory_engine()
    apply_agent_migrations(engine, "$name", AGENT_DIR / "migrations")
    return engine


def test_service_creates_lists_and_changes_status(engine):
    store = $ClassStore(engine)
    created = service.create_item(store, "First", "details")
    assert [i["id"] for i in service.list_items(store)] == [created["id"]]
    assert service.set_status(store, created["id"], "done") is True
    assert service.get_item(store, created["id"])["status"] == "done"


def test_service_rejects_bad_input_with_safe_messages(engine):
    store = $ClassStore(engine)
    with pytest.raises(ValueError, match="Title"):
        service.create_item(store, "", "")
    with pytest.raises(ValueError, match="Status"):
        service.set_status(store, "missing", "archived")
    with pytest.raises(LookupError, match="not found"):
        service.get_item(store, "missing")


def test_tools_cover_every_action_with_typed_schemas(engine):
    tools = {t.name: t for t in build_tools($ClassStore(engine))}
    assert {"create_item", "list_items", "set_status"} <= set(tools)
    assert tools["create_item"].parameters["properties"]["title"]["type"] == "string"


def test_tool_errors_come_back_as_data(engine):
    tools = {t.name: t for t in build_tools($ClassStore(engine))}
    assert "error" in tools["create_item"].handler({"title": "", "body": ""})


def test_cli_prints_json_and_exit_codes(engine, capsys):
    assert cli_main(["create", "--title", "Via CLI"], engine=engine) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True and envelope["result"]["title"] == "Via CLI"
    assert cli_main(["create", "--title", ""], engine=engine) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
    assert cli_main(["create"], engine=engine) == 2


def test_api_tool_and_cli_agree_on_the_same_data(engine, capsys):
    from fastapi.testclient import TestClient  # noqa: F401  (imported to show the API is mountable)
    from sandbox_host.app import create_app
    from sandbox_host.config import HostSettings
    from sandbox_host.testing import signed_in_client
    from $module.api import make_agent_spec

    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=engine)
    client = signed_in_client(app)
    client.post("/api/agents/$name/items", json={"title": "Shared"})
    api_titles = [i["title"] for i in client.get("/api/agents/$name/items").json()["items"]]
    tool_titles = [i["title"] for i in service.list_items($ClassStore(engine))]
    cli_main(["list"], engine=engine)
    cli_titles = [i["title"] for i in json.loads(capsys.readouterr().out)["result"]]
    assert api_titles == tool_titles == cli_titles == ["Shared"]
