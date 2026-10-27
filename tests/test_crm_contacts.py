"""CRM contacts: people at accounts, with validation, duplicates, archiving, and chat tools. Offline."""

from sqlalchemy import text

from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.testing import memory_engine, signed_in_client
from test_common_chat import ScriptedLLM, client as chat_client


def app_client():
    engine = memory_engine()
    app = create_app(HostSettings.from_env({}), agents=[], engine=engine)
    return signed_in_client(app), engine


def account(c, name="Northwind Clinics"):
    return c.post("/api/crm/accounts", json={"name": name, "type": "customer"}).json()


def contact(c, account_id, name="Ana Silva", **extra):
    body = {"account_id": account_id, "name": name, **extra}
    return c.post("/api/crm/contacts", json=body)


def test_k14_contacts_belong_to_an_account_and_are_listed_per_account():  # K-14
    c, _ = app_client()
    acc = account(c)
    other = account(c, "Harbor Health")
    assert contact(c, acc["id"], email="ana@northwind.example", title="CTO").status_code == 201
    assert contact(c, other["id"], name="Jo Lind").status_code == 201
    listed = c.get(f"/api/crm/contacts?account_id={acc['id']}").json()["contacts"]
    assert [x["name"] for x in listed] == ["Ana Silva"]
    assert listed[0]["title"] == "CTO" and listed[0]["owner"]


def test_k15_contacts_need_a_real_account_and_valid_fields():  # K-15
    c, _ = app_client()
    acc = account(c)
    assert contact(c, "missing").status_code == 404
    assert contact(c, acc["id"], name="A").status_code == 422
    assert contact(c, acc["id"], email="not-an-email").status_code == 422
    assert contact(c, acc["id"], phone="call me maybe!").status_code == 422


def test_k16_the_same_email_cannot_be_added_twice_to_one_account():  # K-16
    c, _ = app_client()
    acc = account(c)
    assert contact(c, acc["id"], email="ana@northwind.example").status_code == 201
    assert contact(c, acc["id"], name="Ana again", email="ANA@northwind.example").status_code == 409


def test_k17_archiving_a_contact_hides_it_and_keeps_the_row():  # K-17
    c, engine = app_client()
    acc = account(c)
    made = contact(c, acc["id"]).json()
    assert c.delete(f"/api/crm/contacts/{made['id']}").status_code == 200
    assert c.get(f"/api/crm/contacts?account_id={acc['id']}").json()["contacts"] == []
    with engine.connect() as conn:
        assert conn.execute(text("SELECT archived FROM crm_contacts WHERE id = :id"), {"id": made["id"]}).scalar() == 1


def test_k18_contact_tools_are_offered_in_the_chat():  # K-18
    chat, llm = chat_client([], llm=ScriptedLLM(reply="ok"))
    chat.post("/api/chat", json={"message": "hi", "history": []})
    assert {"crm__add_contact", "crm__list_contacts"} <= set(llm.tool_names)
