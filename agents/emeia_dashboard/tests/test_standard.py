"""Standard checks for the EMEIA dashboard: service, tools, CLI, and API must agree, and models cannot approve."""

import json
from pathlib import Path

import pytest

from emeia_dashboard import service
from emeia_dashboard.cli import main as cli_main
from emeia_dashboard.store import DashboardStore
from emeia_dashboard.tools import build_tools
from sandbox_host.migrations import apply_agent_migrations
from sandbox_host.testing import memory_engine

AGENT_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def store():
    engine = memory_engine()
    apply_agent_migrations(engine, "emeia-dashboard", AGENT_DIR / "migrations")
    return DashboardStore(engine)


def test_service_targets_and_progress(store):
    target = service.add_target(store, {"period": "2026-Q4", "objective": "Grow", "key_result": "Deals",
                                        "target_value": 10, "current_value": 2})
    view = service.overview(store, "2026-Q4")
    assert view["targets"][0]["progress"] == pytest.approx(0.2)
    service.update_target(store, target["id"], 5)
    assert service.overview(store, "2026-Q4")["targets"][0]["current_value"] == 5


def test_service_rejects_invalid_targets(store):
    with pytest.raises(ValueError):
        service.add_target(store, {"period": "2026-Q4", "objective": "x", "key_result": "y", "target_value": 0})


def test_model_created_market_items_are_unreviewed_and_approval_is_separate(store):
    item = service.add_market_item(store, {"kind": "competitor", "title": "Rival launch"})
    assert item["reviewed"] is False
    assert service.overview(store)["market_items"] == []
    service.approve_market_item(store, item["id"])
    assert [i["title"] for i in service.overview(store)["market_items"]] == ["Rival launch"]


def test_tools_do_not_include_an_approval_action(store):
    names = {t.name for t in build_tools(store)}
    assert "approve_market_item" not in names and "review_market_item" not in names
    assert {"add_market_item", "list_review_queue"} <= names


def test_tool_errors_come_back_as_data(store):
    tools = {t.name: t for t in build_tools(store)}
    assert "error" in tools["add_target"].handler({"period": "2026-Q4", "objective": "x", "key_result": "y",
                                                  "target_value": 0, "current_value": 0, "unit": "", "owner": ""})


def test_cli_adds_a_target_and_approval_needs_the_cli_command(store, capsys):
    engine = store.engine
    assert cli_main(["target-add", "--period", "2026-Q4", "--objective", "Grow", "--key-result", "Deals",
                     "--target", "10"], engine=engine) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert cli_main(["market-add", "--kind", "market", "--title", "Trend"], engine=engine) == 0
    item_id = json.loads(capsys.readouterr().out)["result"]["id"]
    assert cli_main(["market-queue"], engine=engine) == 0
    assert json.loads(capsys.readouterr().out)["result"]["items"][0]["id"] == item_id
    assert cli_main(["market-approve", "--id", item_id], engine=engine) == 0


def test_api_tool_and_cli_agree_on_wins(store, capsys):
    from emeia_dashboard.api import make_agent_spec
    from sandbox_host.app import create_app
    from sandbox_host.config import HostSettings
    from sandbox_host.testing import signed_in_client

    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=store.engine)
    client = signed_in_client(app)
    client.post("/api/agents/emeia-dashboard/wins", json={"customer": "Acme", "won_on": "2026-10-05"})
    api_wins = [w["customer"] for w in client.get("/api/agents/emeia-dashboard/overview?period=2026-Q4").json()["wins"]]
    tool_wins = [w["customer"] for w in service.overview(store, "2026-Q4")["wins"]]
    cli_main(["overview", "--period", "2026-Q4"], engine=store.engine)
    cli_wins = [w["customer"] for w in json.loads(capsys.readouterr().out)["result"]["wins"]]
    assert api_wins == tool_wins == cli_wins == ["Acme"]
