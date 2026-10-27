"""Fakes for meeting prep tests: search, reader, model, radar, and notes. No network, no keys."""

from sandbox_blocks.errors import ProviderError
from sandbox_blocks.fetch import PageContent
from sandbox_blocks.llm import LLMResponse
from sandbox_blocks.search import SearchResponse, SearchResult

RESULTS = [
    SearchResult("Acme raises funding", "https://news.example/acme-funding", "Acme raised money"),
    SearchResult("Acme hires CFO", "https://news.example/acme-cfo", "New CFO snippet"),
    SearchResult("Bad link", "javascript:alert(1)", "bad"),
    SearchResult("Acme product launch", "https://acme.example/launch", "Launch snippet"),
]
PAGES = {
    "https://news.example/acme-funding": ("Acme raises funding", "Acme raised EUR 20M in October."),
    "https://acme.example/launch": ("Acme launch", "Acme launched a new line."),
}


class FakeSearch:
    provider = "fake"

    def __init__(self, results=RESULTS, error=None):
        self.results = results
        self.error = error
        self.queries = []

    def search(self, query, max_results):
        self.queries.append((query, max_results))
        if self.error:
            raise self.error
        return SearchResponse(query=query, provider="fake", answer=None, results=tuple(self.results))


def fake_reader(pages=PAGES):
    def read_page(url):
        if url not in pages:
            raise RuntimeError("blocked")
        title, text = pages[url]
        return PageContent(url=url, title=title, text=text)
    return read_page


class FakeLLM:
    provider = "fake"
    model = "fake-model"

    def __init__(self, text="## Company snapshot\nAcme is growing [1].", error=None):
        self.text = text
        self.error = error
        self.calls = []

    def complete(self, prompt, system=None):
        self.calls.append({"prompt": prompt, "system": system})
        if self.error:
            raise self.error
        return LLMResponse(text=self.text, provider="fake", model="fake-model")


def signal(n, competitor="Rival Oy", headline="Rival news", summary="", created="2026-10-01T00:00:00+00:00"):
    return {"id": f"s{n}", "competitor_id": "c1", "competitor_name": competitor, "headline": headline,
            "category": "product", "importance": "high", "summary": summary,
            "source_title": f"Source {n}", "source_url": f"https://radar.example/{n}", "status": "new",
            "created_at": created}


def fake_signals(items=()):
    calls = []

    def signals():
        calls.append(1)
        return list(items)
    signals.calls = calls
    return signals


def fake_notes(text="Last call: Acme wants pricing for 50 seats.", filename="acme-notes.docx"):
    seen = []

    def notes(file_id):
        seen.append(file_id)
        return {"id": file_id, "filename": filename, "text": text}
    notes.seen = seen
    return notes


def failing(*_args, **_kwargs):
    raise RuntimeError("peer said: secret upstream text")


__all__ = ["FakeSearch", "FakeLLM", "fake_reader", "fake_signals", "fake_notes", "signal", "failing", "ProviderError"]
