import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.passwords import hash_password, verify_password
from sandbox_host.users import create_user, set_disabled

HEADERS = {"X-Sandbox-Request": "1"}
PASSWORD = "correct horse battery"


def memory_engine():
    return create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})


def make_client(engine=None, **settings):
    engine = engine if engine is not None else memory_engine()
    app = create_app(HostSettings.from_env({}), engine=engine)
    return TestClient(app), engine


def login(client, username="alice", password=PASSWORD, headers=HEADERS):
    return client.post("/api/auth/login", json={"username": username, "password": password}, headers=headers)


@pytest.fixture
def signed_in():
    client, engine = make_client()
    client.__enter__()
    create_user(engine, "alice", PASSWORD)
    assert login(client).status_code == 200
    yield client, engine
    client.__exit__(None, None, None)


def test_create_user_stores_scrypt_hash_not_password():  # A-1
    client, engine = make_client()
    with client:
        create_user(engine, "alice", PASSWORD)
        with engine.connect() as conn:
            stored = conn.execute(text("SELECT password_hash FROM sandbox_users")).scalar()
    assert stored.startswith("scrypt$") and PASSWORD not in stored
    assert verify_password(PASSWORD, stored) and not verify_password("wrong password!!", stored)


def test_short_password_is_rejected():  # A-1 (policy)
    client, engine = make_client()
    with client, pytest.raises(ValueError, match="12"):
        create_user(engine, "alice", "short")


def test_cli_reads_password_from_prompt_not_argv(monkeypatch, capsys):  # A-2
    import sys
    from sandbox_host import users

    prompts = []
    monkeypatch.setattr(users.getpass, "getpass", lambda prompt="": prompts.append(prompt) or PASSWORD)
    engine = memory_engine()
    monkeypatch.setattr(users, "_engine_from_env", lambda: engine)
    monkeypatch.setattr(sys, "argv", ["users", "create", "alice"])
    with make_client(engine)[0]:
        assert users.main() == 0
    assert prompts and PASSWORD not in " ".join(sys.argv)


def test_correct_credentials_set_hardened_cookie():  # A-3
    client, engine = make_client()
    with client:
        create_user(engine, "alice", PASSWORD)
        response = login(client)
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert cookie.startswith("sandbox_session=") and "httponly" in cookie.lower()
        assert "samesite=strict" in cookie.lower()


def test_wrong_password_and_unknown_user_look_identical():  # A-4
    client, engine = make_client()
    with client:
        create_user(engine, "alice", PASSWORD)
        wrong = login(client, password="wrong password!!", headers=HEADERS)
        unknown = login(client, username="nobody", headers=HEADERS)
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_session_token_is_stored_only_as_hash(signed_in):  # A-5
    client, engine = signed_in
    token = client.cookies.get("sandbox_session")
    with engine.connect() as conn:
        hashes = [r[0] for r in conn.execute(text("SELECT token_hash FROM sandbox_sessions"))]
    assert token not in hashes and hashlib.sha256(token.encode()).hexdigest() in hashes


def test_session_expires_after_twelve_hours_or_two_idle_hours(signed_in):  # A-6
    client, engine = signed_in
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(text("UPDATE sandbox_sessions SET expires_at = :t"), {"t": (now - timedelta(minutes=1)).isoformat()})
    assert client.get("/api/agents").status_code == 401
    client.cookies.clear()
    assert login(client, headers=HEADERS).status_code == 200
    with engine.begin() as conn:
        conn.execute(text("UPDATE sandbox_sessions SET last_seen_at = :t"), {"t": (now - timedelta(hours=3)).isoformat()})
    assert client.get("/api/agents").status_code == 401


def test_logout_removes_the_session(signed_in):  # A-7
    client, engine = signed_in
    token = client.cookies.get("sandbox_session")
    assert client.post("/api/auth/logout", headers=HEADERS).status_code == 200
    client.cookies.set("sandbox_session", token)
    assert client.get("/api/agents").status_code == 401


def test_api_without_session_gets_401_json():  # A-8
    client, _ = make_client()
    with client:
        response = client.get("/api/agents")
    assert response.status_code == 401 and response.json() == {"error": "Sign in required"}


def test_page_without_session_redirects_to_login():  # A-9
    client, _ = make_client()
    with client:
        response = client.get("/", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].startswith("/login")


def test_health_and_login_page_are_public():  # A-10
    client, _ = make_client()
    with client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/login").status_code == 200


def test_six_wrong_passwords_are_throttled_for_that_username_only():  # A-11
    client, engine = make_client()
    with client:
        create_user(engine, "alice", PASSWORD)
        create_user(engine, "bob", PASSWORD)
        codes = [login(client, password="wrong password!!", headers=HEADERS).status_code for _ in range(6)]
        assert codes == [401, 401, 401, 401, 401, 429]
        assert login(client, username="bob", headers=HEADERS).status_code == 200


def test_unsafe_request_without_header_is_forbidden_even_when_signed_in(signed_in):  # A-12
    client, _ = signed_in
    response = client.post("/api/auth/logout")
    assert response.status_code == 403


def test_secure_cookie_flag_follows_setting(monkeypatch):  # A-13
    monkeypatch.setenv("SANDBOX_COOKIE_SECURE", "true")
    engine = memory_engine()
    client = TestClient(create_app(HostSettings.from_env({}), engine=engine))
    with client:
        create_user(engine, "alice", PASSWORD)
        assert "secure" in login(client).headers["set-cookie"].lower()


def test_disabled_user_loses_access_immediately(signed_in):  # A-14
    client, engine = signed_in
    set_disabled(engine, "alice", True)
    assert client.get("/api/agents").status_code == 401


def test_host_migration_creates_user_and_session_tables():  # A-15
    client, engine = make_client()
    with client:
        with engine.connect() as conn:
            names = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert {"sandbox_users", "sandbox_sessions"} <= names


def test_protected_routes_fail_closed_without_a_database():  # A-16
    client = TestClient(create_app(HostSettings.from_env({})))
    with client:
        response = client.get("/api/agents")
    assert response.status_code == 503 and response.json()["error"]
