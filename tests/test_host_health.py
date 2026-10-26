from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from sandbox_host.app import create_app
from sandbox_host.config import HostSettings


def test_settings_load_without_database_url():  # S1
    settings = HostSettings.from_env({})
    assert settings.database_url is None
    assert settings.host == "127.0.0.1"


def test_health_without_engine_reports_not_configured():  # S2
    client = TestClient(create_app(HostSettings.from_env({})))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "not_configured"}


def test_health_with_working_engine_reports_ok():  # S3
    engine = create_engine("sqlite+pysqlite:///:memory:")
    client = TestClient(create_app(HostSettings.from_env({}), engine=engine))
    assert client.get("/api/health").json()["database"] == "ok"


def test_health_hides_driver_error_details():  # S4
    engine = create_engine("sqlite+pysqlite:////nonexistent-dir-for-test/x.db")
    client = TestClient(create_app(HostSettings.from_env({}), engine=engine))
    body = client.get("/api/health").json()
    assert body["database"] == "error"
    assert "nonexistent" not in str(body) and "sqlite" not in str(body).lower()
