# Task spec: page readers (provider-side URL reading)

**Builds on:** [agent building blocks](../agent-building-blocks/task_spec.md) · **Sources:** Exa skill `contents` reference; Gemini URL context docs.

## Goal

Let an agent read the content of known URLs through a choice of readers, selected by environment, without changing agent code:

- `local` (default): our own HTTP reader with the public-address checks already in `fetch_page`.
- `exa`: Exa `/contents`, which extracts page text on Exa's side.
- `gemini`: Gemini's `url_context` tool, which lets the model retrieve the pages in the request.

## Behavior

- **P1 Selection.** `SANDBOX_READER_PROVIDER` is `local`, `exa`, or `gemini` (default `local`). Any other value is a `ConfigurationError`. `exa` requires `EXA_API_KEY`; `gemini` requires `GEMINI_API_KEY`.
- **P2 Common result.** Every reader returns `PageContent(url, title, text)`, with text capped at `SANDBOX_FETCH_MAX_CHARS`.
- **P3 Local check first.** Every reader validates the URL with the same rules as `fetch_page` (http or https, public addresses only) before any call to a provider. A rejected URL never reaches a provider.
- **P4 Exa.** One `POST /contents` per URL, with `text` set to `{maxCharacters: SANDBOX_FETCH_MAX_CHARS}`. A non-success status for the URL is an error, not an empty page.
- **P5 Gemini.** One Interactions call per URL with `tools: [{"type": "url_context"}]`. A retrieval status other than success (including `unsafe`) is an error. The page text is what the model returns, so it may be a paraphrase; this is documented, not hidden.
- **P6 Errors.** Provider failures raise `ProviderError` with a fixed, key-free message. Stack traces and raw bodies are not shown.

## Out of scope

- Batching several URLs in one provider call (the reader reads one URL per call).
- Subpage crawling, PDFs, and images.
- Changing the research brief logic.

## Acceptance criteria

- P1–P6 pass offline (`test_plan.md`).
- Live: each reader reads one public page through its provider; results recorded in `acceptance_results.md`.
