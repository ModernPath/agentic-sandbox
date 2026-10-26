import pytest
from host_test_client import SignedInTestClient as TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from sandbox_blocks.errors import ProviderError
from sandbox_blocks.fetch import PageContent
from sandbox_blocks.llm import LLMResponse
from sandbox_blocks.search import SearchResponse, SearchResult
from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from research_brief.api import make_agent_spec


class FakeSearch:
    provider = "fake"

    def __init__(self, results=()):
        self.results = tuple(results)

    def search(self, query, max_results):
        return SearchResponse(query=query, provider="fake", answer=None, results=self.results)


class FakeLLM:
    provider = "fake"
    model = "fake-model"

    def complete(self, prompt, system=None):
        return LLMResponse(text="Summary [1]", provider="fake", model="fake-model")


class BrokenLLM:
    provider = "fake"
    model = "fake"

    def complete(self, prompt, system=None):
        raise ProviderError("Provider returned HTTP 500: upstream failure")


def read_page(url):
    return PageContent(url=url, title="Page", text="Some useful text")


def memory_engine():
    return create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool,
                         connect_args={"check_same_thread": False})


def client_for(services=None, engine=None):
    engine = engine if engine is not None else memory_engine()
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=engine,
                     services=services or {})
    return TestClient(app)


GOOD_SERVICES = {"research_brief": {
    "llm": FakeLLM(),
    "search": FakeSearch([SearchResult("A", "https://a.example/1", "snip")]),
    "read_page": read_page,
}}


def test_create_brief_stores_and_returns_record():  # S17
    with client_for(GOOD_SERVICES) as client:
        response = client.post("/api/agents/research-brief/briefs", json={"topic": "solar"})
        assert response.status_code == 201
        body = response.json()
        assert body["topic"] == "solar"
        assert body["summary"] == "Summary [1]"
        assert body["sources"][0]["url"] == "https://a.example/1"
        assert body["id"]
        assert client.get(f"/api/agents/research-brief/briefs/{body['id']}").json()["summary"] == "Summary [1]"


@pytest.mark.parametrize("payload", [{"topic": ""}, {"topic": "x" * 301}, {}])
def test_invalid_topic_is_rejected(payload):  # S18
    with client_for(GOOD_SERVICES) as client:
        assert client.post("/api/agents/research-brief/briefs", json=payload).status_code == 422


def test_list_is_newest_first():  # S19
    with client_for(GOOD_SERVICES) as client:
        first = client.post("/api/agents/research-brief/briefs", json={"topic": "first"}).json()
        second = client.post("/api/agents/research-brief/briefs", json={"topic": "second"}).json()
        ids = [b["id"] for b in client.get("/api/agents/research-brief/briefs").json()["briefs"]]
        assert ids == [second["id"], first["id"]]


def test_unknown_brief_is_404():  # S20
    with client_for(GOOD_SERVICES) as client:
        assert client.get("/api/agents/research-brief/briefs/does-not-exist").status_code == 404


def test_brief_without_sources_is_stored_with_reason():  # S21
    services = {"research_brief": {"llm": FakeLLM(), "search": FakeSearch([]), "read_page": read_page}}
    with client_for(services) as client:
        created = client.post("/api/agents/research-brief/briefs", json={"topic": "obscure"}).json()
        assert created["summary"] is None
        assert created["reason"]
        listed = client.get("/api/agents/research-brief/briefs").json()["briefs"]
        assert [b["id"] for b in listed] == [created["id"]]


def test_briefs_persist_across_app_instances_on_same_database():  # S22
    engine = memory_engine()
    with client_for(GOOD_SERVICES, engine=engine) as client:
        created = client.post("/api/agents/research-brief/briefs", json={"topic": "kept"}).json()
    with client_for(GOOD_SERVICES, engine=engine) as client:
        assert client.get(f"/api/agents/research-brief/briefs/{created['id']}").json()["topic"] == "kept"


def test_provider_error_is_502_with_safe_message():  # S23
    services = {"research_brief": {"llm": BrokenLLM(), "search": FakeSearch([SearchResult("A", "https://a.example/1")]),
                                   "read_page": read_page}}
    with client_for(services) as client:
        response = client.post("/api/agents/research-brief/briefs", json={"topic": "x"})
        assert response.status_code == 502
        assert response.json()["error"]
        assert "Traceback" not in response.text


def test_missing_search_configuration_is_503_with_safe_message(monkeypatch):  # S24
    monkeypatch.delenv("SANDBOX_SEARCH_PROVIDER", raising=False)
    with client_for() as client:
        response = client.post("/api/agents/research-brief/briefs", json={"topic": "x"})
        assert response.status_code == 503
        assert "SANDBOX_SEARCH_PROVIDER" in response.json()["error"]


def test_storage_routes_without_engine_return_503():  # S25
    client = TestClient(create_app(HostSettings.from_env({}), agents=[make_agent_spec()], services=GOOD_SERVICES))
    response = client.get("/api/agents/research-brief/briefs")
    assert response.status_code == 503
    assert response.json()["error"]


def test_ui_page_is_served_and_renders_text_safely():  # S27 (static part)
    with client_for(GOOD_SERVICES) as client:
        html = client.get("/agents/research-brief/").text
        assert "Research brief" in html
        assert "innerHTML" not in html
