"""LLM client protocol and provider adapters (Gemini, OpenAI Responses API)."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Optional, Protocol

from .config import Settings
from .errors import ConfigurationError
from .usage import metered
from .tools import Tool, ToolRun, run_anthropic, run_gemini, run_openai_style
from .transport import JsonTransport, urllib_transport

GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


IMAGE_MIME_TYPES = ("image/png", "image/jpeg", "image/webp")


def _check_image(mime: str) -> None:
    if mime not in IMAGE_MIME_TYPES:
        raise ValueError(f"Vision needs an image ({', '.join(IMAGE_MIME_TYPES)}), not {mime}")


def _b64(image: bytes) -> str:
    return base64.b64encode(image).decode("ascii")


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str


class LLMClient(Protocol):
    provider: str
    model: str

    def complete(self, prompt: str, system: Optional[str] = None) -> LLMResponse: ...

    def complete_with_image(self, prompt: str, image: bytes, mime: str,
                            system: Optional[str] = None) -> LLMResponse: ...

    def run_with_tools(self, prompt: str, *, system: Optional[str] = None, history=(), tools=(),
                       max_calls: int = 8) -> ToolRun: ...


class GeminiLLM:
    provider = "gemini"

    def __init__(self, *, api_key: str, model: str, transport: JsonTransport = urllib_transport, timeout: float = 30):
        self.api_key = api_key
        self.model = model
        self.transport = transport
        self.timeout = timeout

    def complete(self, prompt: str, system: Optional[str] = None) -> LLMResponse:
        # The system text is prepended to the input: this is the one request shape
        # confirmed against the provider docs (see technical spec, D3).
        text_input = f"{system}\n\n{prompt}" if system else prompt
        body = {"model": self.model, "input": text_input}
        headers = {"x-goog-api-key": self.api_key}
        payload = self.transport(GEMINI_INTERACTIONS_URL, headers, body, self.timeout)
        parts = [
            item.get("text", "")
            for step in payload.get("steps", [])
            if step.get("type") == "model_output"
            for item in step.get("content", [])
            if item.get("type") == "text"
        ]
        return LLMResponse(text="".join(parts).strip(), provider=self.provider, model=self.model)

    def complete_with_image(self, prompt: str, image: bytes, mime: str, system: Optional[str] = None) -> LLMResponse:
        _check_image(mime)
        text_input = f"{system}\n\n{prompt}" if system else prompt
        body = {"model": self.model, "input": [
            {"type": "text", "text": text_input},
            {"type": "image", "data": _b64(image), "mime_type": mime},
        ]}
        payload = self.transport(GEMINI_INTERACTIONS_URL, {"x-goog-api-key": self.api_key}, body, self.timeout)
        parts = [
            item.get("text", "")
            for step in payload.get("steps", [])
            if step.get("type") == "model_output"
            for item in step.get("content", [])
            if item.get("type") == "text"
        ]
        return LLMResponse(text="".join(parts).strip(), provider=self.provider, model=self.model)

    def run_with_tools(self, prompt: str, *, system: Optional[str] = None, history=(), tools=(),
                       max_calls: int = 8) -> ToolRun:
        return run_gemini(transport=self.transport, url=GEMINI_INTERACTIONS_URL, headers={"x-goog-api-key": self.api_key},
                          model=self.model, prompt=prompt, system=system, history=history, tools=tools,
                          max_calls=max_calls, timeout=self.timeout)


class OpenAILLM:
    provider = "openai"

    def __init__(self, *, api_key: str, model: str, transport: JsonTransport = urllib_transport, timeout: float = 30):
        self.api_key = api_key
        self.model = model
        self.transport = transport
        self.timeout = timeout

    def complete(self, prompt: str, system: Optional[str] = None) -> LLMResponse:
        body = {"model": self.model, "input": prompt}
        if system:
            body["instructions"] = system
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = self.transport(OPENAI_RESPONSES_URL, headers, body, self.timeout)
        return LLMResponse(text=extract_openai_text(payload).strip(), provider=self.provider, model=self.model)

    def complete_with_image(self, prompt: str, image: bytes, mime: str, system: Optional[str] = None) -> LLMResponse:
        _check_image(mime)
        body = {"model": self.model, "input": _openai_image_input(prompt, image, mime)}
        if system:
            body["instructions"] = system
        payload = self.transport(OPENAI_RESPONSES_URL, {"Authorization": f"Bearer {self.api_key}"}, body, self.timeout)
        return LLMResponse(text=extract_openai_text(payload).strip(), provider=self.provider, model=self.model)

    def run_with_tools(self, prompt: str, *, system: Optional[str] = None, history=(), tools=(),
                       max_calls: int = 8) -> ToolRun:
        return run_openai_style(transport=self.transport, url=OPENAI_RESPONSES_URL,
                                headers={"Authorization": f"Bearer {self.api_key}"}, model=self.model,
                                provider=self.provider, prompt=prompt, system=system, history=history,
                                tools=tools, max_calls=max_calls, timeout=self.timeout)


def _require_azure(settings: Settings) -> None:
    missing = [name for name, value in (("AZURE_OPENAI_API_KEY", settings.azure_api_key),
                                        ("AZURE_OPENAI_ENDPOINT", settings.azure_endpoint),
                                        ("AZURE_OPENAI_DEPLOYMENT", settings.azure_deployment)) if not value]
    if missing:
        raise ConfigurationError(f"{', '.join(missing)} required for SANDBOX_LLM_PROVIDER=azure")


def _openai_image_input(prompt: str, image: bytes, mime: str) -> list:
    data_url = f"data:{mime};base64,{_b64(image)}"
    return [{"role": "user", "content": [
        {"type": "input_text", "text": prompt},
        {"type": "input_image", "image_url": data_url},
    ]}]


def extract_openai_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    return "".join(
        item.get("text", "")
        for output in payload.get("output", [])
        for item in output.get("content", []) or []
        if item.get("type") == "output_text"
    )


class AzureOpenAILLM:
    """OpenAI Responses API hosted on Azure AI Foundry: endpoint, api-key header, deployment name as model."""

    provider = "azure"

    def __init__(self, *, endpoint: str, api_key: str, deployment: str, transport: JsonTransport = urllib_transport,
                 timeout: float = 30):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = deployment
        self.transport = transport
        self.timeout = timeout

    def complete(self, prompt: str, system: Optional[str] = None) -> LLMResponse:
        body = {"model": self.model, "input": prompt}
        if system:
            body["instructions"] = system
        payload = self.transport(f"{self.endpoint}/openai/v1/responses", {"api-key": self.api_key}, body, self.timeout)
        return LLMResponse(text=extract_openai_text(payload).strip(), provider=self.provider, model=self.model)

    def complete_with_image(self, prompt: str, image: bytes, mime: str, system: Optional[str] = None) -> LLMResponse:
        _check_image(mime)
        body = {"model": self.model, "input": _openai_image_input(prompt, image, mime)}
        if system:
            body["instructions"] = system
        payload = self.transport(f"{self.endpoint}/openai/v1/responses", {"api-key": self.api_key}, body, self.timeout)
        return LLMResponse(text=extract_openai_text(payload).strip(), provider=self.provider, model=self.model)

    def run_with_tools(self, prompt: str, *, system: Optional[str] = None, history=(), tools=(),
                       max_calls: int = 8) -> ToolRun:
        return run_openai_style(transport=self.transport, url=f"{self.endpoint}/openai/v1/responses",
                                headers={"api-key": self.api_key}, model=self.model, provider=self.provider,
                                prompt=prompt, system=system, history=history, tools=tools, max_calls=max_calls,
                                timeout=self.timeout)


def build_llm(settings: Settings, transport: JsonTransport = urllib_transport) -> LLMClient:
    transport = metered(transport)  # usage is recorded for track_usage(); behaviour is unchanged
    model = settings.model_for_llm()
    if settings.llm_provider == "azure":
        _require_azure(settings)
        return AzureOpenAILLM(endpoint=settings.azure_endpoint, api_key=settings.azure_api_key,
                              deployment=settings.azure_deployment, transport=transport,
                              timeout=settings.http_timeout_seconds)
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY is required for SANDBOX_LLM_PROVIDER=anthropic")
        return AnthropicLLM(api_key=settings.anthropic_api_key, model=model, transport=transport,
                            timeout=settings.http_timeout_seconds)
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise ConfigurationError("GEMINI_API_KEY is required for SANDBOX_LLM_PROVIDER=gemini")
        return GeminiLLM(api_key=settings.gemini_api_key, model=model, transport=transport,
                         timeout=settings.http_timeout_seconds)
    if not settings.openai_api_key:
        raise ConfigurationError("OPENAI_API_KEY is required for SANDBOX_LLM_PROVIDER=openai")
    return OpenAILLM(api_key=settings.openai_api_key, model=model, transport=transport,
                     timeout=settings.http_timeout_seconds)


ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_MAX_TOKENS = 2048


class AnthropicLLM:
    provider = "anthropic"

    def __init__(self, *, api_key: str, model: str, transport: JsonTransport = urllib_transport, timeout: float = 30,
                 max_tokens: int = ANTHROPIC_MAX_TOKENS):
        self.api_key = api_key
        self.model = model
        self.transport = transport
        self.timeout = timeout
        self.max_tokens = max_tokens

    def complete(self, prompt: str, system: Optional[str] = None) -> LLMResponse:
        body = {"model": self.model, "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}]}
        if system:
            body["system"] = system
        headers = {"x-api-key": self.api_key, "anthropic-version": ANTHROPIC_VERSION}
        payload = self.transport(ANTHROPIC_MESSAGES_URL, headers, body, self.timeout)
        text = "".join(
            block.get("text", "") for block in payload.get("content", []) or []
            if block.get("type") == "text"
        )
        return LLMResponse(text=text.strip(), provider=self.provider, model=self.model)

    def complete_with_image(self, prompt: str, image: bytes, mime: str, system: Optional[str] = None) -> LLMResponse:
        _check_image(mime)
        body = {"model": self.model, "max_tokens": self.max_tokens, "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": _b64(image)}},
            {"type": "text", "text": prompt},
        ]}]}
        if system:
            body["system"] = system
        headers = {"x-api-key": self.api_key, "anthropic-version": ANTHROPIC_VERSION}
        payload = self.transport(ANTHROPIC_MESSAGES_URL, headers, body, self.timeout)
        text = "".join(block.get("text", "") for block in payload.get("content", []) or []
                       if block.get("type") == "text")
        return LLMResponse(text=text.strip(), provider=self.provider, model=self.model)

    def run_with_tools(self, prompt: str, *, system: Optional[str] = None, history=(), tools=(),
                       max_calls: int = 8) -> ToolRun:
        return run_anthropic(transport=self.transport, url=ANTHROPIC_MESSAGES_URL,
                             headers={"x-api-key": self.api_key, "anthropic-version": ANTHROPIC_VERSION},
                             model=self.model, prompt=prompt, system=system, history=history, tools=tools,
                             max_calls=max_calls, max_tokens=self.max_tokens, timeout=self.timeout)
