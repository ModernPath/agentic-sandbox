import ast
from pathlib import Path

from blocks_fakes import RecordingTransport
from research_brief.brief import build_brief
from sandbox_blocks.fetch import PageContent
from sandbox_blocks.llm import LLMResponse
from sandbox_blocks.search import SearchResponse, SearchResult

ROOT = Path(__file__).resolve().parents[1]


class FakeSearch:
    provider = "fake"

    def __init__(self, results):
        self.results = results
        self.queries = []

    def search(self, query, max_results):
        self.queries.append((query, max_results))
        return SearchResponse(query=query, provider="fake", answer=None, results=tuple(self.results))


class FakeLLM:
    provider = "fake"
    model = "fake-model"

    def __init__(self):
        self.prompts = []

    def complete(self, prompt, system=None):
        self.prompts.append(prompt)
        return LLMResponse(text="Summary [1][2]", provider="fake", model="fake-model")


def reader_with(pages, failing=()):
    def read_page(url):
        if url in failing:
            raise RuntimeError("blocked")
        return PageContent(url=url, title=pages[url][0], text=pages[url][1])
    return read_page


RESULTS = [
    SearchResult("A", "https://a.example/1", "snippet a"),
    SearchResult("B", "https://b.example/2", "snippet b"),
]


def test_build_brief_summarises_numbered_sources_with_one_llm_call():  # T20
    llm = FakeLLM()
    pages = {"https://a.example/1": ("A", "Alpha text"), "https://b.example/2": ("B", "Beta text")}
    brief = build_brief("topic", search=FakeSearch(RESULTS), read_page=reader_with(pages), llm=llm, max_sources=2)

    assert brief.summary == "Summary [1][2]"
    assert [s.number for s in brief.sources] == [1, 2]
    assert len(llm.prompts) == 1
    assert "[1] A (https://a.example/1)" in llm.prompts[0]
    assert "Beta text" in llm.prompts[0]


def test_failed_page_is_skipped_and_run_completes():  # T21
    llm = FakeLLM()
    pages = {"https://b.example/2": ("B", "Beta text")}
    brief = build_brief("topic", search=FakeSearch(RESULTS), read_page=reader_with(pages, failing={"https://a.example/1"}),
                        llm=llm, max_sources=2)
    assert brief.summary == "Summary [1][2]"
    assert brief.skipped == ("https://a.example/1",)
    assert [(s.url, s.text) for s in brief.sources] == [("https://a.example/1", "snippet a"), ("https://b.example/2", "Beta text")]


def test_no_readable_text_skips_llm_and_explains():  # T22
    llm = FakeLLM()
    brief = build_brief("topic", search=FakeSearch([]), read_page=reader_with({}), llm=llm)
    assert brief.summary is None
    assert brief.reason
    assert llm.prompts == []


def test_snippet_is_used_when_page_cannot_be_read():
    llm = FakeLLM()
    brief = build_brief("topic", search=FakeSearch(RESULTS[:1]), read_page=reader_with({}, failing={"https://a.example/1"}),
                        llm=llm, max_sources=1)
    assert brief.sources[0].text == "snippet a"


def test_example_depends_only_on_building_block_interfaces():  # T23
    tree = ast.parse((ROOT / "agents/research_brief/brief.py").read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    forbidden = ("urllib", "requests", "httpx", "openai", "google", "sandbox_blocks.transport")
    assert not [name for name in imported if name.startswith(forbidden)]
