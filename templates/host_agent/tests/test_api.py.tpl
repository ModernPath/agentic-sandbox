"""Tests for $Title. They run offline against an in-memory database and sign in as a test user."""

from $module.api import make_agent_spec
from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.testing import memory_engine, signed_in_client

BASE = "/api/agents/$name"


def client():
    return signed_in_client(create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=memory_engine()))


def test_create_and_list_items():
    c = client()
    created = c.post(f"{BASE}/items", json={"title": "First"}).json()
    assert created["title"] == "First" and created["status"] == "open" and created["id"]
    assert [i["id"] for i in c.get(f"{BASE}/items").json()["items"]] == [created["id"]]


def test_title_is_required_and_bounded():
    c = client()
    assert c.post(f"{BASE}/items", json={"title": ""}).status_code == 422
    assert c.post(f"{BASE}/items", json={"title": "x" * 201}).status_code == 422


def test_status_can_be_changed_and_unknown_items_are_404():
    c = client()
    item_id = c.post(f"{BASE}/items", json={"title": "Task"}).json()["id"]
    assert c.patch(f"{BASE}/items/{item_id}", json={"status": "done"}).json()["status"] == "done"
    assert c.get(f"{BASE}/items/{item_id}").json()["status"] == "done"
    assert c.patch(f"{BASE}/items/missing", json={"status": "done"}).status_code == 404
    assert c.get(f"{BASE}/items/missing").status_code == 404


def test_only_this_agents_tables_are_created():
    from sqlalchemy import text

    c = client()
    with c.app.state.engine.connect() as conn:
        names = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    ours = {n for n in names if n.startswith("${table}")}
    assert "${table}_items" in ours
    assert {n for n in names if n.startswith("sandbox_")} == {"sandbox_users", "sandbox_sessions", "sandbox_schema_migrations", "sandbox_audit", "sandbox_drafts"}


def test_ui_page_is_served_and_sends_the_header():
    c = client()
    html = c.get(f"/agents/$name/").text
    assert "$Title" in html and "'X-Sandbox-Request': '1'" in html
