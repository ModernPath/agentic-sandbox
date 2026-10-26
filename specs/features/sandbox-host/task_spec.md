# Task spec: sandbox host (shared database and one interface)

**Status:** Draft for implementation · **Product scope:** [architecture](../../architecture-tech-stack.md#agent-sandbox-direction) · **Builds on:** [agent building blocks](../agent-building-blocks/task_spec.md)

## Goal

One sandbox instance runs one web process and one PostgreSQL database. Every agent in that sandbox plugs into the same host, so a client can run the whole sandbox with one command and one browser address. Agents keep their own tables, but they share the database connection, the migration runner, the health check, and the agent index.

## Scope

In scope:

- `src/sandbox_host/`: settings, database connection, per-agent migration runner, agent registry, FastAPI app with an agent index, and a generic health endpoint.
- Migrations for each agent as plain SQL files, applied in order, tracked in one shared table. Supabase and any PostgreSQL URL work without changes.
- One example agent wired into the host end to end: `agents/research_brief` gains an API (create and list briefs), a SQL migration, a stored history, and a minimal UI page.
- A local run command in the docs, and `.env.example` entries.

Out of scope for this slice (listed as next features):

- Authentication and per-user access. The host binds to `127.0.0.1` by default and prints a warning if bound elsewhere. Client deployments must add auth before exposing it.
- Container/Compose service for the sandbox host. The existing Compose file still runs SignalScout.
- Migrating `agents/example-agent` and `agents/secure-agent`.
- Background jobs, scheduling, and the SignalScout application database (kept as is).

## Behavior

- **H1 One database.** The host reads `DATABASE_URL` once. Every agent receives the same engine. Without `DATABASE_URL`, the host still starts; agents that need storage report themselves unavailable, and `/api/health` reports the database as `not_configured`.
- **H2 Agent registry.** An agent is an `AgentSpec(name, title, description, router, migrations_dir, ui_dir)`. Names are lowercase slugs and unique. Registration of a duplicate or invalid name fails at startup.
- **H3 Routes.** An agent's router is mounted under `/api/agents/<name>`. Its UI directory, when given, is served under `/agents/<name>/`.
- **H4 Migrations.** At startup, each agent's `migrations_dir/*.sql` files run in name order, once each. Applied files are recorded with a SHA-256 checksum. A changed checksum for an applied file stops startup with a clear error. Each file runs in its own transaction.
- **H5 Index and health.** `GET /api/agents` lists registered agents with title, description, API base, and UI path. `GET /api/health` returns `{status, database}`. `GET /` serves an index page that lists agents and links to their UIs.
- **H6 Example agent.** `POST /api/agents/research-brief/briefs` with `{"topic": "..."}` runs the brief, stores it, and returns it with an id. `GET .../briefs` lists stored briefs, newest first. `GET .../briefs/{id}` returns one, or 404.
- **H7 Shared state.** Briefs survive restarts. A failed brief run (for example, no sources) is still stored with its reason, so the history shows what happened.
- **H8 Safe errors.** Configuration and provider errors return a JSON error with a safe message. Keys and stack traces are never returned to the browser.

## Acceptance criteria

- H1–H8 each have tests in `test_plan.md`. Routes and migrations are tested against a disposable PostgreSQL database (skipped unless `TEST_DATABASE_URL` is set) and against an in-memory SQLite engine for the fast path.
- The example's UI can create and list a brief from a browser against a running host with fake or real provider keys. Browser verification is recorded in `acceptance_results.md`.
- The host starts with one documented command, and that command is in the README.
