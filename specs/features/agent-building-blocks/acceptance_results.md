# Acceptance results: agent building blocks

## Live smoke test: Gemini (2026-10-24)

Run from the root `.env` (`SANDBOX_LLM_PROVIDER=gemini`, `SANDBOX_SEARCH_PROVIDER=gemini`). Keys were read from the environment and never printed.

| Check | Result |
|---|---|
| `build_llm(...).complete()` with a system prompt, model `gemini-3.8-flash` | Pass: returned `OK`. Confirms the Interactions request shape and the prepended system prompt (decision D3). |
| `GeminiGroundingSearch.search()` | Pass: 3 results with titles and URLs. |
| `fetch_page("https://example.com/")` | Pass: title `Example Domain`. |
| `python -m research_brief "What is the Gemini Interactions API?"` | Pass: summary with numbered `[n]` citations and a source list. |

### Findings

- **Citation URLs are Google redirect links.** Gemini grounding returns `vertexaisearch.cloud.google.com/grounding-api-redirect/...` URLs, and their titles are often only the domain. The brief works, but the source list is not readable for people. Planned fix: resolve the redirect when reading a page and show the final URL.
- The brief's citations are correct in form; claim accuracy was not checked against the sources.

## Not yet tested live

- OpenAI LLM and web search (keys pending).
- Anthropic LLM (key pending).
- Exa search (no key).
- Azure OpenAI: no adapter exists yet; it needs different endpoints and deployment-based routing.

## Live smoke test: Exa web search (2026-10-24)

Exa key from the root `.env`; keys were passed to the process and never printed.

| Check | Result |
|---|---|
| `ExaSearch.search("Exa AI search API for agents", 3)` with `highlights` | Pass: 3 results with titles, URLs, and highlight snippets. |
| `python -m research_brief` with `SANDBOX_SEARCH_PROVIDER=exa`, `SANDBOX_LLM_PROVIDER=gemini` | Pass: summary with `[n]` citations and sources. |

### Findings

- **Adapter changed to follow the Exa skill.** It requested `contents.text` capped at 2000 characters. The skill's default is `highlights: true`, and it advises against adding `maxCharacters` without a stated budget. The adapter now uses highlights; tests updated.
- **Source quality.** One brief citation was a third-party docs mirror (`exa.mintlify.app`) supporting a marketing-style claim. Briefs need source review before use.

## Live smoke test: OpenAI, model `gpt-6-luna` (2026-10-24)

Key from the root `.env` after reset (`GET /v1/models` returned 200; `gpt-6-luna` listed). The key was passed to the process and never printed. `.env` provider settings were not changed.

| Check | Result |
|---|---|
| `OpenAILLM.complete()` with a system prompt | Pass: returned `OK`. |
| `OpenAIWebSearch.search()` (Responses API `web_search` tool) | Pass: answer text plus 2 deduplicated `url_citation` results. |
| `python -m research_brief` with `SANDBOX_LLM_PROVIDER=openai`, `SANDBOX_SEARCH_PROVIDER=openai` | Pass mechanically: brief returned with `[1]` citation. |

### Findings

- **Thin brief.** The brief said the one source did not explain the API. Search found two results, but only one page was summarised, so the brief had little to work with. Possible fix: read more pages or raise `max_sources` when the first source is short.
- An earlier key was rejected with HTTP 401 and was replaced by the user. That is why the earlier results were not recorded.

## Live smoke test: Azure OpenAI on Azure AI Foundry, deployment `gpt-6-luna` (2026-10-24)

Values from the root `.env` (`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`). Passed to the process and never printed. A GET to `/openai/v1/models` returned 200 before the adapter was written.

| Check | Result |
|---|---|
| `AzureOpenAILLM.complete()` (Responses API, `api-key` header, deployment as model) | Pass: returned `OK`. |
| `AzureOpenAIWebSearch.search()` (`web_search` tool on the Azure endpoint) | Pass: answer text plus 2 citations. |
| `python -m research_brief` with `SANDBOX_LLM_PROVIDER=azure`, `SANDBOX_SEARCH_PROVIDER=azure` | Pass mechanically: brief with `[n]` citations. |

### Findings

- **Thin briefs recur** (OpenAI and Azure runs). Both briefs said the cited sources only named the API and did not explain it. The two pages are documentation index pages, so the cause is source selection and page reading, not the model provider. Next improvement: prefer pages with more text, read more candidates, and say when evidence is thin.

## Not yet tested live

- Anthropic LLM (no key in `.env`).
