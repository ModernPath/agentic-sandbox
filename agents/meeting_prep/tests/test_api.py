"""API tests for meeting prep. Offline, in-memory database, signed in as a test user (MP-1, MP-2, MP-12, MP-18, MP-19)."""

from sqlalchemy import text

from meeting_prep.api import make_agent_spec
from meeting_prep_fakes import FakeLLM, FakeSearch, fake_notes, fake_reader, fake_signals, signal
from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.testing import memory_engine, signed_in_client

BASE = "/api/agents/meeting-prep"


def services(**overrides):
    clients = {"search": FakeSearch(), "read_page": fake_reader(), "llm": FakeLLM(),
               "signals": fake_signals([signal(1, competitor="Acme")]), "notes": fake_notes()}
    clients.update(overrides)
    return {"meeting_prep": clients}


def make_app(**overrides):
    return create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=memory_engine(),
                      services=services(**overrides))


def client(**overrides):
    return signed_in_client(make_app(**overrides))


def test_prepare_list_get_and_delete_a_brief():  # MP-1, MP-12
    c = client()
    response = c.post(f"{BASE}/briefs", json={"company": "Acme", "meeting_date": "2026-10-30",
                                              "attendees": [{"name": "Ana Silva", "role": "CTO"}]})
    assert response.status_code == 201
    brief = response.json()
    assert brief["company"] == "Acme" and brief["attendees"][0]["name"] == "Ana Silva"
    assert brief["signals"][0]["source_url"] == "https://radar.example/1"
    assert [b["id"] for b in c.get(f"{BASE}/briefs").json()["briefs"]] == [brief["id"]]
    assert c.get(f"{BASE}/briefs/{brief['id']}").json() == brief
    assert c.delete(f"{BASE}/briefs/{brief['id']}").json() == {"deleted": True}
    assert c.get(f"{BASE}/briefs/{brief['id']}").status_code == 404
    assert c.delete(f"{BASE}/briefs/{brief['id']}").status_code == 404


def test_bad_input_is_422_with_a_safe_message():  # MP-2
    c = client()
    assert c.post(f"{BASE}/briefs", json={"company": "A"}).status_code == 422
    response = c.post(f"{BASE}/briefs", json={"company": "Acme", "website": "javascript:alert(1)"})
    assert response.status_code == 422 and "Website" in response.text
    assert c.post(f"{BASE}/briefs", json={"company": "Acme", "meeting_date": "tomorrow"}).status_code == 422


def test_works_without_any_configured_provider():  # MP-9, MP-10
    c = signed_in_client(create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=memory_engine(),
                                    services={"meeting_prep": {"signals": fake_signals(), "notes": fake_notes()}}))
    brief = c.post(f"{BASE}/briefs", json={"company": "Acme"}).json()
    assert brief["summary"] is None and "Web search is not configured." in brief["gaps"]
    assert brief["reason"] == "No model is configured, so no written brief."


def test_panel():  # MP-14
    c = client()
    c.post(f"{BASE}/briefs", json={"company": "Acme"})
    panel = c.get(f"{BASE}/panel").json()
    assert panel["metric"]["value"] == 1 and panel["items"][0]["title"] == "Acme"


def test_sign_in_is_required():  # MP-19
    from fastapi.testclient import TestClient

    anonymous = TestClient(make_app())
    assert anonymous.get(f"{BASE}/briefs").status_code == 401


def test_only_this_agents_tables_are_created():  # MP-18
    c = client()
    with c.app.state.engine.connect() as conn:
        names = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert {n for n in names if n.startswith("meeting_prep")} == {"meeting_prep_briefs"}
    assert {n for n in names if n.startswith("sandbox_")} == {"sandbox_users", "sandbox_sessions",
                                                               "sandbox_schema_migrations", "sandbox_audit",
                                                               "sandbox_drafts"}


def test_ui_page_is_served_and_uses_the_shared_kit():  # MP-19
    html = client().get("/agents/meeting-prep/").text
    assert "Meeting prep" in html
    assert '/static/sandbox.js' in html and '/static/sandbox.css' in html
    assert "var S = window.Sandbox" in html and "S.api(" in html
    assert "fetch(" not in html and "innerHTML" not in html
