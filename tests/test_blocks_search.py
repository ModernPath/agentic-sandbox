import pytest

from sandbox_blocks.config import Settings
from sandbox_blocks.errors import ConfigurationError
from sandbox_blocks.search import ExaSearch, GeminiGroundingSearch, OpenAIWebSearch, build_search
from blocks_fakes import RecordingTransport


def test_openai_search_uses_web_search_tool_and_url_citations():  # T11
    response = {
        "output": [
            {"type": "web_search_call", "id": "ws_1", "status": "completed"},
            {
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": "Answer [1]",
                    "annotations": [
                        {"type": "url_citation", "url": "https://a.example/x", "title": "A", "start_index": 0, "end_index": 3},
                        {"type": "url_citation", "url": "https://b.example/y", "title": "B", "start_index": 0, "end_index": 3},
                    ],
                }],
            },
        ]
    }
    transport = RecordingTransport(response)
    search = OpenAIWebSearch(api_key="o-key", model="gpt-test", transport=transport, timeout=9)

    result = search.search("topic", max_results=5)

    call = transport.calls[0]
    assert call["url"] == "https://api.openai.com/v1/responses"
    assert call["body"]["tools"] == [{"type": "web_search"}]
    assert call["body"]["input"] == "topic"
    assert result.answer == "Answer [1]"
    assert [r.url for r in result.results] == ["https://a.example/x", "https://b.example/y"]
    assert result.results[0].title == "A"


def test_gemini_search_uses_google_search_tool_and_parses_citations():  # T12
    response = {
        "steps": [
            {"type": "google_search_call", "arguments": {"queries": ["q"]}},
            {"type": "model_output", "content": [{
                "type": "text",
                "text": "Spain won.",
                "annotations": [{"type": "url_citation", "url": "https://news.example/a", "title": "news.example"}],
            }]},
        ]
    }
    transport = RecordingTransport(response)
    search = GeminiGroundingSearch(api_key="g-key", model="gemini-test", transport=transport, timeout=9)

    result = search.search("euro 2024", max_results=5)

    call = transport.calls[0]
    assert call["url"] == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert call["headers"]["x-goog-api-key"] == "g-key"
    assert call["body"]["tools"] == [{"type": "google_search"}]
    assert result.answer == "Spain won."
    assert result.results[0].url == "https://news.example/a"


def test_exa_search_maps_results_and_requests_text():  # T13
    response = {"results": [
        {"title": "Page", "url": "https://p.example/1", "highlights": ["Full body text"]},
        {"title": "Other", "url": "https://p.example/2", "highlights": ["More"]},
    ]}
    transport = RecordingTransport(response)
    search = ExaSearch(api_key="e-key", transport=transport, timeout=9)

    result = search.search("topic", max_results=2)

    call = transport.calls[0]
    assert call["url"] == "https://api.exa.ai/search"
    assert call["headers"]["x-api-key"] == "e-key"
    assert call["body"]["numResults"] == 2
    assert call["body"]["query"] == "topic"
    assert call["body"]["contents"] == {"highlights": True}
    assert "maxCharacters" not in str(call["body"])
    assert result.answer is None
    assert result.results[0].snippet == "Full body text"


def test_duplicate_urls_are_returned_once_with_first_title():  # T14
    response = {"results": [
        {"title": "First", "url": "https://dup.example/", "text": "one"},
        {"title": "Second", "url": "https://dup.example/", "text": "two"},
    ]}
    result = ExaSearch(api_key="e", transport=RecordingTransport(response)).search("q", max_results=5)
    assert [(r.title, r.url) for r in result.results] == [("First", "https://dup.example/")]


def test_results_are_capped_at_max_results():
    response = {"results": [{"title": str(i), "url": f"https://x.example/{i}", "text": ""} for i in range(10)]}
    result = ExaSearch(api_key="e", transport=RecordingTransport(response)).search("q", max_results=3)
    assert len(result.results) == 3


def test_search_none_is_a_configuration_error():  # T10
    with pytest.raises(ConfigurationError, match="SANDBOX_SEARCH_PROVIDER"):
        build_search(Settings.from_env({}), transport=RecordingTransport({}))


def test_build_search_selects_exa_with_its_key():
    settings = Settings.from_env({"SANDBOX_SEARCH_PROVIDER": "exa", "EXA_API_KEY": "e"})
    assert isinstance(build_search(settings, transport=RecordingTransport({})), ExaSearch)


def test_build_search_gemini_uses_search_model_override():
    settings = Settings.from_env({"SANDBOX_SEARCH_PROVIDER": "gemini", "GEMINI_API_KEY": "g", "SANDBOX_SEARCH_MODEL": "s-model"})
    search = build_search(settings, transport=RecordingTransport({}))
    assert isinstance(search, GeminiGroundingSearch)
    assert search.model == "s-model"


def test_exa_snippet_is_built_from_highlights():
    response = {"results": [{"title": "Page", "url": "https://p.example/1",
                             "highlights": ["First key sentence.", "Second key sentence."]}]}
    result = ExaSearch(api_key="e-key", transport=RecordingTransport(response)).search("topic", max_results=1)
    assert result.results[0].snippet == "First key sentence. Second key sentence."
