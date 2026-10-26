# Agentic Sandbox

A sandbox you instantiate per client to build software and AI agents for that client's use cases. One host serves every agent: one PostgreSQL database, one sign-in, one home page. Agents follow one standard (service, tools, CLI, API, migrations) and get models, search, page reading, embeddings, and files from shared building blocks configured by `SANDBOX_*` environment variables.

**Working here as an AI agent?** Read [`AGENTS.md`](AGENTS.md) first, then the file for the area you touch: [`agents/AGENTS.md`](agents/AGENTS.md) for agents, [`docs/agent-development.md`](docs/agent-development.md) for the full how-to, and [`docs/building-blocks.md`](docs/building-blocks.md) for the shared blocks.

## Layout

| Path | What it is |
|---|---|
| `src/sandbox_host/` | Host: app, agent registry, sign-in, migrations, records helper, panels, scaffold, test kit |
| `src/sandbox_blocks/` | Building blocks: LLM, tools, search, page reader, embeddings, files, usage |
| `agents/` | Agents that run on the host (one folder each) |
| `agents/signal-intelligence/` | SignalScout's intelligence agent, kept as its own project |
| `templates/host_agent/` | Template the scaffold copies for a new agent |
| `sandbox_app.py` | Composition root: the list of registered agents |
| `specs/` | Product PRD, architecture, design, and one folder per feature |
| `docs/` | Developer and operator guides |
| `instances/` | Per-client environment templates (real `*.env` files are git-ignored) |
| `tests/` | Host and building-block tests (offline) |

## Run the host

Requirements: Python 3.12 or newer, and a PostgreSQL database (`pgvector` is optional).

1. Copy `.env.example` to `.env` and set `DATABASE_URL` and the provider keys you are allowed to use. Never commit `.env`.
2. Install and run from the repository root:

   ```sh
   pip install -e .
   python -m sandbox_host.migrate up --app sandbox_app
   python -m sandbox_host.users create <your-name>
   PYTHONPATH=src:agents uvicorn sandbox_app:create_sandbox_app --factory --host 127.0.0.1 --port 8100
   ```

3. Open `http://127.0.0.1:8100/` and sign in. Every page and API requires sign-in; only `/static/` and the health and sign-in routes are public.

Docker: `compose.sandbox.yaml` runs the host image with PostgreSQL. Set `SANDBOX_DB_PASSWORD` in `.env`, then `docker compose -f compose.sandbox.yaml up -d --build`. See `docs/agent-development.md` for operations.

## Tests

```sh
python -m pytest -q                                   # everything, offline
PYTHONPATH=src:agents python -m pytest -q agents/<agent>/tests
```

PostgreSQL integration tests run only when `TEST_DATABASE_URL` is set. Tests never reach the network.

## Specs and status

Product-wide documents are `specs/phase-1-prd.md`, `specs/architecture-tech-stack.md`, and `specs/design/`. Each feature has `specs/features/<slug>/` with a task spec, technical spec, and test plan. The index is `specs/features/README.md`.

## Inherited SignalScout application

`src/signalscout/` and the root `compose.yaml`, `Dockerfile`, `alembic.ini`, and `migrations/` are the monitoring and signal-feed app this baseline was copied from. It is not registered on the sandbox host and keeps its own run instructions in `compose.yaml`.

`agents/signal-intelligence/` is SignalScout's intelligence agent. It reads and writes the application's tables (signals, source items, opportunities, company briefs, knowledge), so the migrations in this repository are needed to run it. Whether the application stays in this repository is an open decision.
