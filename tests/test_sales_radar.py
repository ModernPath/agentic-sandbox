"""Sales radar tests (specs/features/sales-radar). Offline: fake search, reader, and model."""

import json

from fastapi.testclient import TestClient

from competitor_watch.api import make_agent_spec
from sandbox_blocks.errors import ProviderError
from sandbox_blocks.llm import LLMResponse
from sandbox_blocks.search import SearchResponse, SearchResult
from sandbox_blocks.tools import ToolCall, ToolRun
from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.testing import memory_engine, signed_in_client

BASE = "/api/agents/competitor-watch"
ENGINE_NEWS = SearchResult("Engine Co launches Nova", "https://news.example/engine", "snippet")
BAD_LINK = SearchResult("Bad link", "javascript:alert(1)", "x")
THREE = [SearchResult("Engine Co pricing", "https://news.example/a", "a"),
         SearchResult("Engine Co hiring", "https://news.example/b", "b"),
         SearchResult("Engine Co roadmap", "https://news.example/c", "c")]
ONE_SIGNAL = [{"headline": "Engine Co launches Nova", "category": "product", "importance": "high",
               "summary": "A new product line [1].", "source": 1}]


class FakeSearch:
    provider = "fake"

    def __init__(self, results=(ENGINE_NEWS, BAD_LINK), fail_for=None):
        self.results = tuple(results)
        self.fail_for = fail_for
        self.queries = []

    def search(self, query, max_results):
        self.queries.append(query)
        if self.fail_for and self.fail_for in query:
            raise ProviderError("upstream secret-key-123 rejected")
        return SearchResponse(query=query, provider="fake", answer=None, results=self.results)


class RadarLLM:
    """Returns `signals` as JSON for enrichment. For chat, calls the scripted tools through their handlers."""
    provider = "fake"
    model = "fake-model"

    def __init__(self, signals=None, raw=None, script=(("list_competitors", {}),), reply="Done."):
        self.signals = ONE_SIGNAL if signals is None else signals
        self.raw = raw
        self.script = script
        self.reply = reply
        self.prompts = []
        self.chat_history = None
        self.results = {}

    def complete(self, prompt, system=None):
        self.prompts.append(prompt)
        text = self.raw if self.raw is not None else json.dumps(self.signals)
        return LLMResponse(text=text, provider="fake", model="fake-model")

    def run_with_tools(self, prompt, *, system=None, history=(), tools=(), max_calls=8):
        self.chat_history = list(history)
        by_name = {t.name: t for t in tools}
        calls = []
        self.results = {}
        for name, args in self.script:
            result = by_name[name].handler(args)
            self.results[name] = result
            calls.append(ToolCall(name=name, arguments=args, result=result))
        return ToolRun(text=self.reply, provider="fake", model="fake-model", tool_calls=tuple(calls))


def app_client(search=None, llm=None):
    services = {"competitor_watch": {"search": search or FakeSearch(), "llm": llm or RadarLLM()}}
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=memory_engine(),
                     services=services)
    return signed_in_client(app)


def add(c, name="Engine Co"):
    response = c.post(f"{BASE}/competitors", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def dashboard(c):
    return c.get(f"{BASE}/dashboard").json()


# S-1 to S-7: checks
def test_s1_check_stores_enriched_signal_with_source():  # S-1
    c = app_client()
    add(c)
    assert c.post(f"{BASE}/check", json={}).status_code == 200
    signals = c.get(f"{BASE}/signals").json()["signals"]
    assert len(signals) == 1
    assert signals[0]["category"] == "product" and signals[0]["importance"] == "high"
    assert signals[0]["source_url"] == "https://news.example/engine"
    assert signals[0]["competitor_name"] == "Engine Co" and signals[0]["status"] == "new"


def test_s2_invalid_category_and_importance_fall_back():  # S-2
    llm = RadarLLM(signals=[{"headline": "Price cut", "category": "gossip", "importance": "urgent",
                             "summary": "Prices fell [1].", "source": 1}])
    c = app_client(llm=llm)
    add(c)
    c.post(f"{BASE}/check", json={})
    signal = c.get(f"{BASE}/signals").json()["signals"][0]
    assert signal["category"] == "other" and signal["importance"] == "low"


def test_s3_signal_citing_a_missing_result_is_dropped():  # S-3
    llm = RadarLLM(signals=[{"headline": "Ghost", "category": "product", "importance": "high",
                             "summary": "x", "source": 9}])
    c = app_client(llm=llm)
    add(c)
    c.post(f"{BASE}/check", json={})
    assert c.get(f"{BASE}/signals").json()["signals"] == []
    assert dashboard(c)["competitors"][0]["last_outcome"] == "no_signals"


def test_s4_second_check_skips_seen_urls():  # S-4
    llm = RadarLLM()
    search = FakeSearch()
    c = app_client(search=search, llm=llm)
    add(c)
    c.post(f"{BASE}/check", json={})
    prompts_after_first = len(llm.prompts)
    c.post(f"{BASE}/check", json={})
    assert len(llm.prompts) == prompts_after_first  # model not called again
    assert dashboard(c)["competitors"][0]["last_outcome"] == "no_new_sources"
    assert len(c.get(f"{BASE}/signals").json()["signals"]) == 1


def test_s5_unparseable_model_output_is_no_signals():  # S-5
    c = app_client(llm=RadarLLM(raw="Sorry, I cannot produce JSON today."))
    add(c)
    c.post(f"{BASE}/check", json={})
    assert dashboard(c)["competitors"][0]["last_outcome"] == "no_signals"
    assert c.get(f"{BASE}/signals").json()["signals"] == []


def test_s6_provider_failure_is_recorded_safely_and_others_continue():  # S-6
    search = FakeSearch(fail_for="Broken")
    c = app_client(search=search)
    add(c, "Broken Co")
    add(c, "Engine Co")
    response = c.post(f"{BASE}/check", json={})
    assert response.status_code == 200
    rows = {row["name"]: row for row in dashboard(c)["competitors"]}
    assert rows["Broken Co"]["last_outcome"] == "error"
    assert rows["Engine Co"]["last_outcome"] == "signals"
    assert "secret-key-123" not in json.dumps(dashboard(c))


def test_s7_non_http_result_is_never_stored():  # S-7
    c = app_client(search=FakeSearch(results=(BAD_LINK, ENGINE_NEWS)))
    add(c)
    c.post(f"{BASE}/check", json={})
    urls = [s["source_url"] for s in c.get(f"{BASE}/signals").json()["signals"]]
    assert urls and all(url.startswith("https://") for url in urls)


# S-8 to S-10: signals, review, dashboard
def seeded_client():
    llm = RadarLLM(signals=[
        {"headline": "Pricing up", "category": "pricing", "importance": "high", "summary": "a [1].", "source": 1},
        {"headline": "Hiring SREs", "category": "hiring", "importance": "low", "summary": "b [2].", "source": 2},
        {"headline": "New roadmap", "category": "product", "importance": "low", "summary": "c [3].", "source": 3},
    ])
    c = app_client(search=FakeSearch(results=THREE), llm=llm)
    add(c)
    c.post(f"{BASE}/check", json={})
    return c


def test_s8_signal_filters():  # S-8
    c = seeded_client()
    assert len(c.get(f"{BASE}/signals?category=pricing").json()["signals"]) == 1
    assert len(c.get(f"{BASE}/signals?importance=high").json()["signals"]) == 1
    competitor_id = c.get(f"{BASE}/competitors").json()["competitors"][0]["id"]
    assert len(c.get(f"{BASE}/signals?competitor_id={competitor_id}").json()["signals"]) == 3


def test_s9_review_and_dismiss_leave_the_default_list():  # S-9
    c = seeded_client()
    first, second, _ = c.get(f"{BASE}/signals").json()["signals"]
    assert c.patch(f"{BASE}/signals/{first['id']}", json={"status": "reviewed"}).status_code == 200
    assert c.patch(f"{BASE}/signals/{second['id']}", json={"status": "dismissed"}).status_code == 200
    remaining_ids = [s["id"] for s in c.get(f"{BASE}/signals").json()["signals"]]
    assert len(remaining_ids) == 1
    assert first["id"] not in remaining_ids and second["id"] not in remaining_ids
    assert c.patch(f"{BASE}/signals/{first['id']}", json={"status": "new"}).status_code == 422


def test_s10_dashboard_shape_and_counts():  # S-10
    data = dashboard(seeded_client())
    assert data["kpis"]["new_signals"] == 3
    assert data["kpis"]["new_high_signals"] == 1
    assert data["kpis"]["watched_competitors"] == 1
    assert data["by_category"]["pricing"] == 1 and data["by_category"]["hiring"] == 1
    assert len(data["daily"]) == 14 and data["daily"][-1]["count"] == 3
    assert data["competitors"][0]["new_signals"] == 3 and data["competitors"][0]["last_outcome"] == "signals"
    assert len(data["latest"]) == 3


# S-11 to S-14: chat
def test_s11_chat_calls_tools_and_returns_reply():  # S-11
    c = app_client(llm=RadarLLM(script=(("list_competitors", {}),), reply="You watch 1 competitor."))
    add(c)
    response = c.post(f"{BASE}/chat", json={"message": "Who do we watch?", "history": []})
    assert response.status_code == 200
    assert response.json() == {"reply": "You watch 1 competitor.", "tool_calls": ["list_competitors"]}


def test_s12_chat_validates_history_and_message_size():  # S-12
    c = app_client()
    too_much_history = [{"role": "user", "content": "x"}] * 21
    assert c.post(f"{BASE}/chat", json={"message": "hi", "history": too_much_history}).status_code == 422
    assert c.post(f"{BASE}/chat", json={"message": "x" * 1001, "history": []}).status_code == 422


def test_s13_chat_without_a_model_is_503(monkeypatch):  # S-13
    for name in ("SANDBOX_LLM_PROVIDER", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    services = {"competitor_watch": {"search": FakeSearch()}}
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=memory_engine(),
                     services=services)
    c = signed_in_client(app)
    response = c.post(f"{BASE}/chat", json={"message": "hi", "history": []})
    assert response.status_code == 503 and "model" in response.json()["error"].lower()


def test_s14_competitor_brief_tool_returns_counts_and_newest_signals():  # S-14
    c = seeded_client()
    competitor_id = c.get(f"{BASE}/competitors").json()["competitors"][0]["id"]
    llm = RadarLLM(script=(("competitor_brief", {"competitor_id": competitor_id}),), reply="Brief.")
    c.app.state.services["competitor_watch"]["llm"] = llm
    response = c.post(f"{BASE}/chat", json={"message": "What changed at Engine Co?", "history": []})
    assert response.json()["tool_calls"] == ["competitor_brief"]
    brief = llm.results["competitor_brief"]
    assert brief["counts"] == {"pricing": 1, "hiring": 1, "product": 1}
    assert len(brief["newest"]) == 3


# S-15 (home redirect) is superseded by the common chat home: see tests/test_common_chat.py C-17.


def test_s16_radar_page_is_served_without_mock_data():  # S-16
    c = app_client()
    response = c.get("/agents/competitor-watch/")
    assert response.status_code == 200
    assert "Sales radar" in response.text
    assert "innerHTML" not in response.text
