import pytest

from blocks_fakes import RecordingTransport
from sandbox_blocks.config import Settings
from sandbox_blocks.errors import ConfigurationError
from sandbox_blocks.llm import AnthropicLLM, build_llm


def test_anthropic_request_shape():  # E-A1
    transport = RecordingTransport({"content": [{"type": "text", "text": "Hi"}]})
    llm = AnthropicLLM(api_key="a-key", model="claude-test", transport=transport, timeout=6)
    result = llm.complete("Say hi")
    call = transport.calls[0]
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["headers"]["x-api-key"] == "a-key"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    assert call["body"]["model"] == "claude-test"
    assert call["body"]["max_tokens"] == 2048
    assert call["body"]["messages"] == [{"role": "user", "content": "Say hi"}]
    assert "system" not in call["body"]
    assert call["timeout"] == 6
    assert result.text == "Hi" and result.provider == "anthropic" and result.model == "claude-test"


def test_anthropic_system_prompt_is_sent_as_system():  # E-A2
    transport = RecordingTransport({"content": [{"type": "text", "text": "ok"}]})
    AnthropicLLM(api_key="k", model="m", transport=transport).complete("x", system="Be brief")
    assert transport.calls[0]["body"]["system"] == "Be brief"


def test_anthropic_response_joins_only_text_blocks():  # E-A3
    response = {"content": [
        {"type": "text", "text": "Hello "},
        {"type": "tool_use", "id": "t1", "name": "x", "input": {}},
        {"type": "text", "text": "there"},
    ]}
    llm = AnthropicLLM(api_key="k", model="m", transport=RecordingTransport(response))
    assert llm.complete("x").text == "Hello there"


def test_anthropic_missing_key_fails_before_call():  # E-A4
    transport = RecordingTransport({})
    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        build_llm(Settings.from_env({"SANDBOX_LLM_PROVIDER": "anthropic"}), transport=transport)
    assert transport.calls == []


def test_build_llm_selects_anthropic_with_default_model():  # E-A5
    settings = Settings.from_env({"SANDBOX_LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "k"})
    llm = build_llm(settings, transport=RecordingTransport({}))
    assert isinstance(llm, AnthropicLLM)
    assert llm.model == "claude-sonnet-5-5"
