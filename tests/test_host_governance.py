"""Host audit trail and drafts with approval (specs/features/crm-platform, phase 1 pieces). Offline."""

from fastapi import APIRouter
from sqlalchemy import text

from sandbox_host.app import create_app
from sandbox_host.audit import record
from sandbox_host.config import HostSettings
from sandbox_host.registry import AgentSpec
from sandbox_host.testing import TEST_USERNAME, memory_engine, signed_in_client


def client():
    engine = memory_engine()
    app = create_app(HostSettings.from_env({}), agents=[], engine=engine)
    return signed_in_client(app), engine


def draft(c, body="Reply to the tender notice", target="#sales"):
    return c.post("/api/drafts", json={"kind": "message", "target": target, "body": body})


def audit_actions(engine):
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT action FROM sandbox_audit ORDER BY at, id"))]


def test_g1_record_writes_a_row_that_the_audit_endpoint_lists():  # G-1
    c, engine = client()
    record(engine, actor="user:tester", action="test.event", subject="thing:1", detail={"n": 1})
    rows = c.get("/api/audit").json()["events"]
    assert rows[0]["action"] == "test.event" and rows[0]["actor"] == "user:tester"
    assert rows[0]["detail"] == {"n": 1}


def test_g2_draft_is_created_pending_and_audited():  # G-2
    c, engine = client()
    response = draft(c)
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "pending" and body["created_by"] == TEST_USERNAME
    assert "draft.created" in audit_actions(engine)


def test_g3_approve_records_who_and_when_and_is_audited():  # G-3
    c, engine = client()
    draft_id = draft(c).json()["id"]
    response = c.post(f"/api/drafts/{draft_id}/approve")
    assert response.status_code == 200 and response.json()["state"] == "approved"
    assert response.json()["decided_by"] == TEST_USERNAME and response.json()["decided_at"]
    assert "draft.approved" in audit_actions(engine)


def test_g4_a_decided_draft_cannot_be_decided_again():  # G-4
    c, _ = client()
    draft_id = draft(c).json()["id"]
    c.post(f"/api/drafts/{draft_id}/reject")
    assert c.post(f"/api/drafts/{draft_id}/approve").status_code == 409


def test_g5_reject_is_audited_and_pending_list_excludes_it():  # G-5
    c, engine = client()
    kept = draft(c, body="Keep me").json()["id"]
    rejected = draft(c, body="Reject me").json()["id"]
    c.post(f"/api/drafts/{rejected}/reject")
    pending = [d["id"] for d in c.get("/api/drafts?state=pending").json()["drafts"]]
    assert pending == [kept]
    assert "draft.rejected" in audit_actions(engine)


def test_g6_unknown_draft_is_404():  # G-6
    c, _ = client()
    assert c.post("/api/drafts/missing/approve").status_code == 404


def test_g7_draft_input_is_validated():  # G-7
    c, _ = client()
    assert draft(c, body="x" * 4001).status_code == 422
    assert draft(c, target="").status_code == 422
    assert c.post("/api/drafts", json={"kind": "shout", "target": "#x", "body": "hi"}).status_code == 422


def test_g8_audit_limit_is_bounded():  # G-8
    c, _ = client()
    assert c.get("/api/audit?limit=500").status_code == 422


def test_g9_a_competitor_check_and_a_signal_review_are_audited():  # G-9
    from competitor_watch.api import make_agent_spec
    from test_sales_radar import FakeSearch, RadarLLM, BASE, ENGINE_NEWS

    engine = memory_engine()
    services = {"competitor_watch": {"search": FakeSearch((ENGINE_NEWS,)), "llm": RadarLLM()}}
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=engine, services=services)
    c = signed_in_client(app)
    c.post(f"{BASE}/competitors", json={"name": "Engine Co"})
    c.post(f"{BASE}/check", json={})
    signal_id = c.get(f"{BASE}/signals").json()["signals"][0]["id"]
    c.patch(f"{BASE}/signals/{signal_id}", json={"status": "reviewed"})
    actions = audit_actions(engine)
    assert "competitor.check" in actions and "signal.reviewed" in actions


def test_g10_front_page_shows_activity_and_drafts():  # G-10
    c, _ = client()
    page = c.get("/").text
    assert 'id="activity"' in page and 'id="drafts"' in page
