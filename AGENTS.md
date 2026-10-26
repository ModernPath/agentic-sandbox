# AGENTS.md — Agentic Sandbox

Instructions for AI agents and developers working in this repository. Read this file first, then the file for the area you touch (`agents/AGENTS.md` for agents, `docs/agent-development.md` for the full how-to).

## What this repository is

A sandbox that is instantiated per client to build software and agents for that client. One host serves every agent: one database, one sign-in, one home page. Agents are built from a shared standard, and model, search, reader, embedding, and file capabilities come from shared building blocks, configured by environment variables.

## Map

| Path | What it is |
|---|---|
| `src/sandbox_host/` | Host: app, registry, sign-in, migrations, records helper, panels, scaffold, test kit |
| `src/sandbox_blocks/` | Building blocks: LLM, tools, search, page reader, embeddings, files, usage |
| `agents/` | Every agent that runs on the host (one folder each) |
| `agents/signal-intelligence/` | SignalScout's intelligence agent (kept as its own project) |
| `templates/host_agent/` | Template the scaffold copies for a new agent |
| `specs/` | Product and feature specifications |
| `docs/` | Operator and developer guides |
| `instances/` | Per-client environment templates (real `*.env` files are git-ignored) |
| `sandbox_app.py` | Composition root: the list of registered agents |
| `tests/` | Tests for the host and the blocks |

## Spec-driven work

- Product-wide documents stay in `specs/`: `specs/phase-1-prd.md`, `specs/architecture-tech-stack.md`, and `specs/design/`. Do not replace them with feature documents.
- Each feature has one folder, `specs/features/<feature-slug>/`, with three files: `task_spec.md` (behaviour and acceptance), `technical_spec.md` (design and decisions), and `test_plan.md` (cases and exit criteria).
- Write the three files before any behaviour. Update them when a decision changes. Record results in `acceptance_results.md`.
- For a question or a review, read the relevant specs and answer without creating placeholder documents.

## Test-first implementation

- For every change to behaviour, write a failing test first, confirm it fails for the expected reason, make the smallest change that passes, then refactor while green.
- Tests run offline: no network, no real keys. Use fakes for models, search, and readers (see `tests/blocks_fakes.py` and the test kit `sandbox_host.testing`).
- Documentation-only changes do not need test runs, but keep `test_plan.md` aligned with the acceptance criteria.
- If a test cannot run because of the environment, say so. Do not claim a completed cycle.

## Commands

- Full suite (from the repository root): `python -m pytest -q`
- One agent's tests: `PYTHONPATH=src:agents python -m pytest -q agents/<agent>/tests`
- Start the host locally: `PYTHONPATH=src:agents uvicorn sandbox_app:create_sandbox_app --factory --port 8100` with `DATABASE_URL` set
- Migrations: `python -m sandbox_host.migrate status|up|down --app sandbox_app`
- New agent: `python -m sandbox_host.scaffold <name> --description "..."`

## Rules that apply everywhere

- Every API and page is behind sign-in. Do not add public routes without a spec entry. Static files under `/static/` are the only public assets.
- Unsafe requests (POST, PATCH, PUT, DELETE) send the header `X-Sandbox-Request: 1`. The shared kit does this; raw `fetch` calls must do it too.
- Models, search, page reading, embeddings, and files go through `sandbox_blocks`, configured by `SANDBOX_*` variables. Never import a provider SDK or hard-code a model name in an agent.
- Errors shown to people or to a model are short and safe: no stack traces, keys, or raw provider text.
- Secrets live in environment files that are git-ignored. Never print, log, or commit a key. Never pass a key as a command-line argument.
- Personal data is not stored unless the feature spec says what is kept and for how long.
- Client data stays on the client's instance. Do not copy client content into shared fixtures or public docs.
- Agents own their tables (prefixed with the agent name) and their migrations. An agent does not read or write another agent's tables; it calls the other agent's CLI or API.
- Outward-facing actions (sending messages, publishing, deleting client data) need explicit human approval. Agents draft; people decide.

## Building things

- A new agent: follow `docs/agent-development.md`. Scaffold, write the spec, then implement test-first in `service.py`. Every agent exposes its actions through `service.py`, `tools.py`, `cli.py`, and `api.py`.
- A new building block (provider or capability): add it in `src/sandbox_blocks/` behind the existing protocol, with config in `config.py`, offline tests with a recording transport, and a line in `.env.example`.
- A new page: use the shared kit, `/static/sandbox.css` and `/static/sandbox.js`, and render with `textContent` or the kit's helpers only.

## Finish against the contract

Compare the result with the PRD, the architecture, and the feature's three spec files. Report what is complete, what was verified and how, and what is still unverified. Update the spec when an agreed decision changes.
