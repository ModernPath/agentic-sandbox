import io
import json
import urllib.error

import pytest

from sandbox_blocks.config import Settings
from sandbox_blocks.errors import ConfigurationError, ProviderError
from sandbox_blocks.llm import GeminiLLM, OpenAILLM, build_llm
from sandbox_blocks.transport import urllib_transport
from blocks_fakes import RecordingTransport


GEMINI_RESPONSE = {
    "steps": [
        {"type": "thought", "summary": "..."},
        {"type": "model_output", "content": [{"type": "text", "text": "Hello "}, {"type": "text", "text": "there"}]},
    ]
}


def test_gemini_complete_sends_key_model_and_input_and_parses_text():  # T5
    transport = RecordingTransport(GEMINI_RESPONSE)
    llm = GeminiLLM(api_key="g-key", model="gemini-test", transport=transport, timeout=7)

    result = llm.complete("Say hi", system="Be brief")

    call = transport.calls[0]
    assert call["url"] == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert call["headers"]["x-goog-api-key"] == "g-key"
    assert call["body"]["model"] == "gemini-test"
    assert call["body"]["input"] == "Be brief\n\nSay hi"
    assert call["timeout"] == 7
    assert result.text == "Hello there"
    assert result.provider == "gemini"
    assert result.model == "gemini-test"


def test_openai_complete_uses_responses_api_with_instructions():  # T6
    transport = RecordingTransport({"output_text": "Hi from GPT"})
    llm = OpenAILLM(api_key="o-key", model="gpt-test", transport=transport, timeout=5)

    result = llm.complete("Say hi", system="Be brief")

    call = transport.calls[0]
    assert call["url"] == "https://api.openai.com/v1/responses"
    assert call["headers"]["Authorization"] == "Bearer o-key"
    assert call["body"] == {"model": "gpt-test", "input": "Say hi", "instructions": "Be brief"}
    assert result.text == "Hi from GPT"
    assert result.provider == "openai"


def test_openai_text_is_extracted_from_output_items_when_output_text_missing():  # T7
    response = {
        "output": [
            {"type": "web_search_call", "id": "ws_1"},
            {"type": "message", "content": [{"type": "output_text", "text": "From items"}]},
        ]
    }
    llm = OpenAILLM(api_key="o-key", model="m", transport=RecordingTransport(response))
    assert llm.complete("x").text == "From items"


def test_missing_key_fails_before_any_call():  # T8
    transport = RecordingTransport({})
    settings = Settings.from_env({"SANDBOX_LLM_PROVIDER": "openai"})
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        build_llm(settings, transport=transport)
    assert transport.calls == []


def test_build_llm_selects_adapter_from_env():
    settings = Settings.from_env({"SANDBOX_LLM_PROVIDER": "openai", "OPENAI_API_KEY": "k", "SANDBOX_LLM_MODEL": "m1"})
    llm = build_llm(settings, transport=RecordingTransport({}))
    assert isinstance(llm, OpenAILLM)
    assert llm.model == "m1"


def test_http_error_becomes_provider_error_without_key(monkeypatch):  # T9
    def fake_urlopen(request, timeout):
        body = io.BytesIO(b'{"error": "rate limited for key secret-key"}')
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many", {}, body)

    monkeypatch.setattr("sandbox_blocks.transport.urllib.request.urlopen", fake_urlopen)
    llm = GeminiLLM(api_key="secret-key", model="m", transport=urllib_transport)

    with pytest.raises(ProviderError) as error:
        llm.complete("x")
    assert "429" in str(error.value)
    assert "secret-key" not in str(error.value)
