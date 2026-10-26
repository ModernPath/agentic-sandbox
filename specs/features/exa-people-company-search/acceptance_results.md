# Acceptance results: Exa people and company search

**Date:** 2026-10-24 · **Scope:** X-1 to X-13 in [test_plan.md](test_plan.md)

## Automated

- Exa client and people/company CLI tests (X-1 to X-13): pass.
- Full suite after the citation fix: 169 passed, 68 skipped (the skips are the PostgreSQL-gated tests).

## Live run (Agent API, effort `auto`, cap $5)

Query: engineering leaders at AI infrastructure companies in Europe that raised a Series A or B in the last six months.

| Check | Result |
|---|---|
| Run completed (`status: completed`, `stopReason: schema_satisfied`) | Pass. Run ID `agent_run_bbac531d7f7047c09fa02239a695ee72`. |
| Items returned | 25 people, within `maxItems: 25`. |
| Cost | $0.81 total (agent compute $0.59, search $0.22, no email or phone lookups), under the $5 cap. |
| Sources per item | Every item has 2–3 cited URLs from grounding entries `structured.people[i]`; 0 unsourced. Before the citation fix, 2 items showed as unsourced. |
| Grounding confidence | All 25 entries `high`. |

### Findings

- **Grounding shape.** Grounding is a list of `{field, citations: [{url}], confidence}`, keyed by a JSON path such as `structured.people[0]`. The first CLI version read a non-existent flat `url` key and printed blank lines. It now maps citations to each item.
- **Cost breakdown.** `costDollars` is an object (`total`, `agentCompute`, `search`, `emails`, `phoneNumbers`), not a number. The client now reads `total`.
- **A first live run crashed while printing** because of the cost bug above. Its output and actual cost were not captured. It was billed under the same $5 cap.
- **Citations are the agent's sources, not verified facts.** Job titles and companies still need a human check before outreach.

## Not yet done

- A company search live run (the company schema is tested offline only).
- Checking a sample of the returned profile URLs by hand.
- Any storage or UI for results (out of scope in the task spec).
