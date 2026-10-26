import pytest

from blocks_fakes import RecordingTransport
from sandbox_blocks.config import Settings
from sandbox_blocks.errors import ConfigurationError
from sandbox_blocks.llm import AzureOpenAILLM, build_llm
from sandbox_blocks.search import AzureOpenAIWebSearch, build_search

ENDPOINT = "https://example-resource.services.ai.azure.com"
ENV = {
    "SANDBOX_LLM_PROVIDER": "azure",
    "AZURE_OPENAI_API_KEY": "az-key-123",
    "AZURE_OPENAI_ENDPOINT": ENDPOINT + "/",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-6-luna",
}


def test_azure_request_uses_v1_path_api_key_header_and_deployment_as_model():  # A-1
    transport = RecordingTransport({"output_text": "OK"})
    llm = AzureOpenAILLM(endpoint=ENDPOINT + "/", api_key="az-key-123", deployment="gpt-6-luna", transport=transport)
    result = llm.complete("Say OK", system="Be terse")
    call = transport.calls[0]
    assert call["url"] == ENDPOINT + "/openai/v1/responses"
    assert call["headers"] == {"api-key": "az-key-123"}
    assert call["body"] == {"model": "gpt-6-luna", "input": "Say OK", "instructions": "Be terse"}
    assert result.text == "OK" and result.provider == "azure" and result.model == "gpt-6-luna"


def test_build_llm_selects_azure_with_deployment_name():  # A-2
    settings = Settings.from_env(ENV)
    llm = build_llm(settings, transport=RecordingTransport({}))
    assert isinstance(llm, AzureOpenAILLM)
    assert llm.model == "gpt-6-luna"


@pytest.mark.parametrize("missing", ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT"])
def test_missing_azure_setting_fails_before_any_call(missing):  # A-3
    env = {k: v for k, v in ENV.items() if k != missing}
    transport = RecordingTransport({})
    with pytest.raises(ConfigurationError, match=missing):
        build_llm(Settings.from_env(env), transport=transport)
    assert transport.calls == []


def test_azure_search_uses_web_search_tool_on_the_azure_endpoint():  # A-4
    response = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "Answer",
                "annotations": [{"type": "url_citation", "url": "https://a.example", "title": "A"}]}]}]}
    transport = RecordingTransport(response)
    search = AzureOpenAIWebSearch(endpoint=ENDPOINT, api_key="az-key-123", deployment="gpt-6-luna", transport=transport)
    result = search.search("topic", max_results=3)
    call = transport.calls[0]
    assert call["url"] == ENDPOINT + "/openai/v1/responses"
    assert call["headers"] == {"api-key": "az-key-123"}
    assert call["body"]["tools"] == [{"type": "web_search"}] and call["body"]["model"] == "gpt-6-luna"
    assert result.answer == "Answer" and [r.url for r in result.results] == ["https://a.example"]


def test_build_search_selects_azure():
    settings = Settings.from_env({**ENV, "SANDBOX_SEARCH_PROVIDER": "azure"})
    assert isinstance(build_search(settings, transport=RecordingTransport({})), AzureOpenAIWebSearch)
