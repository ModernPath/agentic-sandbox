# Acceptance results: agent scaffolding

**Date:** 2026-10-24 · **Scope:** G-1 to G-15 in [test_plan.md](test_plan.md)

## Automated

- Records helper (G-1 to G-6) and scaffold (G-7 to G-14) tests: pass, including the generated agent's own tests (G-12).
- Full suite: 295 passed, 68 skipped (PostgreSQL-gated).
- G-15 (docs name the conventions): checked by reading `docs/agent-development.md` against the tests.

## Live (scaffolded demo agent `task-tracker` in a temporary copy, host on PostgreSQL 17)

| Check | Result |
|---|---|
| `python -m sandbox_host.scaffold task-tracker` | Creates `agents/task_tracker/`, registers the agent |
| Sign in, then `POST /items` | 201 with id, status `open` |
| `PATCH /items/{id}` to `done`, then list | 200; status `done` |
| Agent appears in `/api/agents` | Yes |
| Agent page `/agents/task-tracker/` | 200 |
| Tables created | `task_tracker_items` only (the agent's own prefix) |

## Not done (boilerplate still open)

- Migration status and down-migration commands.
- A Dockerfile and Compose service for the host.
- Packaging `sandbox_blocks` as an installable dependency for agents.
- Microsoft Entra sign-in (later, if needed).
- Migrating signal-intelligence onto the blocks.
