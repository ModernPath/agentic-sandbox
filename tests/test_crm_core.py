"""CRM core: accounts, opportunities, tasks, summary, and chat tools (specs/features/crm-platform). Offline."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.testing import TEST_USERNAME, memory_engine, signed_in_client
from test_common_chat import ScriptedLLM, client as chat_client


def app_client():
    engine = memory_engine()
    app = create_app(HostSettings.from_env({}), agents=[], engine=engine)
    return signed_in_client(app), engine


def account(c, name="Northwind Clinics", kind="customer"):
    response = c.post("/api/crm/accounts", json={"name": name, "type": kind})
    assert response.status_code == 201, response.text
    return response.json()


def opportunity(c, account_id, name="Renewal", amount=120000):
    return c.post("/api/crm/opportunities", json={"account_id": account_id, "name": name, "amount_minor": amount,
                                                  "currency": "EUR"})


def past(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def future(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_k1_accounts_have_types_and_competitors_are_accounts():  # K-1
    c, _ = app_client()
    account(c, "Engine Co", "competitor")
    account(c, "Harbor Health", "prospect")
    listed = c.get("/api/crm/accounts?type=competitor").json()["accounts"]
    assert [a["name"] for a in listed] == ["Engine Co"]
    assert c.post("/api/crm/accounts", json={"name": "Bad", "type": "alien"}).status_code == 422


def test_k2_account_names_are_unique_case_insensitively():  # K-2
    c, _ = app_client()
    account(c, "Acme")
    assert c.post("/api/crm/accounts", json={"name": "ACME", "type": "customer"}).status_code == 409


def test_k3_opportunities_need_an_account_a_valid_stage_and_an_amount():  # K-3
    c, _ = app_client()
    acc = account(c)
    assert opportunity(c, acc["id"]).status_code == 201
    assert opportunity(c, "missing").status_code == 404
    assert opportunity(c, acc["id"], amount=-5).status_code == 422
    assert c.post(f"/api/crm/opportunities/{opportunity(c, acc['id']).json()['id']}/stage",
                  json={"stage": "gossip"}).status_code == 422


def test_k4_stage_changes_are_audited():  # K-4
    c, engine = app_client()
    deal = opportunity(c, account(c)["id"]).json()
    assert c.post(f"/api/crm/opportunities/{deal['id']}/stage", json={"stage": "commit"}).json()["stage"] == "commit"
    with engine.connect() as conn:
        actions = [r[0] for r in conn.execute(text("SELECT action FROM sandbox_audit"))]
    assert "opportunity.stage_changed" in actions


def test_k5_summary_counts_open_pipeline_won_and_accounts():  # K-5
    c, _ = app_client()
    acc = account(c)
    open_deal = opportunity(c, acc["id"], "Open", 100000).json()
    won_deal = opportunity(c, acc["id"], "Won", 50000).json()
    lost_deal = opportunity(c, acc["id"], "Lost", 70000).json()
    c.post(f"/api/crm/opportunities/{won_deal['id']}/stage", json={"stage": "won"})
    c.post(f"/api/crm/opportunities/{lost_deal['id']}/stage", json={"stage": "lost"})
    summary = c.get("/api/crm/summary").json()
    assert summary["open_pipeline_minor"] == 100000 and summary["won_minor"] == 50000
    assert summary["accounts"] == 1 and summary["open_opportunities"] == 1
    assert open_deal["id"]


def test_k6_tasks_can_be_overdue_and_completed():  # K-6
    c, _ = app_client()
    acc = account(c)
    task = c.post("/api/crm/tasks", json={"subject_id": acc["id"], "body": "Call procurement", "due_at": past(4)}).json()
    c.post("/api/crm/tasks", json={"subject_id": acc["id"], "body": "Send sheet", "due_at": future(2)})
    assert c.get("/api/crm/summary").json()["overdue_tasks"] == 1
    assert c.post(f"/api/crm/tasks/{task['id']}/complete").status_code == 200
    assert c.get("/api/crm/summary").json()["overdue_tasks"] == 0
    assert c.post("/api/crm/tasks/missing/complete").status_code == 404


def test_k7_archiving_hides_a_record_but_keeps_it():  # K-7
    c, engine = app_client()
    acc = account(c)
    assert c.delete(f"/api/crm/accounts/{acc['id']}").status_code == 200
    assert c.get("/api/crm/accounts").json()["accounts"] == []
    with engine.connect() as conn:
        assert conn.execute(text("SELECT archived FROM crm_accounts WHERE id = :id"), {"id": acc["id"]}).scalar() == 1


def test_k8_accounts_store_the_signed_in_owner():  # K-8
    c, _ = app_client()
    assert account(c)["owner"] == TEST_USERNAME


def test_k9_crm_tools_are_offered_in_the_chat():  # K-9
    chat, llm = chat_client([], llm=ScriptedLLM(reply="ok"))
    chat.post("/api/chat", json={"message": "hi", "history": []})
    names = set(llm.tool_names)
    assert {"crm__list_accounts", "crm__create_account", "crm__create_opportunity", "crm__set_stage",
            "crm__list_open_tasks", "crm__add_task", "crm__complete_task", "crm__summary"} <= names


def test_k10_front_page_has_crm_numbers_and_tasks():  # K-10
    c, _ = app_client()
    page = c.get("/").text
    assert 'id="crm-kpis"' in page and 'id="tasks"' in page and 'id="accounts"' in page


def test_k11_won_counts_only_deals_closed_this_quarter():  # K-11
    c, engine = app_client()
    acc = account(c)
    this_quarter = opportunity(c, acc["id"], "This quarter", 30000).json()
    last_year = opportunity(c, acc["id"], "Last year", 90000).json()
    c.post(f"/api/crm/opportunities/{this_quarter['id']}/stage", json={"stage": "won"})
    c.post(f"/api/crm/opportunities/{last_year['id']}/stage", json={"stage": "won"})
    with engine.begin() as conn:
        conn.execute(text("UPDATE crm_opportunities SET closed_at = :old WHERE id = :id"),
                     {"old": "2020-01-15T00:00:00+00:00", "id": last_year["id"]})
    summary = c.get("/api/crm/summary").json()
    assert summary["won_minor"] == 120000
    assert summary["won_quarter_minor"] == 30000


def test_k12_summary_reports_open_pipeline_by_stage_in_order():  # K-12
    c, _ = app_client()
    acc = account(c)
    a = opportunity(c, acc["id"], "Alpha", 10000).json()
    b = opportunity(c, acc["id"], "Beta", 25000).json()
    c.post(f"/api/crm/opportunities/{b['id']}/stage", json={"stage": "commit"})
    stages = c.get("/api/crm/summary").json()["by_stage"]
    assert [s["stage"] for s in stages] == ["qualify", "propose", "negotiate", "commit"]
    assert {s["stage"]: s["amount_minor"] for s in stages} == {"qualify": 10000, "propose": 0, "negotiate": 0, "commit": 25000}
    assert a["id"]


def test_k13_front_page_has_stage_view_and_creation_forms():  # K-13
    c, _ = app_client()
    page = c.get("/").text
    for marker in ('id="stage-bars"', 'id="new-account-form"', 'id="new-opportunity-form"', 'id="new-task-form"'):
        assert marker in page, marker
