"""Standard tests for people and company search: service rules, tools, JSON CLI, and the router. No network calls."""

import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from people_company_search import cli, service
from people_company_search.api import router
from people_company_search.tools import build_tools
from sandbox_blocks.errors import ConfigurationError, ProviderError


class FakeAgent:
    def __init__(self, structured=None, grounding=None, cost=0.12):
        self.structured = structured if structured is not None else {"people": [
            {"name": "Ada\x1b[31m", "job_title": "CTO", "company": "Acme", "profile_url": "https://example.com/ada"},
            {"name": "Bo", "job_title": "Analyst", "company": "Beta"},
        ]}
        self.grounding = grounding if grounding is not None else [
            {"field": "structured.people[0]", "citations": [{"url": "https://news.example.com/ada"}]},
        ]
        self.cost = cost
        self.calls = []

    def run(self, query, schema):
        self.calls.append((query, schema))
        return SimpleNamespace(structured=self.structured, grounding=self.grounding, cost=self.cost, run_id="run-1")


def test_run_search_cleans_text_and_prefers_cited_sources():
    result = service.run_search(FakeAgent(), "people", "CTOs in Finland")
    first, second = result["items"]
    assert first["name"] == "Ada[31m"  # control characters removed
    assert first["sources"] == ["https://news.example.com/ada"]
    assert second["sources"] == []  # no citation and no link


def test_run_search_falls_back_to_the_item_link_when_uncited():
    agent = FakeAgent(grounding=[])
    result = service.run_search(agent, "people", "CTOs")
    assert result["items"][0]["sources"] == ["https://example.com/ada"]


def test_run_search_validates_kind_and_query():
    for kind, query, message in [("sales", "x", "kind"), ("people", "  ", "empty"), ("people", "x" * 501, "at most")]:
        try:
            service.run_search(FakeAgent(), kind, query)
        except ValueError as error:
            assert message in str(error)
        else:
            raise AssertionError(f"expected ValueError for {kind!r}")


def test_run_search_sends_the_matching_schema():
    agent = FakeAgent(structured={"companies": []})
    service.run_search(agent, "company", "Nordic fintechs")
    query, schema = agent.calls[0]
    assert query == "Nordic fintechs"
    assert "companies" in schema["properties"]


def test_tools_return_errors_and_fixed_messages_instead_of_raising():
    tools = {t.name: t for t in build_tools(FakeAgent())}
    assert set(tools) == {"find_people", "find_companies"}
    assert tools["find_people"].handler({"query": "CTOs"})["items"]
    assert "error" in tools["find_companies"].handler({"query": ""})

    class Broken:
        def run(self, query, schema):
            raise ProviderError("secret upstream detail")

    assert tools_for(Broken())["find_people"].handler({"query": "x"}) == {
        "error": "The search provider failed. Try again later."}
    class Unconfigured:
        def run(self, query, schema):
            raise ConfigurationError("EXA_API_KEY missing")

    assert tools_for(Unconfigured())["find_people"].handler({"query": "x"}) == {
        "error": "People and company search is not configured."}


def tools_for(agent):
    return {t.name: t for t in build_tools(agent)}


def test_cli_prints_json_result(capsys):
    code = cli.main(["people", "CTOs", "in", "Finland"], client=FakeAgent())
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] is True
    assert out["result"]["run_id"] == "run-1"
    assert out["result"]["items"][0]["name"] == "Ada[31m"


def test_cli_usage_and_missing_key_exit_codes(capsys):
    assert cli.main(["sales", "x"], client=FakeAgent()) == 2
    assert "usage error" in capsys.readouterr().err
    code = cli.main(["people", "x"], environ={})
    out = json.loads(capsys.readouterr().out)
    assert code == 1 and out == {"ok": False, "error": "EXA_API_KEY is required for people and company search"}


def test_api_search_uses_the_injected_agent():
    app = FastAPI()
    app.include_router(router)
    app.state.services = {"people_company_search": FakeAgent()}
    client = TestClient(app)
    response = client.post("/search", json={"kind": "company", "query": "Nordic fintechs"})
    assert response.status_code == 200 and response.json()["kind"] == "company"
    assert client.post("/search", json={"kind": "sales", "query": "x"}).status_code == 422
    assert client.post("/search", json={"kind": "people", "query": ""}).status_code == 422
