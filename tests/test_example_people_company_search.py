import io

import pytest

from people_company_search.__main__ import main
from people_company_search.schemas import COMPANY_SCHEMA, PEOPLE_SCHEMA, clean_text
from sandbox_blocks.exa_agent import AgentResult


class FakeAgentClient:
    def __init__(self, structured=None, grounding=None, text="", error=None):
        self.structured = structured
        self.grounding = grounding or []
        self.text = text
        self.error = error
        self.queries = []

    def run(self, query, output_schema):
        self.queries.append((query, output_schema))
        if self.error:
            raise self.error
        return AgentResult(run_id="agent_run_x", status="completed", structured=self.structured,
                           text=self.text, grounding=self.grounding, cost=0.3, stop_reason="schema_satisfied")


def run_cli(argv, client, capsys):
    code = main(argv, environ={"EXA_API_KEY": "ex-test-key"}, client=client)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_people_and_company_schemas_are_bounded_and_omit_contact_fields():  # X-10
    for schema, key in ((PEOPLE_SCHEMA, "people"), (COMPANY_SCHEMA, "companies")):
        assert schema["properties"][key]["maxItems"] == 25
        text = repr(schema).lower()
        assert "email" not in text and "phone" not in text


def test_empty_query_exits_2_without_calling_exa(capsys):  # X-9
    client = FakeAgentClient()
    code, _, err = run_cli(["people", "   "], client, capsys)
    assert code == 2 and "query" in err.lower()
    assert client.queries == []


def test_query_over_500_characters_exits_2(capsys):  # X-9
    client = FakeAgentClient()
    code, _, _ = run_cli(["company", "x" * 501], client, capsys)
    assert code == 2 and client.queries == []


def test_unknown_kind_exits_2(capsys):
    code, _, _ = run_cli(["cars", "anything"], FakeAgentClient(), capsys)
    assert code == 2


def test_people_output_shows_each_items_citations_and_marks_unsourced_items(capsys):  # X-11
    structured = {"people": [
        {"name": "Ada Lovelace", "job_title": "CTO", "company": "Engine Co", "profile_url": "https://linkedin.example/ada"},
        {"name": "Alan Turing", "job_title": "VP Eng", "company": "Logic Ltd"},
    ]}
    grounding = [
        {"field": "structured.people[0]", "confidence": "high",
         "citations": [{"url": "https://news.example/engine-series-b"}]},
    ]
    code, out, _ = run_cli(["people", "AI infra engineering leaders"],
                           FakeAgentClient(structured=structured, grounding=grounding), capsys)
    assert code == 0
    assert "Ada Lovelace" in out and "https://news.example/engine-series-b" in out
    assert "Alan Turing" in out and "unsourced" in out
    assert "Sources cited by the run" not in out


def test_item_without_citations_falls_back_to_profile_url(capsys):
    structured = {"people": [
        {"name": "Ada Lovelace", "job_title": "CTO", "company": "Engine Co", "profile_url": "https://linkedin.example/ada"},
    ]}
    code, out, _ = run_cli(["people", "q"], FakeAgentClient(structured=structured, grounding=[]), capsys)
    assert code == 0 and "https://linkedin.example/ada" in out and "unsourced" not in out


def test_company_output_uses_website_as_source(capsys):
    structured = {"companies": [{"name": "Engine Co", "website": "https://engine.example", "industry": "AI infra"}]}
    code, out, _ = run_cli(["company", "AI infra companies"], FakeAgentClient(structured=structured), capsys)
    assert code == 0 and "Engine Co" in out and "https://engine.example" in out


def test_terminal_escape_codes_are_removed_from_printed_text(capsys):  # X-12
    structured = {"people": [{"name": "Evil\x1b[2J Name", "job_title": "x\x07", "company": "c"}]}
    code, out, _ = run_cli(["people", "q"], FakeAgentClient(structured=structured), capsys)
    assert code == 0
    assert "\x1b" not in out and "\x07" not in out
    assert "Evil" in out


def test_failed_run_message_has_no_key(capsys):  # X-13
    from sandbox_blocks.errors import ProviderError
    code, _, err = run_cli(["people", "q"], FakeAgentClient(error=ProviderError("Exa agent run failed: stop reason error")),
                           capsys)
    assert code == 1
    assert "ex-test-key" not in err and "failed" in err


def test_clean_text_strips_control_characters():
    assert clean_text("a\x00b\x1bc\nd") == "abcd"
