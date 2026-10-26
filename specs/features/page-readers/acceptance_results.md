# Acceptance results: page readers

**Date:** 2026-10-24 · **Scope:** R-1 to R-12 in [test_plan.md](test_plan.md)

## Automated

- Reader tests (R-1 to R-12, plus R-9b for a retrieval error on another URL): pass.
- Full suite: 193 passed, 68 skipped (PostgreSQL-gated).

## Live (same public page, `https://exa.ai/docs/reference/search`, 1,500-character cap)

| Reader | Result |
|---|---|
| `local` | Returned 79 characters of script text. The page is built in JavaScript, so plain HTTP reading cannot see its content. Expected limit. |
| `exa` (`/contents`) | Pass: title "Search - Exa", 1,500 characters of page text. |
| `gemini` (`url_context`) | Pass: title "exa.ai", 1,500 characters of page text. Needed a 120-second timeout. |

### Findings

- **Gemini retrieval reports per URL.** The first live attempt failed because the response also carried an `error` status for a different URL the model touched. The reader now checks only the requested URL's status.
- **Gemini timeouts.** Retrieval takes longer than the 30-second default. The reader uses the configured `SANDBOX_HTTP_TIMEOUT_SECONDS`, so set it to 120 when using `gemini` as the reader.
- **Gemini text is model output.** The text came back as model output, not the raw HTML. The reader asks for the page text without commentary, but it can still be paraphrased. Use the Exa reader when exact wording matters.
