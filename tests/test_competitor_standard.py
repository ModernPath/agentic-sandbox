import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from competitor_watch import service
from competitor_watch.api import make_agent_spec
from competitor_watch.cli import main as cli_main
from competitor_watch.store import CompetitorStore
from competitor_watch.tools import build_tools
from sandbox_blocks.errors import ProviderError
from sandbox_blocks.llm import LLMResponse
from sandbox_blocks.search import SearchResponse, SearchResult
from sandbox_blocks.tools import Tool
from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.migrate import up_files
from sandbox_host.migrations import apply_agent_migrations
from sandbox_host.testing import memory_engine, signed_in_client

AGENT_DIR = Path(__file__).resolve().parents[1] / "agents" / "competitor_watch"
NEWS = [SearchResult("Engine Co launches", "https://news.example/engine", "snippet")]


class FakeSearch:
    provider = "fake"

    def __init__(self, results=NEWS):
        self.results = results

    def search(self, query, max_results):
        return SearchResponse(query=query, provider="fake", answer=None, results=tuple(self.results))


class FakeLLM:
    provider = "fake"
    model = "fake"

    def complete(self, prompt, system=None):
        return LLMResponse(text='[{"headline": "Engine Co launches a product", "category": "product", "importance": "high", "summary": "New product line [1].", "source": 1}]', provider="fake", model="fake")


def read_page(url):
    from sandbox_blocks.fetch import PageContent
    return PageContent(url=url, title="t", text="Engine Co launched a product.")


@pytest.fixture
def store():
    engine = memory_engine()
    apply_agent_migrations(engine, "competitor-watch", AGENT_DIR / "migrations")
    return CompetitorStore(engine)


def test_service_runs_without_the_api(store):  # AS-1
    service.add_competitor(store, "Engine Co", None, "")
    assert [c["name"] for c in service.list_competitors(store)] == ["Engine Co"]
    assert service.run_check(store, FakeSearch(), FakeLLM(), read_page) == 1
    assert len(service.list_signals(store)) == 1


@pytest.mark.parametrize("name, website", [("x", None), ("Good Co", "ftp://nope.example")])
def test_service_validates_inputs(store, name, website):  # AS-2
    with pytest.raises(ValueError):
        service.add_competitor(store, name, website, "")


def test_tools_cover_every_action_with_typed_schemas(store):  # AS-3
    tools = {t.name: t for t in build_tools(store, FakeSearch(), FakeLLM(), read_page)}
    assert set(tools) == {"add_competitor", "list_competitors", "check_competitors", "list_signals",
                          "review_signal", "competitor_brief"}
    for tool in tools.values():
        assert tool.parameters["type"] == "object"
    assert tools["add_competitor"].parameters["properties"]["name"]["type"] == "string"
    assert tools["review_signal"].parameters["properties"]["signal_id"]["type"] == "string"


def test_calling_a_tool_runs_the_service_and_records_the_call(store):  # AS-4
    seen = []
    tools = {t.name: t for t in build_tools(store, FakeSearch(), FakeLLM(), read_page, on_call=seen.append)}
    created = tools["add_competitor"].handler({"name": "Engine Co", "website": "", "note": ""})
    assert created["name"] == "Engine Co" and seen == ["add_competitor"]


def test_tool_errors_come_back_as_data(store):  # AS-5
    tools = {t.name: t for t in build_tools(store, FakeSearch(), FakeLLM(), read_page)}
    result = tools["add_competitor"].handler({"name": "x", "website": "", "note": ""})
    assert "error" in result


def test_cli_add_then_list_prints_a_json_envelope(store, capsys):  # AS-6
    engine = store.engine
    assert cli_main(["add", "--name", "Engine Co"], engine=engine) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True and envelope["result"]["name"] == "Engine Co"
    assert cli_main(["list"], engine=engine) == 0
    assert json.loads(capsys.readouterr().out)["result"][0]["name"] == "Engine Co"


def test_cli_error_envelope_and_exit_code(store, capsys):  # AS-7
    engine = store.engine
    cli_main(["add", "--name", "Engine Co"], engine=engine)
    capsys.readouterr()
    assert cli_main(["add", "--name", "engine co"], engine=engine) == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is False and "already exists" in envelope["error"]


def test_cli_bad_usage_exits_2_and_writes_nothing(store, capsys):  # AS-8
    assert cli_main(["add"], engine=store.engine) == 2
    assert service.list_competitors(store) == []


def test_cli_check_uses_injected_services(store, capsys):  # AS-9
    engine = store.engine
    cli_main(["add", "--name", "Engine Co"], engine=engine)
    capsys.readouterr()
    code = cli_main(["check"], engine=engine, search=FakeSearch(), llm=FakeLLM(), read_page=read_page)
    assert code == 0 and json.loads(capsys.readouterr().out)["result"]["checked"] == 1
    assert len(service.list_signals(store)) == 1


def test_cli_runs_as_a_subprocess_with_a_timeout(tmp_path):  # AS-10
    db = tmp_path / "cli.db"
    engine = create_engine(f"sqlite:///{db}")
    apply_agent_migrations(engine, "competitor-watch", AGENT_DIR / "migrations")
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}",
           "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src") + ":" +
                         str(Path(__file__).resolve().parents[1] / "agents")}
    result = subprocess.run([sys.executable, "-m", "competitor_watch.cli", "list"], env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True, "result": []}


def test_migrations_are_additive_and_rollback_files_are_not_applied():  # AS-11
    names = [p.name for p in up_files(AGENT_DIR / "migrations")]
    assert names == ["0001_init.sql", "0002_radar.sql"]
    assert (AGENT_DIR / "migrations" / "0001_init.down.sql").is_file()
    assert (AGENT_DIR / "migrations" / "0002_radar.down.sql").is_file()


def test_api_tool_and_cli_agree_on_data_and_errors(store, capsys):  # AS-12, AS-13
    engine = store.engine
    services = {"competitor_watch": {"search": FakeSearch(), "llm": FakeLLM(), "read_page": read_page}}
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=engine, services=services)
    client = signed_in_client(app)
    client.post("/api/agents/competitor-watch/competitors", json={"name": "Engine Co"})
    api_names = [c["name"] for c in client.get("/api/agents/competitor-watch/competitors").json()["competitors"]]
    tool_names = [c["name"] for c in service.list_competitors(store)]
    capsys.readouterr()
    cli_main(["list"], engine=engine)
    cli_names = [c["name"] for c in json.loads(capsys.readouterr().out)["result"]]
    assert api_names == tool_names == cli_names == ["Engine Co"]

    duplicate_api = client.post("/api/agents/competitor-watch/competitors", json={"name": "engine co"})
    tools = {t.name: t for t in build_tools(store, FakeSearch(), FakeLLM(), read_page)}
    duplicate_tool = tools["add_competitor"].handler({"name": "engine co", "website": "", "note": ""})
    cli_main(["add", "--name", "engine co"], engine=engine)
    duplicate_cli = json.loads(capsys.readouterr().out)
    assert duplicate_api.status_code == 409
    assert "error" in duplicate_tool and duplicate_cli["ok"] is False
