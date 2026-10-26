"""TestClient that signs in before use, for tests of protected sandbox host routes.

Enter it with `with`: startup (migrations) runs first, then a test user is created and signed in.
Tests of the sign-in behaviour itself use plain TestClient.
"""

from fastapi.testclient import TestClient

from sandbox_host.users import create_user

TEST_USERNAME = "tester"
TEST_PASSWORD = "test-password-long-enough"
WRITE_HEADER = {"X-Sandbox-Request": "1"}


class SignedInTestClient(TestClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers.update(WRITE_HEADER)  # every request from tests is a same-origin sandbox request

    def __enter__(self):
        client = super().__enter__()
        engine = self.app.state.engine
        if engine is not None:
            try:
                create_user(engine, TEST_USERNAME, TEST_PASSWORD)
            except ValueError:
                pass  # already created by an earlier entry of this app
            response = self.post("/api/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
                                 headers=WRITE_HEADER)
            assert response.status_code == 200, response.text
        return client


def ready_client(app):
    """A signed-in client for tests that do not use `with`: applies the host migration first."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from sandbox_host.migrations import apply_agent_migrations
    from sandbox_host.app import HOST_MIGRATION_NAME, HOST_MIGRATIONS_DIR

    engine = app.state.engine or create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool,
                                               connect_args={"check_same_thread": False})
    app.state.engine = engine
    apply_agent_migrations(engine, HOST_MIGRATION_NAME, HOST_MIGRATIONS_DIR)
    try:
        create_user(engine, TEST_USERNAME, TEST_PASSWORD)
    except ValueError:
        pass
    client = SignedInTestClient(app)
    response = client.post("/api/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return client
