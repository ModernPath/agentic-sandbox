import math

import pytest

from blocks_fakes import RecordingTransport
from sandbox_blocks.config import Settings
from sandbox_blocks.embeddings import AzureOpenAIEmbedder, OpenAIEmbedder, build_embedder
from sandbox_blocks.errors import ConfigurationError, ProviderError


def vector(seed, dims=768):
    values = [math.sin(seed + i) for i in range(dims)]
    return values


def response(vectors, order=None):
    items = [{"index": i, "embedding": v} for i, v in enumerate(vectors)]
    if order:
        items = [items[i] for i in order]
    return {"data": items, "usage": {"prompt_tokens": 4, "total_tokens": 4}}


def test_openai_request_asks_for_requested_dimensions():  # E-1
    transport = RecordingTransport(response([vector(1)]))
    embedder = OpenAIEmbedder(api_key="o-key", model="text-embedding-3-small", dimensions=768, transport=transport)
    embedder.embed(["hello"])
    call = transport.calls[0]
    assert call["url"] == "https://api.openai.com/v1/embeddings"
    assert call["headers"] == {"Authorization": "Bearer o-key"}
    assert call["body"] == {"model": "text-embedding-3-small", "input": ["hello"], "dimensions": 768}


def test_vectors_are_returned_in_input_order_and_normalised():  # E-2
    transport = RecordingTransport(response([vector(1), vector(2)], order=[1, 0]))
    vectors = OpenAIEmbedder(api_key="k", dimensions=768, transport=transport).embed(["a", "b"])
    assert len(vectors) == 2 and all(len(v) == 768 for v in vectors)
    assert vectors[0] == pytest.approx([x / math.sqrt(sum(y * y for y in vector(1))) for x in vector(1)])
    assert all(abs(math.sqrt(sum(x * x for x in v)) - 1) < 1e-9 for v in vectors)


def test_query_flag_does_not_change_the_openai_request():  # E-3
    transport = RecordingTransport(response([vector(1)]))
    OpenAIEmbedder(api_key="k", dimensions=768, transport=transport).embed(["q"], query=True)
    assert transport.calls[0]["body"]["input"] == ["q"]


def test_identity_string_separates_vector_spaces():  # E-4
    small = OpenAIEmbedder(api_key="k", model="text-embedding-3-small", dimensions=768)
    large = OpenAIEmbedder(api_key="k", model="text-embedding-3-large", dimensions=768)
    other_dims = OpenAIEmbedder(api_key="k", model="text-embedding-3-small", dimensions=1536)
    assert small.config == "openai:text-embedding-3-small:768:v1"
    assert len({small.config, large.config, other_dims.config}) == 3


def test_wrong_dimension_count_or_bad_values_are_rejected():  # E-5
    short = RecordingTransport(response([[0.1, 0.2]]))
    with pytest.raises(ProviderError):
        OpenAIEmbedder(api_key="k", dimensions=768, transport=short).embed(["x"])
    nan = RecordingTransport(response([[float("nan")] * 768]))
    with pytest.raises(ProviderError):
        OpenAIEmbedder(api_key="k", dimensions=768, transport=nan).embed(["x"])


def test_input_bounds_are_enforced_before_any_call():  # E-6
    transport = RecordingTransport(response([]))
    embedder = OpenAIEmbedder(api_key="k", dimensions=768, transport=transport)
    with pytest.raises(ValueError):
        embedder.embed([])
    with pytest.raises(ValueError):
        embedder.embed(["x"] * 17)
    with pytest.raises(ValueError):
        embedder.embed(["x" * 9000])
    assert transport.calls == []


def test_azure_embedder_uses_endpoint_api_key_and_deployment():  # E-7
    transport = RecordingTransport(response([vector(1)]))
    embedder = AzureOpenAIEmbedder(endpoint="https://r.services.ai.azure.com/", api_key="az",
                                   deployment="emb-small", dimensions=768, transport=transport)
    embedder.embed(["hello"])
    call = transport.calls[0]
    assert call["url"] == "https://r.services.ai.azure.com/openai/v1/embeddings"
    assert call["headers"] == {"api-key": "az"} and call["body"]["model"] == "emb-small"
    assert embedder.config == "azure:emb-small:768:v1"


def test_build_embedder_is_off_by_default_and_checks_keys():  # E-8
    assert build_embedder(Settings.from_env({})) is None
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        build_embedder(Settings.from_env({"SANDBOX_EMBEDDING_PROVIDER": "openai"}))
    built = build_embedder(Settings.from_env({"SANDBOX_EMBEDDING_PROVIDER": "openai", "OPENAI_API_KEY": "k"}))
    assert isinstance(built, OpenAIEmbedder) and built.model == "text-embedding-3-small" and built.dimensions == 768


def test_unknown_embedding_provider_is_rejected():
    with pytest.raises(ConfigurationError, match="SANDBOX_EMBEDDING_PROVIDER"):
        Settings.from_env({"SANDBOX_EMBEDDING_PROVIDER": "gemini"})
