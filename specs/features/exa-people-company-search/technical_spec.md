# Technical spec: Exa people and company search

## Layout

```text
src/sandbox_blocks/exa_agent.py       AgentRun client: create, poll, result type
agents/people_company_search/
  schemas.py      people and company output schemas (bounded, no contact fields)
  search.py       build_people_search(...), build_company_search(...) -> AgentResult
  __main__.py     CLI
```

## Exa Agent client

- `POST https://api.exa.ai/agent/runs`, header `x-api-key`. Body: `{query, effort, outputSchema, budget: {maxCostDollars}}`. `budget` is omitted for fixed efforts, which reject it.
- `GET https://api.exa.ai/agent/runs/{id}` with header `x-api-key`. Poll every `poll_seconds` (default 4) until `status` is `completed`, `failed`, or `cancelled`. Total wait limit `max_wait_seconds` (default 600). Sleep and clock are injectable for tests.
- Result fields read: `output.structured`, `output.text`, `output.grounding`, `costDollars`, `stopReason`, `status`.
- `costDollars` is a breakdown object (`total`, `agentCompute`, `search`, `emails`, `phoneNumbers`). `AgentResult.cost` is its `total` (or the sum of its numeric parts when `total` is absent); the raw breakdown is kept in `cost_breakdown`.
- Grounding entries are `{field, citations: [{url}], confidence}`. Each item's citations are the entries whose `field` is `structured.<key>[i]`.
- Terminal non-completed statuses raise `ProviderError` naming the status and stop reason.
- The transport is the same `JsonTransport` used elsewhere; a GET is issued with `body=None` (the urllib transport sends GET for `None`). The shared transport raises on HTTP errors, which the client does not catch.

## Schemas

People: `{people: [{name, job_title, company, profile_url}], maxItems: 25}`, required `name, job_title, company`. Profile URL is `format: uri` and optional.

Companies: `{companies: [{name, website, industry, headquarters, description}], maxItems: 25}`, required `name, website`.

## Settings

`SANDBOX_EXA_AGENT_EFFORT` (must be one of `minimal, low, medium, high, xhigh, auto, ultra`; default `auto`), `SANDBOX_EXA_AGENT_MAX_COST_DOLLARS` (number in 1–100; default 2, sent only for `auto`/`ultra`). Both added to `Settings` in `sandbox_blocks.config`, with validation.

## Decisions

- **F1 Agent API over category search.** Matches the skill: list building and enrichment are Agent workflows.
- **F2 No contact fields by default.** Smaller personal-data footprint; contact fields need a deliberate schema change.
- **F3 Explicit cost ceiling.** Every `auto` run carries a budget so a bad query cannot spend unbounded.
