"""Test kit for agents built on the sandbox host.

  from sandbox_host.testing import memory_engine, signed_in_client, make_user
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from .app import HOST_MIGRATION_NAME, HOST_MIGRATIONS_DIR
from .migrations import apply_agent_migrations
from .users import create_user

TEST_USERNAME = "tester"
TEST_PASSWORD = "test-password-long-enough"
WRITE_HEADER = {"X-Sandbox-Request": "1"}


def memory_engine() -> Engine:
    """An in-memory SQLite engine shared across connections (for tests only)."""
    return create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})


def make_user(engine: Engine, username: str = TEST_USERNAME, password: str = TEST_PASSWORD) -> None:
    try:
        create_user(engine, username, password)
    except ValueError:
        pass  # already exists


def signed_in_client(app, username: str = TEST_USERNAME, password: str = TEST_PASSWORD):
    """A TestClient for `app`, signed in, sending the sandbox header on every request.

    Works without a `with` block: applies the host migration first. The app gets an in-memory
    database if it has none.
    """
    from fastapi.testclient import TestClient

    class _Client(TestClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.headers.update(WRITE_HEADER)

    if app.state.engine is None:
        app.state.engine = memory_engine()
    apply_agent_migrations(app.state.engine, HOST_MIGRATION_NAME, HOST_MIGRATIONS_DIR)
    for agent in getattr(app.state, "agents", []):
        if agent.migrations_dir is not None:
            apply_agent_migrations(app.state.engine, agent.name, agent.migrations_dir)
    make_user(app.state.engine, username, password)
    client = _Client(app)
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return client
