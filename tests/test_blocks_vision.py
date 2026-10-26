import base64

import pytest

from blocks_fakes import RecordingTransport
from sandbox_blocks.config import Settings
from sandbox_blocks.llm import AnthropicLLM, AzureOpenAILLM, GeminiLLM, OpenAILLM

IMAGE = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"
B64 = base64.b64encode(IMAGE).decode()


def test_openai_vision_sends_input_image_as_data_url():  # V-1
    transport = RecordingTransport({"output_text": "A chart"})
    llm = OpenAILLM(api_key="k", model="gpt-6-luna", transport=transport)
    result = llm.complete_with_image("Describe", IMAGE, "image/png", system="Be brief")
    body = transport.calls[0]["body"]
    assert body["model"] == "gpt-6-luna" and body["instructions"] == "Be brief"
    assert body["input"] == [{"role": "user", "content": [
        {"type": "input_text", "text": "Describe"},
        {"type": "input_image", "image_url": f"data:image/png;base64,{B64}"},
    ]}]
    assert result.text == "A chart"


def test_azure_vision_uses_azure_endpoint_and_api_key_header():  # V-2
    transport = RecordingTransport({"output_text": "ok"})
    llm = AzureOpenAILLM(endpoint="https://r.services.ai.azure.com", api_key="az", deployment="gpt-6-luna",
                         transport=transport)
    llm.complete_with_image("Describe", IMAGE, "image/png")
    call = transport.calls[0]
    assert call["url"] == "https://r.services.ai.azure.com/openai/v1/responses"
    assert call["headers"] == {"api-key": "az"}
    assert call["body"]["input"][0]["content"][1]["type"] == "input_image"


def test_gemini_vision_sends_inline_image_part():  # V-3
    transport = RecordingTransport({"steps": [{"type": "model_output", "content": [{"type": "text", "text": "A chart"}]}]})
    llm = GeminiLLM(api_key="g", model="gemini-3.8-flash", transport=transport)
    result = llm.complete_with_image("Describe", IMAGE, "image/png")
    assert transport.calls[0]["body"]["input"] == [
        {"type": "text", "text": "Describe"},
        {"type": "image", "data": B64, "mime_type": "image/png"},
    ]
    assert result.text == "A chart"


def test_anthropic_vision_sends_base64_image_block():  # V-4 (offline only; no live key)
    transport = RecordingTransport({"content": [{"type": "text", "text": "A chart"}]})
    llm = AnthropicLLM(api_key="a", model="claude-sonnet-5-5", transport=transport)
    llm.complete_with_image("Describe", IMAGE, "image/png")
    content = transport.calls[0]["body"]["messages"][0]["content"]
    assert content[0] == {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": B64}}
    assert content[1] == {"type": "text", "text": "Describe"}


@pytest.mark.parametrize("mime", ["text/plain", "application/pdf"])
def test_vision_rejects_non_image_mime(mime):  # V-5
    llm = OpenAILLM(api_key="k", model="m", transport=RecordingTransport({"output_text": "x"}))
    with pytest.raises(ValueError, match="image"):
        llm.complete_with_image("Describe", IMAGE, mime)
