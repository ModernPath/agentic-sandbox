# Test plan: page readers

Offline with recording transports. No network, no keys.

| ID | Behavior | Case | Expected |
|---|---|---|---|
| R-1 | P1 | Default settings | `local` reader |
| R-2 | P1 | Unknown reader name | `ConfigurationError` |
| R-3 | P1 | `exa` without key; `gemini` without key | `ConfigurationError` before any call |
| R-4 | P4 | Exa request | `POST https://api.exa.ai/contents`, `x-api-key`, body `{urls: [url], text: {maxCharacters: N}}` |
| R-5 | P2, P4 | Exa success | `PageContent` with title and text from `results[0]` |
| R-6 | P4 | Exa status `error` for the URL | `ProviderError`; no text returned |
| R-7 | P5 | Gemini request | Interactions URL, `x-goog-api-key`, `tools: [{"type": "url_context"}]`, URL in input |
| R-8 | P5 | Gemini success | text from `model_output`; title from URL host |
| R-9 | P5 | Gemini `url_context_result` status `unsafe` | `ProviderError` |
| R-10 | P3 | `file://`, `127.0.0.1`, private IP given to exa or gemini reader | `ValueError`; transport never called |
| R-11 | P6 | Provider HTTP error body containing the key | message has no key value |
| R-12 | P2 | Long page text | capped at `SANDBOX_FETCH_MAX_CHARS` |

## Exit criteria

- R-1 to R-12 pass in the full suite.
- Live smoke run per reader recorded in `acceptance_results.md`.
