"""Web search protocol and adapters: Gemini grounding, OpenAI web_search, Exa."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from .config import DEFAULT_LLM_MODELS, Settings
from .errors import ConfigurationError
from .llm import GEMINI_INTERACTIONS_URL, OPENAI_RESPONSES_URL, extract_openai_text
from .transport import JsonTransport, urllib_transport

EXA_SEARCH_URL = "https://api.exa.ai/search"


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True)
class SearchResponse:
    query: str
    provider: str
    answer: Optional[str]
    results: tuple[SearchResult, ...] = field(default_factory=tuple)


class SearchClient(Protocol):
    provider: str

    def search(self, query: str, max_results: int) -> SearchResponse: ...


class OpenAIWebSearch:
    provider = "openai"

    def __init__(self, *, api_key: str, model: str, transport: JsonTransport = urllib_transport, timeout: float = 30):
        self.api_key = api_key
        self.model = model
        self.transport = transport
        self.timeout = timeout

    def search(self, query: str, max_results: int) -> SearchResponse:
        body = {"model": self.model, "tools": [{"type": "web_search"}], "input": query}
        payload = self.transport(OPENAI_RESPONSES_URL, {"Authorization": f"Bearer {self.api_key}"}, body, self.timeout)
        citations = [
            annotation
            for output in payload.get("output", [])
            if output.get("type") == "message"
            for item in output.get("content", []) or []
            for annotation in item.get("annotations", []) or []
        ]
        return SearchResponse(
            query=query,
            provider=self.provider,
            answer=extract_openai_text(payload).strip() or None,
            results=_from_citations(citations, max_results),
        )


class AzureOpenAIWebSearch(OpenAIWebSearch):
    """OpenAI web_search tool on Azure AI Foundry (same Responses shape, Azure endpoint and api-key header)."""

    provider = "azure"

    def __init__(self, *, endpoint: str, api_key: str, deployment: str, transport: JsonTransport = urllib_transport,
                 timeout: float = 30):
        super().__init__(api_key=api_key, model=deployment, transport=transport, timeout=timeout)
        self.endpoint = endpoint.rstrip("/")

    def search(self, query: str, max_results: int) -> SearchResponse:
        body = {"model": self.model, "tools": [{"type": "web_search"}], "input": query}
        payload = self.transport(f"{self.endpoint}/openai/v1/responses", {"api-key": self.api_key}, body, self.timeout)
        citations = [
            annotation
            for output in payload.get("output", [])
            if output.get("type") == "message"
            for item in output.get("content", []) or []
            for annotation in item.get("annotations", []) or []
        ]
        return SearchResponse(query=query, provider=self.provider,
                              answer=extract_openai_text(payload).strip() or None,
                              results=_from_citations(citations, max_results))


class GeminiGroundingSearch:
    provider = "gemini"

    def __init__(self, *, api_key: str, model: str, transport: JsonTransport = urllib_transport, timeout: float = 30):
        self.api_key = api_key
        self.model = model
        self.transport = transport
        self.timeout = timeout

    def search(self, query: str, max_results: int) -> SearchResponse:
        body = {"model": self.model, "input": query, "tools": [{"type": "google_search"}]}
        payload = self.transport(GEMINI_INTERACTIONS_URL, {"x-goog-api-key": self.api_key}, body, self.timeout)
        steps = [step for step in payload.get("steps", []) if step.get("type") == "model_output"]
        items = [item for step in steps for item in step.get("content", []) if item.get("type") == "text"]
        answer = "".join(item.get("text", "") for item in items).strip() or None
        citations = [annotation for item in items for annotation in item.get("annotations", []) or []]
        return SearchResponse(query=query, provider=self.provider, answer=answer,
                              results=_from_citations(citations, max_results))


class ExaSearch:
    provider = "exa"

    def __init__(self, *, api_key: str, transport: JsonTransport = urllib_transport, timeout: float = 30):
        self.api_key = api_key
        self.transport = transport
        self.timeout = timeout

    def search(self, query: str, max_results: int) -> SearchResponse:
        body = {
            "query": query,
            "numResults": max_results,
            "contents": {"highlights": True},
        }
        payload = self.transport(EXA_SEARCH_URL, {"x-api-key": self.api_key}, body, self.timeout)
        results = [
            SearchResult(title=item.get("title") or item.get("url", ""), url=item.get("url", ""),
                         snippet=" ".join(h for h in (item.get("highlights") or []) if h))
            for item in payload.get("results", [])
            if item.get("url")
        ]
        return SearchResponse(query=query, provider=self.provider, answer=None,
                              results=tuple(_dedupe(results)[:max_results]))


def build_search(settings: Settings, transport: JsonTransport = urllib_transport) -> SearchClient:
    provider = settings.search_provider
    model = settings.search_model
    if provider == "none":
        raise ConfigurationError("Set SANDBOX_SEARCH_PROVIDER to gemini, openai, or exa to use web search")
    if provider == "azure":
        missing = [name for name, value in (("AZURE_OPENAI_API_KEY", settings.azure_api_key),
                                            ("AZURE_OPENAI_ENDPOINT", settings.azure_endpoint),
                                            ("AZURE_OPENAI_DEPLOYMENT", settings.azure_deployment)) if not value]
        if missing:
            raise ConfigurationError(f"{', '.join(missing)} required for SANDBOX_SEARCH_PROVIDER=azure")
        return AzureOpenAIWebSearch(endpoint=settings.azure_endpoint, api_key=settings.azure_api_key,
                                    deployment=model or settings.azure_deployment, transport=transport,
                                    timeout=settings.http_timeout_seconds)
    if provider == "exa":
        if not settings.exa_api_key:
            raise ConfigurationError("EXA_API_KEY is required for SANDBOX_SEARCH_PROVIDER=exa")
        return ExaSearch(api_key=settings.exa_api_key, transport=transport, timeout=settings.http_timeout_seconds)
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ConfigurationError("GEMINI_API_KEY is required for SANDBOX_SEARCH_PROVIDER=gemini")
        return GeminiGroundingSearch(api_key=settings.gemini_api_key, model=model or DEFAULT_LLM_MODELS["gemini"],
                                     transport=transport, timeout=settings.http_timeout_seconds)
    if not settings.openai_api_key:
        raise ConfigurationError("OPENAI_API_KEY is required for SANDBOX_SEARCH_PROVIDER=openai")
    return OpenAIWebSearch(api_key=settings.openai_api_key, model=model or DEFAULT_LLM_MODELS["openai"],
                           transport=transport, timeout=settings.http_timeout_seconds)


def _from_citations(citations: list[dict], max_results: int) -> tuple[SearchResult, ...]:
    results = [
        SearchResult(title=c.get("title") or c.get("url", ""), url=c.get("url", ""))
        for c in citations
        if c.get("type", "url_citation") == "url_citation" and c.get("url")
    ]
    return tuple(_dedupe(results)[:max_results])


def _dedupe(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for result in results:
        if result.url not in seen:
            seen.add(result.url)
            unique.append(result)
    return unique
