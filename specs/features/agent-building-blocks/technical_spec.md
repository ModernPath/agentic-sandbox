# Technical spec: agent building blocks

## Package layout

```text
src/sandbox_blocks/
  __init__.py      public names: Settings, build_llm, build_search, fetch_page, errors
  config.py        Settings.from_env(environ) and defaults
  errors.py        ConfigurationError, ProviderError
  transport.py     JsonTransport callable + urllib implementation (stdlib only)
  llm.py           LLMClient protocol, LLMResponse, GeminiLLM, OpenAILLM, build_llm
  search.py        SearchClient protocol, SearchResult, SearchResponse, Gemini/OpenAI/Exa adapters, build_search
  fetch.py         URL validation, HTML-to-text extraction, fetch_page
agents/research_brief/
  brief.py         build_brief(...) using only the protocols
  __main__.py      CLI: python -m research_brief "topic" (builds clients from env)
templates/agent/   skeleton copied by developers
docs/building-blocks.md
```

Dependencies: standard library only for the blocks (`urllib`, `html.parser`, `ipaddress`, `socket`, `json`). This keeps the sandbox free of provider SDK pins for the first slice and makes adapters testable with a fake transport. Provider SDKs may be adopted later behind the same protocols.

## Configuration

`Settings.from_env(environ=os.environ)` returns a frozen dataclass:

| Field | Env var | Default |
|---|---|---|
| `llm_provider` | `SANDBOX_LLM_PROVIDER` | `gemini` |
| `llm_model` | `SANDBOX_LLM_MODEL` | provider default (`gemini-3.8-flash`, `gpt-6-astra`) |
| `search_provider` | `SANDBOX_SEARCH_PROVIDER` | `none` |
| `search_model` | `SANDBOX_SEARCH_MODEL` | same as the LLM default for that provider |
| `search_max_results` | `SANDBOX_SEARCH_MAX_RESULTS` | `5` |
| `fetch_max_chars` | `SANDBOX_FETCH_MAX_CHARS` | `8000` |
| `http_timeout_seconds` | `SANDBOX_HTTP_TIMEOUT_SECONDS` | `30` |
| `gemini_api_key` | `GEMINI_API_KEY` | none |
| `openai_api_key` | `OPENAI_API_KEY` | none |
| `exa_api_key` | `EXA_API_KEY` | none |

Validation happens in `from_env`: unknown provider names, non-positive integers, and invalid numbers raise `ConfigurationError`. Missing keys are reported when a provider is built, not when settings load, so offline runs and tests need no keys.

Model defaults are constants in one place (`config.py`). Model names are never literals inside adapters.

## Transport

`JsonTransport = Callable[[str, dict[str, str], dict | None, float], dict]` with arguments `(url, headers, body, timeout)`. The urllib implementation POSTs JSON and returns the decoded object. HTTP errors are converted to `ProviderError` with the status code and a truncated body that has the key values removed. Adapters receive a transport in their constructor; tests pass a recording fake.

## LLM adapters

- `GeminiLLM` posts to `https://generativelanguage.googleapis.com/v1beta/interactions` with header `x-goog-api-key`. Body: `{"model", "input"}`, where `input` is the system text (when given) followed by a blank line and the prompt (decision D3). The text is taken from the `model_output` steps' `text` content items, joined in order.
- `OpenAILLM` posts to `https://api.openai.com/v1/responses` with `Authorization: Bearer`. Body: `{"model", "input", "instructions"}`. Text comes from `output_text` when present, otherwise from `output[].content[].text` where type is `output_text`.

## Search adapters

- `OpenAIWebSearch` posts to the Responses endpoint with `tools: [{"type": "web_search"}]` and the search model. Answer = message `output_text`. Results = unique `url_citation` annotations (`title`, `url`). Snippets are empty.
- `GeminiGroundingSearch` posts to the Interactions endpoint with `tools: [{"type": "google_search"}]`. Answer = `model_output` text. Results = unique `url_citation` annotations on that text. Note: citation titles may be only the domain name.
- `ExaSearch` posts to `https://api.exa.ai/search` with `x-api-key`, body `{"query", "numResults", "contents": {"highlights": true}}`, following the Exa skill default (no `maxCharacters` without a stated budget). Results map `title`, `url`, and the joined `highlights` (as snippet). No answer.

Every search adapter returns a `SearchResponse` and dedupes results by URL, keeping the first occurrence.

## Page reader

1. `validate_url(url, resolver)`: scheme must be `http` or `https`; host must be present; each resolved address must be a global IP (`ipaddress.ip_address(...).is_global`). The resolver is injectable for tests. Literal IP hosts go through the same check.
2. Fetch with `urllib` using the timeout and a `User-Agent`; read at most a fixed byte budget (`fetch_max_chars * 4`) before decoding.
3. `extract_text(html)` uses `html.parser.HTMLParser`: skips `script`, `style`, `noscript`, `template`; captures `<title>`; joins text blocks with newlines and collapses whitespace; truncates to `fetch_max_chars`.

Known limitation (documented, not fixed in this slice): DNS rebinding between validation and connection is not prevented. Agents that read untrusted URLs in production should add egress controls at the network layer.

## Example agent

`build_brief(topic, *, search, read_page, llm, max_sources=3)`:

1. `search.search(topic, max_results=max_sources * 2)`.
2. For each result until `max_sources` pages are read: `read_page(url)`. Failures are recorded in `skipped` and do not stop the run. If a page cannot be read but the search result has a snippet, the snippet is used as the source text.
3. If no source text exists, return a `Brief` with no summary and the reason, without calling the LLM.
4. Otherwise build a prompt with numbered sources and instructions to cite as `[n]` and not to use facts outside the sources. Call `llm.complete`.
5. Return `Brief(topic, summary, sources, skipped, provider, model)`.

The CLI builds clients with `build_llm(Settings.from_env())`, `build_search(...)`, and `fetch_page` partially applied. It prints the summary and a numbered source list.

## Decisions

- **D1 Stdlib HTTP.** Chosen to avoid new pins in the first slice; a provider SDK can replace an adapter later behind the same protocol.
- **D2 Search defaults off.** `SANDBOX_SEARCH_PROVIDER=none` prevents surprise search spend and keeps offline runs deterministic.
- **D3 System prompt in input.** The Interactions system-instruction field is not in the documented examples, so the system text is prepended to `input`. A live call is still needed to confirm quality (test plan exit criteria).
- **D4 Exa text as snippet.** Exa returns page text in the search response, which the example uses only as a fallback when a page cannot be read; it reads every result page first so sources are fresh.
- **D5 Shared DB and UI are deferred.** The next feature will use the existing SQLAlchemy/Alembic stack, which already accepts any PostgreSQL URL (including Supabase), and one FastAPI host that mounts each agent's router. This slice does not change `src/signalscout`.


## Azure OpenAI (added after the first slice)

- `SANDBOX_LLM_PROVIDER=azure` and `SANDBOX_SEARCH_PROVIDER=azure` select `AzureOpenAILLM` and `AzureOpenAIWebSearch`.
- Requests go to `{AZURE_OPENAI_ENDPOINT}/openai/v1/responses` with header `api-key`. The deployment name (`AZURE_OPENAI_DEPLOYMENT`) is sent as `model`. The request and response shapes are the OpenAI Responses shapes, so parsing is shared.
- `SANDBOX_LLM_MODEL` / `SANDBOX_SEARCH_MODEL` may override the deployment name. Missing `AZURE_OPENAI_*` settings raise `ConfigurationError` before any call.
