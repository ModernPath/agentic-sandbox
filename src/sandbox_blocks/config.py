"""Environment-driven settings for building blocks."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

from .errors import ConfigurationError

LLM_PROVIDERS = ("gemini", "openai", "anthropic", "azure")
SEARCH_PROVIDERS = ("none", "gemini", "openai", "exa", "azure")
READER_PROVIDERS = ("local", "exa", "gemini")
EMBEDDING_PROVIDERS = ("none", "openai", "azure")

EXA_AGENT_EFFORTS = ("minimal", "low", "medium", "high", "xhigh", "auto", "ultra")

DEFAULT_LLM_MODELS = {"gemini": "gemini-3.8-flash", "openai": "gpt-6-astra", "anthropic": "claude-sonnet-5-5"}


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "gemini"
    llm_model: Optional[str] = None
    search_provider: str = "none"
    search_model: Optional[str] = None
    search_max_results: int = 5
    fetch_max_chars: int = 8000
    http_timeout_seconds: float = 30.0
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    exa_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    reader_provider: str = "local"
    embedding_provider: str = "none"
    embedding_model: Optional[str] = None
    embedding_dimensions: int = 768
    reader_model: Optional[str] = None
    azure_api_key: Optional[str] = None
    azure_endpoint: Optional[str] = None
    azure_deployment: Optional[str] = None
    exa_agent_effort: str = "auto"
    exa_agent_max_cost_dollars: float = 2.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> "Settings":
        llm_provider = environ.get("SANDBOX_LLM_PROVIDER", "gemini").strip().lower()
        search_provider = environ.get("SANDBOX_SEARCH_PROVIDER", "none").strip().lower()
        if llm_provider not in LLM_PROVIDERS:
            raise ConfigurationError(
                f"SANDBOX_LLM_PROVIDER must be one of: {', '.join(LLM_PROVIDERS)}"
            )
        if search_provider not in SEARCH_PROVIDERS:
            raise ConfigurationError(
                f"SANDBOX_SEARCH_PROVIDER must be one of: {', '.join(SEARCH_PROVIDERS)}"
            )
        return cls(
            llm_provider=llm_provider,
            llm_model=_optional(environ, "SANDBOX_LLM_MODEL"),
            search_provider=search_provider,
            search_model=_optional(environ, "SANDBOX_SEARCH_MODEL"),
            search_max_results=_positive_int(environ, "SANDBOX_SEARCH_MAX_RESULTS", 5),
            fetch_max_chars=_positive_int(environ, "SANDBOX_FETCH_MAX_CHARS", 8000),
            http_timeout_seconds=float(_positive_int(environ, "SANDBOX_HTTP_TIMEOUT_SECONDS", 30)),
            gemini_api_key=_optional(environ, "GEMINI_API_KEY"),
            openai_api_key=_optional(environ, "OPENAI_API_KEY"),
            exa_api_key=_optional(environ, "EXA_API_KEY"),
            anthropic_api_key=_optional(environ, "ANTHROPIC_API_KEY"),
            reader_provider=_reader_provider(environ),
            embedding_provider=_embedding_provider(environ),
            embedding_model=_optional(environ, "SANDBOX_EMBEDDING_MODEL"),
            embedding_dimensions=_positive_int(environ, "SANDBOX_EMBEDDING_DIMENSIONS", 768),
            reader_model=_optional(environ, "SANDBOX_READER_MODEL"),
            azure_api_key=_optional(environ, "AZURE_OPENAI_API_KEY"),
            azure_endpoint=_optional(environ, "AZURE_OPENAI_ENDPOINT"),
            azure_deployment=_optional(environ, "AZURE_OPENAI_DEPLOYMENT"),
            exa_agent_effort=_agent_effort(environ),
            exa_agent_max_cost_dollars=_cost_dollars(environ),
        )

    def model_for_llm(self) -> str:
        if self.llm_provider == "azure":
            return self.llm_model or self.azure_deployment or ""
        return self.llm_model or DEFAULT_LLM_MODELS[self.llm_provider]


def _optional(environ: Mapping[str, str], name: str) -> Optional[str]:
    value = environ.get(name, "").strip()
    return value or None


def _positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw = environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive")
    return value


def _agent_effort(environ: Mapping[str, str]) -> str:
    effort = (environ.get("SANDBOX_EXA_AGENT_EFFORT") or "auto").strip().lower()
    if effort not in EXA_AGENT_EFFORTS:
        raise ConfigurationError(f"SANDBOX_EXA_AGENT_EFFORT must be one of: {', '.join(EXA_AGENT_EFFORTS)}")
    return effort


def _cost_dollars(environ: Mapping[str, str]) -> float:
    raw = (environ.get("SANDBOX_EXA_AGENT_MAX_COST_DOLLARS") or "").strip()
    if not raw:
        return 2.0
    try:
        value = float(raw)
    except ValueError as error:
        raise ConfigurationError("SANDBOX_EXA_AGENT_MAX_COST_DOLLARS must be a number") from error
    if not 1 <= value <= 100:
        raise ConfigurationError("SANDBOX_EXA_AGENT_MAX_COST_DOLLARS must be between 1 and 100")
    return value


def _reader_provider(environ: Mapping[str, str]) -> str:
    name = (environ.get("SANDBOX_READER_PROVIDER") or "local").strip().lower()
    if name not in READER_PROVIDERS:
        raise ConfigurationError(f"SANDBOX_READER_PROVIDER must be one of: {', '.join(READER_PROVIDERS)}")
    return name


def _embedding_provider(environ: Mapping[str, str]) -> str:
    name = (environ.get("SANDBOX_EMBEDDING_PROVIDER") or "none").strip().lower()
    if name not in EMBEDDING_PROVIDERS:
        raise ConfigurationError(f"SANDBOX_EMBEDDING_PROVIDER must be one of: {', '.join(EMBEDDING_PROVIDERS)}")
    return name
