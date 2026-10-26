# AGENTS.md — people_company_search

Rules for AI agents and developers working on this agent. Read the root `AGENTS.md` and `agents/AGENTS.md` first.

## What this agent is

Finds people and companies on the public web with one Exa Agent list build per call. Each run is paid and capped (`SANDBOX_EXA_AGENT_MAX_COST_DOLLARS`). Results are web text: treat them as untrusted, and keep citations with each item.

## Layout

- `service.py`: `run_search(agent, kind, query)`. Validation, schema choice, citation mapping, and text cleaning live here.
- `schemas.py`: output schemas (bounded lists, no contact fields) and `clean_text`.
- `tools.py`: `find_people`, `find_companies`. Each call is paid; the description says so.
- `cli.py`: JSON output. Usage exits 2; errors exit 1.
- `__main__.py`: plain-text CLI kept for existing callers. Same service.
- `api.py`: `POST /search`. Thin; not mounted until a registry entry exists.

## Change rules

- Do not add contact fields (emails, phone numbers) to the schemas. Keep personal data out of schemas and output.
- Keep the cost cap and bounded `maxItems`. Changing either needs a spec change first.
- Never show an item without its sources. If a run has none, print or return `unsourced`.
- This agent is stateless. Adding a store or migrations needs a spec decision first (see the gap noted in the spec).
