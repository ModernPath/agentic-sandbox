"""Page readers: read one known URL and return PageContent.

Every reader checks the URL locally first (http/https, public addresses only), so a
rejected URL never reaches a provider. Provider readers return text capped at max_chars.
"""

from __future__ import annotations

import urllib.parse
from typing import Optional

from .config import DEFAULT_LLM_MODELS, Settings
from .errors import ConfigurationError, ProviderError
from .fetch import PageContent, Resolver, extract_text, fetch_page, validate_url
from .llm import GEMINI_INTERACTIONS_URL
from .transport import JsonTransport, urllib_transport

EXA_CONTENTS_URL = "https://api.exa.ai/contents"


def _title_from_url(url: str) -> str:
    return urllib.parse.urlsplit(url).hostname or url


class LocalPageReader:
    def __init__(self, max_chars: int, timeout: float = 30):
        self.max_chars = max_chars
        self.timeout = timeout

    def read(self, url: str) -> PageContent:
        return fetch_page(url, max_chars=self.max_chars, timeout=self.timeout)


class ExaContentsReader:
    """Exa /contents: extraction on Exa's side. Options follow the Exa skill (explicit text budget)."""

    def __init__(self, *, api_key: str, max_chars: int, transport: JsonTransport = urllib_transport,
                 timeout: float = 30, resolver: Optional[Resolver] = None):
        self.api_key = api_key
        self.max_chars = max_chars
        self.transport = transport
        self.timeout = timeout
        self.resolver = resolver

    def read(self, url: str) -> PageContent:
        checked = validate_url(url, resolver=self.resolver)
        body = {"urls": [checked], "text": {"maxCharacters": self.max_chars}}
        payload = self.transport(EXA_CONTENTS_URL, {"x-api-key": self.api_key}, body, self.timeout)
        status = next((s for s in payload.get("statuses") or [] if s.get("id") == checked), None)
        if status is not None and status.get("status") != "success":
            tag = status.get("tag") or status.get("status") or "unknown"
            raise ProviderError(f"Exa could not read the page ({tag})")
        results = payload.get("results") or []
        if not results:
            raise ProviderError("Exa returned no content for the page")
        first = results[0]
        text = (first.get("text") or "")[: self.max_chars]
        return PageContent(url=checked, title=first.get("title") or _title_from_url(checked), text=text.strip())


class GeminiUrlContextReader:
    """Gemini url_context: the model retrieves the page. The text is model output, so it may be a paraphrase."""

    def __init__(self, *, api_key: str, model: str, max_chars: int, transport: JsonTransport = urllib_transport,
                 timeout: float = 30, resolver: Optional[Resolver] = None):
        self.api_key = api_key
        self.model = model
        self.max_chars = max_chars
        self.transport = transport
        self.timeout = timeout
        self.resolver = resolver

    def read(self, url: str) -> PageContent:
        checked = validate_url(url, resolver=self.resolver)
        prompt = ("Return the complete readable text of this web page, without commentary or summary.\n"
                  f"{checked}")
        body = {"model": self.model, "input": prompt, "tools": [{"type": "url_context"}]}
        payload = self.transport(GEMINI_INTERACTIONS_URL, {"x-goog-api-key": self.api_key}, body, self.timeout)
        retrievals = [r for step in payload.get("steps", []) if "url_context" in step.get("type", "")
                      for r in step.get("result") or []]
        own = [r.get("status") for r in retrievals if r.get("url") == checked]
        if not own or any(s != "success" for s in own):
            observed = ", ".join(str(s) for s in own) or "none"
            raise ProviderError(f"Gemini could not retrieve the page (url_context status: {observed})")
        text = "".join(
            item.get("text", "")
            for step in payload.get("steps", []) if step.get("type") == "model_output"
            for item in step.get("content", []) if item.get("type") == "text"
        ).strip()
        if not text:
            raise ProviderError("Gemini returned no text for the page")
        return PageContent(url=checked, title=_title_from_url(checked), text=text[: self.max_chars])


def build_reader(settings: Settings, transport: JsonTransport = urllib_transport, resolver: Optional[Resolver] = None):
    provider = settings.reader_provider
    if provider == "local":
        return LocalPageReader(max_chars=settings.fetch_max_chars, timeout=settings.http_timeout_seconds)
    if provider == "exa":
        if not settings.exa_api_key:
            raise ConfigurationError("EXA_API_KEY is required for SANDBOX_READER_PROVIDER=exa")
        return ExaContentsReader(api_key=settings.exa_api_key, max_chars=settings.fetch_max_chars,
                                 transport=transport, timeout=settings.http_timeout_seconds, resolver=resolver)
    if not settings.gemini_api_key:
        raise ConfigurationError("GEMINI_API_KEY is required for SANDBOX_READER_PROVIDER=gemini")
    return GeminiUrlContextReader(api_key=settings.gemini_api_key,
                                  model=settings.reader_model or DEFAULT_LLM_MODELS["gemini"],
                                  max_chars=settings.fetch_max_chars, transport=transport,
                                  timeout=settings.http_timeout_seconds, resolver=resolver)
