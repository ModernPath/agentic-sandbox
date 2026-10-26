# Task spec: Exa people and company search

**Integration:** Exa API (see the installed `build-with-exa` skill, `.agents/skills/build-with-exa/`) · **Use case:** find people and companies for the sales team, returned as structured lists with sources · **Builds on:** [agent building blocks](../agent-building-blocks/task_spec.md)

## Goal

Given a plain-language request ("engineering leaders at AI infrastructure companies that raised a Series A or B in the last 6 months"), return a bounded, structured list of people or companies, each with its public source links, so a salesperson can review it.

## Approach (from the Exa skill)

- List building and enrichment belong on the **Agent API** (`POST /agent/runs`), not on `/search` with `category: people|company`. The category filters are for raw documents only.
- Every run sets `effort` explicitly and a per-run cost ceiling through `budget.maxCostDollars`.
- The client polls until a terminal status (`completed`, `failed`, `cancelled`). Only `completed` carries output; failures are surfaced, never shown as empty results.
- The output schema is bounded with `maxItems`.

## Scope

In scope:

- `sandbox_blocks.exa_agent`: a client for `/agent/runs` with polling, an injectable transport and sleep, and a result type with status, structured output, grounding, cost, and stop reason.
- Two output schemas, people and companies, in the example package.
- `agents/people_company_search/`: a CLI, `python -m people_company_search people "<query>"` or `company "<query>"`, that prints the list with sources.
- Settings: `EXA_API_KEY` (already read), `SANDBOX_EXA_AGENT_EFFORT` (default `auto`), `SANDBOX_EXA_AGENT_MAX_COST_DOLLARS` (default `2`).

Out of scope for this slice:

- Contact details (email, phone). The schema does not request them; the skill allows them, but a person should approve that for this client first.
- Raw `/search` with `category: people|company`.
- Storing results in the sandbox database, a UI page, or a dashboard integration. These follow once the output is reviewed.
- Exa Connect data sources (`dataSources`).

## Behavior

- **X1 Create.** `run(query, output_schema, ...)` posts to `/agent/runs` with `query`, `effort`, `outputSchema`, and `budget.maxCostDollars`. `budget` is sent only for effort `auto` or `ultra`.
- **X2 Wait.** The client polls `GET /agent/runs/{id}` every few seconds until the status is terminal, with a total wait limit.
- **X3 Outcome.** `completed` returns `AgentResult(structured, text, grounding, cost, stop_reason)`. `failed` or `cancelled` raises `ProviderError` with the stop reason and no key. A timeout raises `ProviderError`.
- **X4 Bounds.** The schema has `maxItems` and the CLI rejects an empty query or one over 500 characters.
- **X5 Sources.** The CLI prints each item with its grounding URLs. Items without a source URL are labelled as unsourced.
- **X6 Safety.** Model and web text are printed as plain text. The client never logs the API key.

## Acceptance criteria

- X1–X6 have tests (`test_plan.md`) that run without network access or a key.
- A live run with the configured key returns a completed list, recorded in `acceptance_results.md`.
