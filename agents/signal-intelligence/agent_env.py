"""Agent-scoped environment and service construction."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

AGENT_DIR = Path(__file__).resolve().parent


def load_agent_environment() -> None:
    path = AGENT_DIR / ".env.local"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#") or "=" not in value:
            continue
        key, content = value.split("=", 1)
        key = key.strip()
        if key in {"DATABASE_URL", "GEMINI_API_KEY", "OPENAI_API_KEY", "SIGNAL_INTELLIGENCE_MODEL",
                   "KNOWLEDGE_SEMANTIC_ENABLED", "KNOWLEDGE_EMBEDDING_PROVIDER", "KNOWLEDGE_EMBEDDING_MODEL",
                   "OPENAI_EMBEDDING_MODEL"}:
            os.environ.setdefault(key, content.strip().strip('"').strip("'"))


def make_store():
    from memory.memory import IntelligenceStore

    load_agent_environment()
    url = os.environ.get("DATABASE_URL", "")
    try:
        parsed = make_url(url)
        if parsed.drivername != "postgresql+psycopg" or not parsed.database:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError("DATABASE_URL must be a postgresql+psycopg URL") from None
    store = IntelligenceStore(create_engine(url, pool_pre_ping=True,
                                            connect_args={"connect_timeout": 3}))
    store.check_schema()
    return store


def make_service(*, use_subagents: bool = True):
    from intelligence_provider import GeminiProvider
    from intelligence_service import IntelligenceService
    from intelligence_subagents import SubagentRunner

    store = make_store()
    key = os.environ.get("GEMINI_API_KEY", "")
    model = os.environ.get("SIGNAL_INTELLIGENCE_MODEL", "gemini-2.5-flash")
    provider = GeminiProvider(key, model=model) if key and not use_subagents else None
    runner = SubagentRunner(database_url=store.engine.url.render_as_string(hide_password=False)) if key and use_subagents else None
    embedder = make_embedder(os.environ)
    return IntelligenceService(store, provider=provider, subagent_runner=runner, embedder=embedder)


OPENAI_MIN_SIMILARITY = 0.35


def make_embedder(environ):
    """Semantic search embedder, or None (lexical only). Gemini is the default; OpenAI is the alternative.

    KNOWLEDGE_EMBEDDING_PROVIDER=openai uses the sandbox embedding block with OPENAI_API_KEY and
    OPENAI_EMBEDDING_MODEL (default text-embedding-3-small, 768 dimensions). Each provider has its own
    index identity (embedder.config), so switching providers re-embeds the knowledge base.
    """
    if environ.get("KNOWLEDGE_SEMANTIC_ENABLED", "true").lower() != "true":
        return None
    if environ.get("KNOWLEDGE_EMBEDDING_PROVIDER", "gemini").lower() == "openai":
        key = environ.get("OPENAI_API_KEY", "")
        if not key:
            return None
        from sandbox_blocks.embeddings import OpenAIEmbedder

        embedder = OpenAIEmbedder(api_key=key, model=environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                                  dimensions=768)
        # Similarity floor for OpenAI's score range: 0.55 (Gemini's) removed every semantic hit on the
        # labelled fixture; the correct passage scored 0.40-0.49. Provisional until a larger set confirms it.
        embedder.min_similarity = OPENAI_MIN_SIMILARITY
        return embedder
    key = environ.get("GEMINI_API_KEY", "")
    if not key:
        return None
    from intelligence_embeddings import GeminiEmbedder

    return GeminiEmbedder(key, environ.get("KNOWLEDGE_EMBEDDING_MODEL", "gemini-embedding-2"))
