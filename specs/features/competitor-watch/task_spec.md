# Task spec: competitor watch (sales intelligence agent)

**Status:** Superseded in part by the [sales radar](../sales-radar/task_spec.md) (C2–C6 now store signals) · **Builds on:** [sales home](../sales-home/task_spec.md), [building blocks](../agent-building-blocks/task_spec.md)

## Goal

Sales keeps a short list of competitors. The agent searches for each competitor's recent public news, summarises what is new, and shows the findings on the sales home for review. Nothing is published or sent anywhere.

## Behavior

- **C1 Competitors.** A signed-in user can add a competitor (name 2–120 characters, optional public website, optional note up to 500). Names are unique case-insensitively. Competitors can be removed.
- **C2 Check.** `POST /api/agents/competitor-watch/check` checks every competitor (or one, given `competitor_id`): search for `"<name>" news` through the configured search block (up to 5 results per competitor), then ask the configured model to summarise the new results in at most 120 words, with citations `[n]` to the results. A competitor with no results stores a "no news found" finding.
- **C3 Findings.** Each check stores one finding per competitor with: summary text, source list (title, url, snippet), created time, and `reviewed` (default false). Findings are never published.
- **C4 Review.** `PATCH /api/agents/competitor-watch/findings/{id}` with `{reviewed: true}` marks a finding reviewed. Unreviewed findings are the default list.
- **C5 Safety.** Search results and model output are treated as untrusted text. Only `http(s)` source links are kept. Summaries are capped at 1200 characters.
- **C6 Panel.** Panel: metric "Unreviewed findings", items = latest 5 unreviewed findings (title = competitor name, meta = created day, href = the agent's page).
- **C7 Failures.** A search or model failure for one competitor is stored as an error finding for that competitor and the check continues with the others. Provider messages are not shown; a fixed message is stored.
- **C8 Storage.** Tables `competitor_watch_competitors` and `competitor_watch_findings`, owned by this agent.

## Acceptance criteria

- C1–C8 covered by tests (`test_plan.md`) with fake search and model.
- Live: one check with the configured search and model, result recorded in `acceptance_results.md`.
