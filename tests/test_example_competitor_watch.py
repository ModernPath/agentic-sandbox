import json
import pytest
from sqlalchemy import text

from competitor_watch.api import make_agent_spec
from sandbox_blocks.errors import ProviderError
from sandbox_blocks.llm import LLMResponse
from sandbox_blocks.search import SearchResponse, SearchResult
from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.testing import memory_engine, signed_in_client

BASE = "/api/agents/competitor-watch"


class FakeSearch:
    provider = "fake"

    def __init__(self, results=None, fail_for=None):
        self.results = results
        self.fail_for = fail_for
        self.queries = []

    def search(self, query, max_results):
        self.queries.append(query)
        if self.fail_for and self.fail_for in query:
            raise ProviderError("upstream secret-key-123 rejected")
        if self.results is None:
            return SearchResponse(query=query, provider="fake", answer=None, results=())
        return SearchResponse(query=query, provider="fake", answer=None, results=tuple(self.results))


class FakeLLM:
    provider = "fake"
    model = "fake-model"

    def __init__(self, text='[{"headline": "Engine Co launches a product", "category": "product", "importance": "high", "summary": "New product line [1].", "source": 1}]', fail=False):
        self.text = text
        self.fail = fail
        self.prompts = []

    def complete(self, prompt, system=None):
        if self.fail:
            raise ProviderError("model down")
        self.prompts.append(prompt)
        return LLMResponse(text=self.text, provider="fake", model="fake-model")


NEWS = [SearchResult("Engine Co launches", "https://news.example/engine", "snippet"),
        SearchResult("Bad link", "javascript:alert(1)", "x")]


def app_client(search=None, llm=None):
    engine = memory_engine()
    services = {"competitor_watch": {"search": search or FakeSearch(NEWS), "llm": llm or FakeLLM()}}
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=engine, services=services)
    return signed_in_client(app)


def add(c, name="Engine Co", website=None, note=""):
    body = {"name": name, "note": note}
    if website:
        body["website"] = website
    return c.post(f"{BASE}/competitors", json=body)


def test_add_and_list_competitors():  # CW-1
    c = app_client()
    response = add(c, "Engine Co", "https://engine.example")
    assert response.status_code == 201
    assert [x["name"] for x in c.get(f"{BASE}/competitors").json()["competitors"]] == ["Engine Co"]


def test_duplicate_names_are_refused_case_insensitively():  # CW-2
    c = app_client()
    add(c, "Acme")
    assert add(c, "ACME").status_code == 409


@pytest.mark.parametrize("payload", [
    {"name": "x"},
    {"name": "Good Co", "website": "ftp://nope.example"},
    {"name": "Good Co", "note": "n" * 501},
])
def test_invalid_competitors_are_rejected(payload):  # CW-3
    c = app_client()
    assert c.post(f"{BASE}/competitors", json=payload).status_code == 422


def test_competitor_can_be_deleted_and_unknown_is_404():  # CW-4
    c = app_client()
    cid = add(c, "Engine Co").json()["id"]
    assert c.delete(f"{BASE}/competitors/{cid}").status_code == 200
    assert c.get(f"{BASE}/competitors").json()["competitors"] == []
    assert c.delete(f"{BASE}/competitors/{cid}").status_code == 404


def test_check_all_stores_signals_per_competitor():  # CW-5
    search = FakeSearch(NEWS)
    c = app_client(search=search)
    add(c, "Engine Co")
    add(c, "Rival Oy")
    response = c.post(f"{BASE}/check")
    assert response.status_code == 200 and response.json()["checked"] == 2
    signals = c.get(f"{BASE}/signals").json()["signals"]
    assert sorted(s["competitor_name"] for s in signals) == ["Engine Co", "Rival Oy"]
    assert search.queries == ['"Engine Co" news', '"Rival Oy" news']


def test_check_one_competitor_by_id():  # CW-6
    c = app_client()
    cid = add(c, "Engine Co").json()["id"]
    add(c, "Rival Oy")
    assert c.post(f"{BASE}/check", json={"competitor_id": cid}).json()["checked"] == 1
    signals = c.get(f"{BASE}/signals").json()["signals"]
    assert [s["competitor_name"] for s in signals] == ["Engine Co"]


def test_no_news_is_recorded_as_a_check_outcome():  # CW-7
    c = app_client(search=FakeSearch(results=None))
    add(c, "Quiet Co")
    c.post(f"{BASE}/check")
    assert c.get(f"{BASE}/signals").json()["signals"] == []
    assert c.get(f"{BASE}/dashboard").json()["competitors"][0]["last_outcome"] == "no_new_sources"


def test_signal_has_headline_category_importance_source_and_status_new():  # CW-8
    c = app_client()
    add(c, "Engine Co")
    c.post(f"{BASE}/check")
    signal = c.get(f"{BASE}/signals").json()["signals"][0]
    assert signal["headline"] and signal["created_at"] and signal["status"] == "new"
    assert signal["category"] == "product" and signal["importance"] == "high"
    assert signal["source_url"] == "https://news.example/engine"


def test_review_marks_a_signal_and_unknown_is_404():  # CW-9
    c = app_client()
    add(c, "Engine Co")
    c.post(f"{BASE}/check")
    sid = c.get(f"{BASE}/signals").json()["signals"][0]["id"]
    assert c.patch(f"{BASE}/signals/{sid}", json={"status": "reviewed"}).status_code == 200
    assert c.get(f"{BASE}/signals").json()["signals"] == []
    assert c.patch(f"{BASE}/signals/missing", json={"status": "reviewed"}).status_code == 404


def test_only_http_source_links_are_kept():  # CW-10
    c = app_client()
    add(c, "Engine Co")
    c.post(f"{BASE}/check")
    urls = [s["source_url"] for s in c.get(f"{BASE}/signals").json()["signals"]]
    assert urls == ["https://news.example/engine"]


def test_summary_is_capped_at_300_characters():  # CW-11
    long_summary = json.dumps([{"headline": "Big news", "category": "product", "importance": "low",
                                "summary": "x" * 400, "source": 1}])
    c = app_client(llm=FakeLLM(text=long_summary))
    add(c, "Engine Co")
    c.post(f"{BASE}/check")
    assert len(c.get(f"{BASE}/signals").json()["signals"][0]["summary"]) == 300


def test_panel_counts_new_signals_and_shows_the_latest_five():  # CW-12
    c = app_client()
    add(c, "Engine Co")
    c.post(f"{BASE}/check")
    body = c.get(f"{BASE}/panel").json()
    assert body["metric"] == {"label": "New signals", "value": 1}
    assert body["items"][0]["title"] == "Engine Co launches a product"
    assert body["items"][0]["href"] == "/agents/competitor-watch/"


def test_search_failure_for_one_competitor_does_not_stop_the_others():  # CW-13
    c = app_client(search=FakeSearch(NEWS, fail_for="Broken Co"))
    add(c, "Broken Co")
    add(c, "Engine Co")
    assert c.post(f"{BASE}/check").json()["checked"] == 2
    rows = {row["name"]: row for row in c.get(f"{BASE}/dashboard").json()["competitors"]}
    assert rows["Broken Co"]["last_outcome"] == "error"
    assert rows["Engine Co"]["last_outcome"] == "signals"
    assert "secret-key-123" not in json.dumps(c.get(f"{BASE}/dashboard").json())


def test_model_failure_is_recorded_as_a_fixed_error():  # CW-14
    c = app_client(llm=FakeLLM(fail=True))
    add(c, "Engine Co")
    c.post(f"{BASE}/check")
    assert c.get(f"{BASE}/dashboard").json()["competitors"][0]["last_outcome"] == "error"
    assert "model down" not in json.dumps(c.get(f"{BASE}/dashboard").json())


def test_only_this_agents_tables_are_created():  # CW-15
    c = app_client()
    with c.app.state.engine.connect() as conn:
        names = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert {n for n in names if n.startswith("competitor_watch_")} == {
        "competitor_watch_competitors", "competitor_watch_findings",
        "competitor_watch_checks", "competitor_watch_signals"}


def test_requires_sign_in():  # CW-16
    from fastapi.testclient import TestClient

    engine = memory_engine()
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=engine)
    with TestClient(app) as anonymous:
        assert anonymous.get(f"{BASE}/competitors").status_code == 401


def test_summary_is_built_from_page_text_when_pages_can_be_read():  # CW-17
    from sandbox_blocks.fetch import PageContent

    llm = FakeLLM()

    def read_page(url):
        return PageContent(url=url, title="t", text="Varex launched the VX-9 X-ray detector in May.")

    engine = memory_engine()
    services = {"competitor_watch": {"search": FakeSearch(NEWS), "llm": llm, "read_page": read_page}}
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=engine, services=services)
    c = signed_in_client(app)
    add(c, "Engine Co")
    c.post(f"{BASE}/check")
    assert "VX-9 X-ray detector" in llm.prompts[0]


def test_failed_page_read_falls_back_to_the_search_snippet():  # CW-18
    llm = FakeLLM()

    def read_page(url):
        raise RuntimeError("blocked")

    engine = memory_engine()
    services = {"competitor_watch": {"search": FakeSearch(NEWS), "llm": llm, "read_page": read_page}}
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=engine, services=services)
    c = signed_in_client(app)
    add(c, "Engine Co")
    c.post(f"{BASE}/check")
    assert "snippet" in llm.prompts[0]
