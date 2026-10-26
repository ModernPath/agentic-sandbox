# Task spec: Sales radar

**Status:** Specified · **Builds on:** [competitor watch](../competitor-watch/task_spec.md), [sales home](../sales-home/task_spec.md), [agent building blocks](../agent-building-blocks/task_spec.md)
**Supersedes:** competitor-watch C2–C6 (findings become signals). Competitor management (C1) and storage rules stay.

## Goal

The sales home becomes a radar. Sales sees watched competitors, the signals their public news reveals (categorised, rated, sourced), and a chat that can act on that data through tools. Checks skip what was already seen. Nothing is published or sent anywhere.

## Behavior

- **R1 Competitors.** As competitor-watch C1: add (name 2–120, optional http(s) website, note ≤500), unique case-insensitively, delete.
- **R2 Intelligent check.** A check (all competitors, or one by id) searches `"<name>" news`, takes up to 5 results, and skips any result URL already stored as a signal for that competitor. Only new results are read (up to 3 pages, snippet fallback) and enriched by the configured model. Enrichment returns structured signals: headline (≤120 chars), category (`pricing`, `product`, `hiring`, `funding`, `partnership`, `leadership`, `customers`, `other`), importance (`high`, `medium`, `low`), summary (≤300 chars), and the number of the result it comes from. Invalid category → `other`; invalid importance → `low`; a result number that does not exist → that signal is dropped.
- **R3 Check record.** Each competitor checked records one check run: outcome `signals` (new signals stored), `no_new_sources` (every result was already seen), `no_signals` (model found nothing relevant), or `error` (fixed message, no provider text). A failure for one competitor does not stop the others.
- **R4 Signals.** A signal has: id, competitor, headline, category, importance, summary, source title, source URL (http(s) only), status (`new` default, `reviewed`, `dismissed`), created time. The list filters by `status`, `category`, `importance`, and `competitor_id`. Default filter: status `new`.
- **R5 Review.** `PATCH /signals/{id}` with `{"status": "reviewed"|"dismissed"}` changes status. Reviewed and dismissed signals leave the default list.
- **R6 Dashboard.** `GET /dashboard` returns:
  - `kpis`: watched competitors, new signals, new high-importance signals, signals in the last 7 days, time of the last check.
  - `by_category`: counts of signals in the last 30 days, per category.
  - `daily`: signal counts per day for the last 14 days (zero-filled).
  - `competitors`: per competitor: name, new signals, new high-importance signals, last check outcome and time.
  - `latest`: the 25 newest new signals.
- **R7 Chat.** `POST /chat` with `{"message": ≤1000 chars, "history": [{"role": "user"|"assistant", "content": ≤2000}] ≤20 entries}`. The model answers with tools: `list_competitors`, `add_competitor`, `check_competitors`, `list_signals`, `review_signal`, `competitor_brief`. Response: `{"reply": text, "tool_calls": [names]}`. Chat stores nothing; the browser keeps the conversation. Without a model configured the endpoint returns 503 with a fixed message.
- **R8 Competitor brief.** `competitor_brief(competitor_id)` returns the competitor's counts by category and its 5 newest new signals. This is the chat's way to answer "what changed at X".
- **R9 Home.** `/` redirects signed-in users to the radar page (`/agents/competitor-watch/`). The radar page links to the other registered agents in an "Other agents" list.
- **R10 Safety.** Search results, pages, and model output are untrusted text. Chat tool results are data. No provider text, keys, or stack traces reach the page. Source links are http(s) only.

## Acceptance criteria

- R1–R10 covered by tests in `test_plan.md`, using fake search, reader, and model. No network.
- The radar page renders every dashboard section from real API data, with no mock arrays, and passes the phone-width check.
- Live: one check and one chat turn with the configured providers, recorded in `acceptance_results.md`.
