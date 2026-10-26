"""Text embeddings: OpenAI and Azure OpenAI adapters with bounded, validated output.

Each embedder has a `config` identity string. Indexes are keyed by it, so vectors from
different models or dimensions are never compared with each other.
"""

from __future__ import annotations

import math
from typing import Optional, Protocol, Sequence

from .config import Settings
from .errors import ConfigurationError, ProviderError
from .transport import JsonTransport, urllib_transport

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
MAX_INPUTS = 16
MAX_TEXT_CHARS = 2400


class EmbeddingClient(Protocol):
    provider: str
    model: str
    dimensions: int
    config: str

    def embed(self, texts: Sequence[str], *, query: bool = False) -> list[list[float]]: ...


class OpenAIEmbedder:
    provider = "openai"

    def __init__(self, *, api_key: str, model: str = DEFAULT_OPENAI_EMBEDDING_MODEL, dimensions: int = 768,
                 transport: JsonTransport = urllib_transport, timeout: float = 30):
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.transport = transport
        self.timeout = timeout

    @property
    def config(self) -> str:
        return f"{self.provider}:{self.model}:{self.dimensions}:v1"

    def embed(self, texts: Sequence[str], *, query: bool = False) -> list[list[float]]:
        _check_inputs(texts)
        body = {"model": self.model, "input": list(texts), "dimensions": self.dimensions}
        payload = self.transport(OPENAI_EMBEDDINGS_URL, {"Authorization": f"Bearer {self.api_key}"}, body, self.timeout)
        return _vectors(payload, len(texts), self.dimensions)


class AzureOpenAIEmbedder(OpenAIEmbedder):
    """The same embeddings API on an Azure AI Foundry resource; the deployment name is the model."""

    provider = "azure"

    def __init__(self, *, endpoint: str, api_key: str, deployment: str, dimensions: int = 768,
                 transport: JsonTransport = urllib_transport, timeout: float = 30):
        super().__init__(api_key=api_key, model=deployment, dimensions=dimensions, transport=transport,
                         timeout=timeout)
        self.endpoint = endpoint.rstrip("/")

    def embed(self, texts: Sequence[str], *, query: bool = False) -> list[list[float]]:
        _check_inputs(texts)
        body = {"model": self.model, "input": list(texts), "dimensions": self.dimensions}
        payload = self.transport(f"{self.endpoint}/openai/v1/embeddings", {"api-key": self.api_key}, body, self.timeout)
        return _vectors(payload, len(texts), self.dimensions)


def build_embedder(settings: Settings, transport: JsonTransport = urllib_transport) -> Optional[EmbeddingClient]:
    provider = settings.embedding_provider
    if provider == "none":
        return None
    if provider == "openai":
        if not settings.openai_api_key:
            raise ConfigurationError("OPENAI_API_KEY is required for SANDBOX_EMBEDDING_PROVIDER=openai")
        return OpenAIEmbedder(api_key=settings.openai_api_key,
                              model=settings.embedding_model or DEFAULT_OPENAI_EMBEDDING_MODEL,
                              dimensions=settings.embedding_dimensions, transport=transport,
                              timeout=settings.http_timeout_seconds)
    missing = [name for name, value in (("AZURE_OPENAI_API_KEY", settings.azure_api_key),
                                        ("AZURE_OPENAI_ENDPOINT", settings.azure_endpoint),
                                        ("SANDBOX_EMBEDDING_MODEL", settings.embedding_model)) if not value]
    if missing:
        raise ConfigurationError(f"{', '.join(missing)} required for SANDBOX_EMBEDDING_PROVIDER=azure")
    return AzureOpenAIEmbedder(endpoint=settings.azure_endpoint, api_key=settings.azure_api_key,
                               deployment=settings.embedding_model, dimensions=settings.embedding_dimensions,
                               transport=transport, timeout=settings.http_timeout_seconds)


def _check_inputs(texts: Sequence[str]) -> None:
    if not texts or len(texts) > MAX_INPUTS:
        raise ValueError(f"Embed between 1 and {MAX_INPUTS} texts per request")
    if any(len(text) > MAX_TEXT_CHARS for text in texts):
        raise ValueError(f"Each text must be at most {MAX_TEXT_CHARS} characters")


def _vectors(payload: dict, count: int, dimensions: int) -> list[list[float]]:
    try:
        items = sorted(payload["data"], key=lambda item: item["index"])
        if len(items) != count:
            raise ValueError("count")
        result = []
        for item in items:
            values = [float(x) for x in item["embedding"]]
            if len(values) != dimensions or not all(math.isfinite(x) for x in values):
                raise ValueError("shape")
            norm = math.sqrt(sum(x * x for x in values))
            if norm <= 0:
                raise ValueError("zero")
            result.append([x / norm for x in values])
        return result
    except (KeyError, TypeError, ValueError):
        raise ProviderError("Embedding response was invalid") from None
