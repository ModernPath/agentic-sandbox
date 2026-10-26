# Acceptance results: Sales radar

**Date:** 2026-10-25 · **Scope:** R1–R10 in `task_spec.md`

## Automated

- `tests/test_sales_radar.py`: 17 tests (S-1…S-16, with S-15 covering signed-in and signed-out redirects). All pass.
- Competitor watch tests rewritten for signals (CW-5…CW-15 in `tests/test_example_competitor_watch.py`) and the standard-shape tests (`tests/test_competitor_standard.py`). The old findings assertions were replaced by their signal equivalents, not deleted; CW-7's "no news finding" became the `no_new_sources` check outcome.
- Full root suite: 365 passed, 68 skipped (PostgreSQL-gated). `agents/signal-intelligence`: 37 passed, 20 skipped.

## Live (local app on 127.0.0.1:8100, real providers from `.env`)

- Competitor "Varex Imaging" checked through the running app. Search provider for this run: **Exa** (see issue 1). Result: outcome `signals`, 3 new signals (1 high, 1 medium, 1 low), each with an http(s) source link (investing.com and the company's own news page).
- Dashboard KPIs and competitor row updated from the stored data.
- Chat (`POST /chat`) used `list_competitors` and `competitor_brief` and answered from the stored signals.
- Browser (localhost, throwaway test account, removed afterwards): sign-in, radar page renders the KPI tiles, signal cards with review buttons, competitor table, 14-day chart, category bars, and the chat. A chat question was answered and listed the tools it used.

## Issues found in the live run

1. **Gemini search returns unusable sources for this use.** Results are `vertexaisearch.cloud.google.com` redirect links with empty snippets. Reading those pages mostly failed, so the model correctly answered `[]`. Recommendation: set `SANDBOX_SEARCH_PROVIDER=exa` for the radar. This is an operator decision and was not changed in `.env`.
2. **Chat replies show raw markdown** (`**bold**`, `*` bullets). Follow-up: render a safe subset of markdown with `textContent`-based rendering.
3. **Model timeouts** on some page reads and calls (Gemini). Checks still complete (failed reads fall back to snippets). Follow-up: record read failures separately from model failures.
4. The check log line (count-only, `WARNING` level, logger `competitor_watch`) was added while diagnosing issue 1. It records result, fresh-source, output-length, and stored counts, never content.

## Not verified

- A live check with Anthropic or OpenAI as the model (only Gemini was used).
- Phone-width layout (only desktop width was captured).
