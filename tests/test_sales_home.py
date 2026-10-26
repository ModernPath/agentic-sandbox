import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi import APIRouter

from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.panels import panel
from sandbox_host.registry import AgentSpec, RegistryError, validate_registry
from sandbox_host.testing import memory_engine, signed_in_client

STATIC = Path(__file__).resolve().parents[1] / "src" / "sandbox_host" / "static"


def test_panel_keeps_at_most_five_items():  # H-1
    p = panel("T", items=[{"title": str(i)} for i in range(7)])
    assert len(p["items"]) == 5


@pytest.mark.parametrize("href", ["//evil.example", "javascript:alert(1)", "https://ok.example/x"])
def test_panel_drops_unsafe_or_external_hrefs(href):  # H-2
    p = panel("T", items=[{"title": "x", "href": href}])
    expected = href if href.startswith("/") and not href.startswith("//") else None
    assert p["items"][0]["href"] == expected


def test_panel_trims_long_text():  # H-3
    p = panel("T", items=[{"title": "x" * 500}])
    assert len(p["items"][0]["title"]) == 200


def test_panel_has_the_contract_keys():  # H-4
    p = panel("Title", metric={"label": "Open", "value": 3}, empty="None", action={"label": "Open", "href": "/x"})
    assert set(p) == {"title", "metric", "items", "empty", "action"}


def test_agent_declaring_a_panel_must_serve_one():  # H-5
    spec = AgentSpec(name="needs-panel", title="N", description="d", router=APIRouter(), has_panel=True)
    with pytest.raises(RegistryError, match="panel"):
        validate_registry([spec])


def test_describe_reports_has_panel_and_home_lists_agents():  # H-6
    router = APIRouter()

    @router.get("/panel")
    def panel_route():
        return panel("Demo")

    spec = AgentSpec(name="demo-agent", title="Demo", description="d", router=router, has_panel=True)
    client = signed_in_client(create_app(HostSettings.from_env({}), agents=[spec], engine=memory_engine()))
    agents = client.get("/api/agents").json()["agents"]
    assert agents[0]["has_panel"] is True
    assert client.get("/api/agents/demo-agent/panel").json()["title"] == "Demo"


def test_home_page_loads_the_shared_kit():  # H-7
    client = signed_in_client(create_app(HostSettings.from_env({}), engine=memory_engine()))
    html = client.get("/").text
    assert "/static/sandbox.js" in html and "/static/sandbox.css" in html


def test_shared_script_has_the_api_helper_and_no_innerhtml_assignment():  # H-8
    js = (STATIC / "sandbox.js").read_text(encoding="utf-8")
    assert "Sandbox.api" in js or "api:" in js or "function api" in js
    assert "signOut" in js
    assert ".innerHTML =" not in js and ".innerHTML=" not in js


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_shared_script_is_valid_javascript():  # H-9
    result = subprocess.run(["node", "--check", str(STATIC / "sandbox.js")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_static_kit_is_public():  # H-10
    client = signed_in_client(create_app(HostSettings.from_env({}), engine=memory_engine()))
    client.cookies.clear()
    assert client.get("/static/sandbox.css").status_code == 200
