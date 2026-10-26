# Test plan: agent building blocks

All tests run without network access and without real keys. Adapters receive a recording fake transport; fetch tests inject a resolver and a fake byte source.

## Cases

| ID | Behavior | Case | Expected |
|---|---|---|---|
| T1 | B1 | Default settings from empty env | provider `gemini`, search `none` |
| T2 | B1 | `SANDBOX_LLM_PROVIDER=openai` and model override | settings reflect both; `build_llm` returns OpenAI adapter |
| T3 | B1 | Unknown LLM provider | `ConfigurationError` naming allowed values |
| T4 | B1 | Non-integer `SANDBOX_SEARCH_MAX_RESULTS` | `ConfigurationError` |
| T5 | B2 | Gemini `complete` request | URL, `x-goog-api-key`, model and input in body; text parsed from `model_output` |
| T6 | B2 | OpenAI `complete` with `output_text` | request has `instructions`; text returned |
| T7 | B2 | OpenAI response without `output_text`, only `output[].content` | text still extracted |
| T8 | B2 | Missing key when building the adapter | `ConfigurationError`, no transport call |
| T9 | B2 | HTTP 429 from provider | `ProviderError`; message contains status and not the key value |
| T10 | B3 | `build_search` with provider `none` | `ConfigurationError` |
| T11 | B4 | OpenAI search request | `tools` is `[{"type": "web_search"}]`; results from `url_citation` annotations |
| T12 | B4 | Gemini search request | `tools` is `[{"type": "google_search"}]`; answer and citations parsed |
| T13 | B4 | Exa search request | URL, `x-api-key`, `numResults`, `contents: {highlights: true}`; results mapped from highlights |
| T14 | B4 | Duplicate URLs across citations | returned once, first title kept |
| T15 | B5 | `validate_url` rejects `file://`, `http://127.0.0.1`, `http://10.0.0.5`, `http://[::1]`, and a host resolving to 192.168.1.1 | `ValueError` |
| T16 | B5 | `validate_url` accepts a public host resolving to a global IP | returns normalized URL |
| T17 | B5 | `extract_text` removes script/style, keeps title and body, collapses whitespace | expected text |
| T18 | B5 | `extract_text` on a very long page | length at most `fetch_max_chars` |
| T19 | B5 | `fetch_page` with a fake byte source over the budget | body truncated to budget; no error |
| T20 | B8 | `build_brief` with fakes | summary returned; prompt contains numbered sources; LLM called once |
| T21 | B8 | One page read fails, one succeeds | failure in `skipped`; run completes |
| T22 | B8 | No readable text at all | no LLM call; reason returned |
| T23 | B7 | Example module imports | does not import provider SDKs or the urllib transport directly (static check on import names) |
| T24 | — | Template copy | template tests pass after renaming the package |
| T25 | — | `.env.example` coverage | every `SANDBOX_*`, `*_API_KEY` variable read by `config.py` appears in `.env.example` |

## Exit criteria

- All T-cases pass under `pytest` from the repository root.
- No test reaches the network (verified by running with network-denying fixtures; any real socket use fails the test).
- Live smoke check (manual, not in the normal run): one `complete` call per configured provider and one search per configured search provider, recorded in `specs/features/agent-building-blocks/acceptance_results.md`. Resolves D3.

## TDD order

Implement in this order, one red-green-refactor cycle per case: config (T1–T4), transport and LLM (T5–T9), search (T10–T14), fetch (T15–T19), example (T20–T23), template and docs (T24–T25).
