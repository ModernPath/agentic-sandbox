"""Standard checks for research brief: service, tools, CLI, and API must agree."""

import json
from pathlib import Path

import pytest

from research_brief import service
from research_brief.cli import main as cli_main
from research_brief.store import BriefStore
from research_brief.tools import build_tools
from sandbox_blocks.errors import ProviderError
from sandbox_blocks.fetch import PageContent
from sandbox_blocks.llm import LLMResponse
from sandbox_blocks.search import SearchResponse, SearchResult
from sandbox_host.migrations import apply_agent_migrations
from sandbox_host.testing import memory_engine

AGENT_DIR = Path(__file__).resolve().parents[1]


class FakeSearch:
    provider = "fake"

    def search(self, query, max_results):
        return SearchResponse(query=query, provider="fake", answer=None,
                              results=(SearchResult("A", "https://a.example/1", "snippet"),))


class FakeLLM:
    provider = "fake"
    model = "fake"

    def complete(self, prompt, system=None):
        return LLMResponse(text="Summary [1].", provider="fake", model="fake")


def read_page(url):
    return PageContent(url=url, title="A", text="Some useful text about the topic.")


class BrokenLLM(FakeLLM):
    def complete(self, prompt, system=None):
        raise ProviderError("upstream failed")


@pytest.fixture
def store():
    engine = memory_engine()
    apply_agent_migrations(engine, "research-brief", AGENT_DIR / "migrations")
    return BriefStore(engine)


def test_service_writes_a_brief_and_lists_it(store):
    record = service.run_brief(store, FakeSearch(), FakeLLM(), read_page, "solar storage")
    assert record["summary"] == "Summary [1]." and record["sources"][0]["url"] == "https://a.example/1"
    assert service.get_brief(store, record["id"])["topic"] == "solar storage"
    assert [b["id"] for b in service.list_briefs(store)] == [record["id"]]


def test_service_validates_the_topic(store):
    with pytest.raises(ValueError, match="Topic"):
        service.run_brief(store, FakeSearch(), FakeLLM(), read_page, "   ")


def test_tools_cover_the_actions_with_typed_parameters(store):
    tools = {t.name: t for t in build_tools(store, FakeSearch(), FakeLLM(), read_page)}
    assert set(tools) == {"research_topic", "list_briefs", "get_brief"}
    assert tools["research_topic"].parameters["properties"]["topic"]["type"] == "string"


def test_tool_errors_come_back_as_data(store):
    tools = {t.name: t for t in build_tools(store, FakeSearch(), BrokenLLM(), read_page)}
    result = tools["research_topic"].handler({"topic": "solar"})
    assert "error" in result and "upstream" not in str(result)


def test_cli_research_list_and_get(store, capsys):
    engine = store.engine
    assert cli_main(["research", "solar storage"], engine=engine, search=FakeSearch(), llm=FakeLLM(),
                    read_page=read_page) == 0
    brief = json.loads(capsys.readouterr().out)["result"]
    assert cli_main(["list"], engine=engine) == 0
    assert json.loads(capsys.readouterr().out)["result"][0]["id"] == brief["id"]
    assert cli_main(["get", "--id", "missing"], engine=engine) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
    assert cli_main(["get"], engine=engine) == 2


def test_api_tool_and_cli_agree(store, capsys):
    from research_brief.api import make_agent_spec
    from sandbox_host.app import create_app
    from sandbox_host.config import HostSettings
    from sandbox_host.testing import signed_in_client

    services = {"research_brief": {"search": FakeSearch(), "llm": FakeLLM(), "read_page": read_page}}
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=store.engine, services=services)
    client = signed_in_client(app)
    client.post("/api/agents/research-brief/briefs", json={"topic": "solar storage"})
    api_topics = [b["topic"] for b in client.get("/api/agents/research-brief/briefs").json()["briefs"]]
    tool_topics = [b["topic"] for b in service.list_briefs(store)]
    cli_main(["list"], engine=store.engine)
    cli_topics = [b["topic"] for b in json.loads(capsys.readouterr().out)["result"]]
    assert api_topics == tool_topics == cli_topics == ["solar storage"]
