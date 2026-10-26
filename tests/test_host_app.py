import logging

from fastapi import APIRouter
from host_test_client import ready_client
from sqlalchemy import create_engine

from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.registry import AgentSpec


def notes_agent(tmp_path=None, with_ui=None):
    router = APIRouter()

    @router.get("/ping")
    def ping():
        return {"agent": "notes", "pong": True}

    return AgentSpec(name="notes", title="Notes", description="Keeps notes", router=router,
                     ui_dir=with_ui)


def test_agent_router_is_mounted_under_api_prefix():  # S13
    client = ready_client(create_app(HostSettings.from_env({}), agents=[notes_agent()]))
    assert client.get("/api/agents/notes/ping").json() == {"agent": "notes", "pong": True}


def test_agent_ui_directory_is_served(tmp_path):  # S14
    (tmp_path / "index.html").write_text("<h1>Notes UI</h1>")
    client = ready_client(create_app(HostSettings.from_env({}), agents=[notes_agent(with_ui=tmp_path)]))
    response = client.get("/agents/notes/")
    assert response.status_code == 200
    assert "Notes UI" in response.text


def test_agent_index_lists_title_description_and_paths(tmp_path):  # S15
    (tmp_path / "index.html").write_text("ui")
    client = ready_client(create_app(HostSettings.from_env({}), agents=[notes_agent(with_ui=tmp_path)]))
    agents = client.get("/api/agents").json()["agents"]
    assert agents == [{
        "name": "notes", "title": "Notes", "description": "Keeps notes",
        "api_base": "/api/agents/notes", "ui_path": "/agents/notes/", "has_panel": False,
    }]


def test_index_page_links_to_agents():  # S16
    client = ready_client(create_app(HostSettings.from_env({}), agents=[notes_agent()]))
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "/api/agents" in response.text


def test_non_loopback_bind_logs_warning(caplog):  # S26
    with caplog.at_level(logging.WARNING, logger="sandbox_host"):
        create_app(HostSettings(host="0.0.0.0"))
    assert any("https" in r.message.lower() for r in caplog.records)


def test_loopback_bind_does_not_warn(caplog):
    with caplog.at_level(logging.WARNING, logger="sandbox_host"):
        create_app(HostSettings(host="127.0.0.1"))
    assert not [r for r in caplog.records if "authentication" in r.message.lower()]
