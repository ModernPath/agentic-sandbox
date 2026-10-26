import pytest

from blocks_fakes import RecordingTransport
from sandbox_blocks.config import Settings
from sandbox_blocks.errors import ConfigurationError, ProviderError
from sandbox_blocks.readers import ExaContentsReader, GeminiUrlContextReader, LocalPageReader, build_reader

PUBLIC = "https://news.example/story"


def settings(**env):
    return Settings.from_env(env)


def test_default_reader_is_local():  # R-1
    assert isinstance(build_reader(settings()), LocalPageReader)


def test_unknown_reader_is_rejected():  # R-2
    with pytest.raises(ConfigurationError, match="SANDBOX_READER_PROVIDER"):
        build_reader(settings(SANDBOX_READER_PROVIDER="scrapy"))


@pytest.mark.parametrize("env, name", [({"SANDBOX_READER_PROVIDER": "exa"}, "EXA_API_KEY"),
                                       ({"SANDBOX_READER_PROVIDER": "gemini"}, "GEMINI_API_KEY")])
def test_provider_reader_without_key_fails_before_any_call(env, name):  # R-3
    with pytest.raises(ConfigurationError, match=name):
        build_reader(settings(**env))


def test_exa_request_shape():  # R-4
    transport = RecordingTransport({"results": [{"url": PUBLIC, "title": "Story", "text": "Body text"}], "statuses": []})
    reader = ExaContentsReader(api_key="ex-key", max_chars=3000, transport=transport, resolver=lambda h: ["93.184.216.34"])
    reader.read(PUBLIC)
    call = transport.calls[0]
    assert call["url"] == "https://api.exa.ai/contents"
    assert call["headers"] == {"x-api-key": "ex-key"}
    assert call["body"] == {"urls": [PUBLIC], "text": {"maxCharacters": 3000}}


def test_exa_success_returns_page_content():  # R-5
    transport = RecordingTransport({"results": [{"url": PUBLIC, "title": "Story", "text": "Body text"}],
                                    "statuses": [{"id": PUBLIC, "status": "success"}]})
    page = ExaContentsReader(api_key="k", max_chars=3000, transport=transport,
                             resolver=lambda h: ["93.184.216.34"]).read(PUBLIC)
    assert (page.url, page.title, page.text) == (PUBLIC, "Story", "Body text")


def test_exa_status_error_is_an_error_not_an_empty_page():  # R-6
    transport = RecordingTransport({"results": [], "statuses": [{"id": PUBLIC, "status": "error", "tag": "CRAWL_TIMEOUT"}]})
    with pytest.raises(ProviderError):
        ExaContentsReader(api_key="k", max_chars=3000, transport=transport,
                          resolver=lambda h: ["93.184.216.34"]).read(PUBLIC)


def test_gemini_request_enables_url_context():  # R-7
    transport = RecordingTransport({"steps": [
        {"type": "url_context_result", "result": [{"url": PUBLIC, "status": "success"}]},
        {"type": "model_output", "content": [{"type": "text", "text": "Body"}]},
    ]})
    GeminiUrlContextReader(api_key="g-key", model="m", max_chars=3000, transport=transport,
                           resolver=lambda h: ["93.184.216.34"]).read(PUBLIC)
    call = transport.calls[0]
    assert call["url"] == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert call["headers"] == {"x-goog-api-key": "g-key"}
    assert call["body"]["tools"] == [{"type": "url_context"}]
    assert PUBLIC in call["body"]["input"]


def test_gemini_success_returns_model_text():  # R-8
    transport = RecordingTransport({"steps": [
        {"type": "url_context_result", "result": [{"url": PUBLIC, "status": "success"}]},
        {"type": "model_output", "content": [{"type": "text", "text": "Page text here"}]},
    ]})
    page = GeminiUrlContextReader(api_key="g", model="m", max_chars=3000, transport=transport,
                                  resolver=lambda h: ["93.184.216.34"]).read(PUBLIC)
    assert page.text == "Page text here"
    assert page.title == "news.example"


def test_gemini_unsafe_url_is_an_error():  # R-9
    transport = RecordingTransport({"steps": [
        {"type": "url_context_result", "result": [{"url": PUBLIC, "status": "unsafe"}]},
        {"type": "model_output", "content": [{"type": "text", "text": "x"}]},
    ]})
    with pytest.raises(ProviderError):
        GeminiUrlContextReader(api_key="g", model="m", max_chars=3000, transport=transport,
                               resolver=lambda h: ["93.184.216.34"]).read(PUBLIC)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1/admin", "http://10.0.0.5/"])
def test_unsafe_urls_never_reach_a_provider(url):  # R-10
    transport = RecordingTransport({})
    for reader in (ExaContentsReader(api_key="k", max_chars=3000, transport=transport),
                   GeminiUrlContextReader(api_key="g", model="m", max_chars=3000, transport=transport)):
        with pytest.raises(ValueError):
            reader.read(url)
    assert transport.calls == []


def test_provider_error_message_hides_key_values():  # R-11
    from sandbox_blocks.transport import urllib_transport  # noqa: F401  (redaction is shared)
    transport = RecordingTransport({"results": [], "statuses": [{"id": PUBLIC, "status": "error", "tag": "x"}]})
    with pytest.raises(ProviderError) as error:
        ExaContentsReader(api_key="secret-exa-key", max_chars=3000, transport=transport,
                          resolver=lambda h: ["93.184.216.34"]).read(PUBLIC)
    assert "secret-exa-key" not in str(error.value)


def test_long_page_text_is_capped():  # R-12
    transport = RecordingTransport({"results": [{"url": PUBLIC, "title": "t", "text": "x" * 9000}],
                                    "statuses": [{"id": PUBLIC, "status": "success"}]})
    page = ExaContentsReader(api_key="k", max_chars=500, transport=transport,
                             resolver=lambda h: ["93.184.216.34"]).read(PUBLIC)
    assert len(page.text) <= 500


def test_gemini_error_for_another_url_does_not_fail_the_requested_page():  # R-9b
    other = "https://elsewhere.example/linked"
    transport = RecordingTransport({"steps": [
        {"type": "url_context_result", "result": [{"url": PUBLIC, "status": "success"},
                                                  {"url": other, "status": "error"}]},
        {"type": "model_output", "content": [{"type": "text", "text": "Page text"}]},
    ]})
    page = GeminiUrlContextReader(api_key="g", model="m", max_chars=3000, transport=transport,
                                  resolver=lambda h: ["93.184.216.34"]).read(PUBLIC)
    assert page.text == "Page text"
