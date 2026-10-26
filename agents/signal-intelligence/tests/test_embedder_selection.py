import pytest

from agent_env import make_embedder
from intelligence_embeddings import GeminiEmbedder
from sandbox_blocks.embeddings import OpenAIEmbedder


def test_gemini_remains_the_default_when_its_key_is_set():
    embedder = make_embedder({"GEMINI_API_KEY": "g-key"})
    assert isinstance(embedder, GeminiEmbedder)
    assert embedder.config == "gemini-embedding-2:768:retrieval-prefix-v1"


def test_openai_is_selected_by_provider_variable():
    embedder = make_embedder({"KNOWLEDGE_EMBEDDING_PROVIDER": "openai", "OPENAI_API_KEY": "o-key"})
    assert isinstance(embedder, OpenAIEmbedder)
    assert embedder.model == "text-embedding-3-small" and embedder.dimensions == 768
    assert embedder.config == "openai:text-embedding-3-small:768:v1"


def test_openai_model_can_be_overridden():
    embedder = make_embedder({"KNOWLEDGE_EMBEDDING_PROVIDER": "openai", "OPENAI_API_KEY": "o-key",
                              "OPENAI_EMBEDDING_MODEL": "text-embedding-3-large"})
    assert embedder.model == "text-embedding-3-large"


@pytest.mark.parametrize("env", [
    {"KNOWLEDGE_EMBEDDING_PROVIDER": "openai"},          # no key: semantic search stays off
    {"KNOWLEDGE_SEMANTIC_ENABLED": "false", "GEMINI_API_KEY": "g", "OPENAI_API_KEY": "o"},
    {},                                                    # no key at all
])
def test_no_key_or_disabled_means_lexical_only(env):
    assert make_embedder(env) is None


def test_gemini_and_openai_indexes_never_share_a_config():
    gemini = make_embedder({"GEMINI_API_KEY": "g"})
    openai = make_embedder({"KNOWLEDGE_EMBEDDING_PROVIDER": "openai", "OPENAI_API_KEY": "o"})
    assert gemini.config != openai.config
