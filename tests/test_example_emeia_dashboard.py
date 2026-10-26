import re
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest
from host_test_client import SignedInTestClient as TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from emeia_dashboard.api import make_agent_spec
from emeia_dashboard.models import validate_http_url
from sandbox_host.app import create_app
from sandbox_host.config import HostSettings

ROOT = Path(__file__).resolve().parents[1]
BASE = "/api/agents/emeia-dashboard"


def client(engine=None):
    engine = engine if engine is not None else create_engine(
        "sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=engine)
    return TestClient(app)


def target(**overrides):
    body = {"period": "2026-Q4", "objective": "Grow EMEIA pipeline", "key_result": "Signed deals",
            "target_value": 10, "current_value": 2, "unit": "deals", "owner": "Sales lead"}
    body.update(overrides)
    return body


def test_progress_is_current_over_target_in_overview():  # E-M1
    with client() as c:
        c.post(f"{BASE}/targets", json=target())
        body = c.get(f"{BASE}/overview", params={"period": "2026-Q4"}).json()
        assert body["targets"][0]["progress"] == pytest.approx(0.2)


@pytest.mark.parametrize("bad", [{"target_value": 0}, {"target_value": -3}, {"current_value": -1}, {"period": "2026-12"}])
def test_invalid_target_is_rejected(bad):  # E-M2
    with client() as c:
        assert c.post(f"{BASE}/targets", json=target(**bad)).status_code == 422


def test_patch_updates_current_value_and_unknown_is_404():  # E-M3
    with client() as c:
        created = c.post(f"{BASE}/targets", json=target()).json()
        assert c.patch(f"{BASE}/targets/{created['id']}", json={"current_value": 6}).status_code == 200
        assert c.get(f"{BASE}/overview", params={"period": "2026-Q4"}).json()["targets"][0]["current_value"] == 6
        assert c.patch(f"{BASE}/targets/nope", json={"current_value": 1}).status_code == 404


def test_win_dated_far_in_future_is_rejected():  # E-M4
    future = (date.today() + timedelta(days=10)).isoformat()
    with client() as c:
        response = c.post(f"{BASE}/wins", json={"customer": "Acme", "won_on": future})
        assert response.status_code == 422


@pytest.mark.parametrize("extra", [{"value": -5}, {"value": 10, "currency": "euro"}])
def test_win_with_negative_value_or_bad_currency_is_rejected(extra):  # E-M5
    with client() as c:
        body = {"customer": "Acme", "won_on": date.today().isoformat(), **extra}
        assert c.post(f"{BASE}/wins", json=body).status_code == 422


def test_market_item_is_unreviewed_and_hidden_from_overview():  # E-M6
    with client() as c:
        c.post(f"{BASE}/market-items", json={"kind": "competitor", "title": "Rival launch", "summary": "s"})
        assert c.get(f"{BASE}/overview").json()["market_items"] == []


def test_marking_reviewed_publishes_item():  # E-M7
    with client() as c:
        item = c.post(f"{BASE}/market-items", json={"kind": "market", "title": "Trend", "summary": "s"}).json()
        assert c.patch(f"{BASE}/market-items/{item['id']}", json={"reviewed": True}).status_code == 200
        shown = c.get(f"{BASE}/overview").json()["market_items"]
        assert [i["title"] for i in shown] == ["Trend"]


def test_client_cannot_create_item_as_reviewed():  # E-M8
    with client() as c:
        created = c.post(f"{BASE}/market-items", json={"kind": "market", "title": "T", "reviewed": True}).json()
        assert created["reviewed"] is False


def test_review_queue_lists_only_unreviewed():  # E-M9
    with client() as c:
        a = c.post(f"{BASE}/market-items", json={"kind": "market", "title": "A"}).json()
        c.post(f"{BASE}/market-items", json={"kind": "market", "title": "B"})
        c.patch(f"{BASE}/market-items/{a['id']}", json={"reviewed": True})
        queue = c.get(f"{BASE}/market-items", params={"reviewed": "false"}).json()["items"]
        assert [i["title"] for i in queue] == ["B"]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://example.com/x", "https://", "https://ex.com/\n<script>"])
def test_unsafe_tool_link_is_rejected(url):  # E-M10
    with client() as c:
        assert c.post(f"{BASE}/tool-links", json={"label": "x", "url": url}).status_code == 422


def test_https_tool_link_is_created_and_listed():  # E-M11
    with client() as c:
        c.post(f"{BASE}/tool-links", json={"label": "Configurator", "url": "https://tools.example.com/cfg"})
        links = c.get(f"{BASE}/overview").json()["tool_links"]
        assert [(l["label"], l["url"]) for l in links] == [("Configurator", "https://tools.example.com/cfg")]


def test_overview_filters_targets_and_wins_by_period():  # E-M12
    with client() as c:
        c.post(f"{BASE}/targets", json=target(period="2026-Q4"))
        c.post(f"{BASE}/targets", json=target(period="2026-Q1", objective="Old"))
        assert c.post(f"{BASE}/wins", json={"customer": "Q4 win", "won_on": "2026-10-05"}).status_code == 201
        assert c.post(f"{BASE}/wins", json={"customer": "Q1 win", "won_on": "2026-02-05"}).status_code == 201
        body = c.get(f"{BASE}/overview", params={"period": "2026-Q4"}).json()
        assert [t["objective"] for t in body["targets"]] == ["Grow EMEIA pipeline"]
        assert [w["customer"] for w in body["wins"]] == ["Q4 win"]


def test_entries_survive_a_new_app_instance_on_same_engine():  # E-M13
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with client(engine) as c:
        c.post(f"{BASE}/tool-links", json={"label": "Kept", "url": "https://kept.example.com"})
    with client(engine) as c:
        assert [l["label"] for l in c.get(f"{BASE}/overview").json()["tool_links"]] == ["Kept"]


def test_migrations_create_tables_at_startup():  # E-M15
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with client(engine):
        from sqlalchemy import text
        with engine.connect() as conn:
            names = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert {"emeia_dashboard_targets", "emeia_dashboard_wins", "emeia_dashboard_market_items",
            "emeia_dashboard_tool_links"} <= names


def test_ui_page_has_no_inner_html_and_script_is_valid_js(tmp_path):  # E-M14
    html = (ROOT / "agents/emeia_dashboard/ui/index.html").read_text()
    assert "innerHTML" not in html
    with client() as c:
        assert c.get("/agents/emeia-dashboard/").status_code == 200
    if shutil.which("node"):
        scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
        assert len(scripts) == 1
        script = tmp_path / "dash.js"
        script.write_text(scripts[0])
        result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_validate_http_url_accepts_public_https_only():
    assert validate_http_url("https://example.com/a?b=1") == "https://example.com/a?b=1"
    with pytest.raises(ValueError):
        validate_http_url("file:///etc/passwd")
