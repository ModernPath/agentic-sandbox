# Acceptance results: competitor watch

**Date:** 2026-10-25 · **Scope:** CW-1 to CW-18 in [test_plan.md](test_plan.md)

## Automated

- CW-1 to CW-18: pass (fake search and model; 20 tests in the file).
- Full suite: 336 passed, 68 PostgreSQL-gated tests skipped.

## Live (local host, Gemini search and model, competitor "Varex Imaging")

| Check | Result |
|---|---|
| Add a competitor from the page | Pass |
| Check all now | Pass. One finding stored with sources and a summary. |
| Summary built from page text | Pass. The model reported that the two readable pages contained only navigation menus and that no substantive news was found, instead of inventing news. |
| Finding shows on the sales home panel | Pass (panel counts unreviewed findings) |
| Mark reviewed | Covered by tests (CW-9); not repeated in the browser |

## Known issues

- **Gemini search returns redirect links.** Sources are `vertexaisearch.cloud.google.com` redirect URLs, so people cannot easily see the real site. Fix: resolve the final URL when reading the page, or use a search provider that returns content directly (Exa, OpenAI web search).
- **Search quality is the limit here.** Gemini grounding returned navigation pages for this company, so the agent has little to summarise. Trying the Exa search provider for this agent is the next experiment.
