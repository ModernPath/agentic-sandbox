# Task spec: agent standard (service, tools, CLI, migrations)

**Status:** Pilot done on competitor-watch; pending review before rollout · **Builds on:** [agent scaffolding](../agent-scaffolding/task_spec.md), [sandbox operations](../sandbox-operations/task_spec.md)

## Goal

Every host agent is reusable: its actions can be called from the web API, from a model as tools, from the command line, and by other agents as subagents, all through one service layer that owns the rules.

## Standard (required for every host agent)

- **S1 Service.** `service.py` holds every use case as a plain function that takes the store and the injected clients. API, tools, and CLI call these functions and nothing else. Business rules live only here.
- **S2 Tools.** `tools.py` exposes the service actions as model-callable tools (`sandbox_blocks.tools.Tool`) with JSON schemas. Parameters are typed (`str`, `int`, `float`, `bool`). Each tool returns a dictionary, and errors are returned as `{"error": ...}`.
- **S3 CLI.** `cli.py` gives each action a subcommand that prints one JSON object to stdout: `{"ok": true, "result": ...}` or `{"ok": false, "error": "..."}`. Exit code 0 on success, 1 on error, 2 on bad usage. The CLI uses the shared database from `DATABASE_URL`, like the API.
- **S4 Subagents.** A delegated job is a CLI call with a timeout, not an in-process import. An agent that needs another agent calls its CLI.
- **S5 Migrations.** Agents own their migrations in `migrations/`, applied by the host runner. Each migration is additive when possible and ships a `.down.sql` when a rollback is safe. Table names carry the agent's prefix.
- **S6 Equivalence.** For the same inputs, the API, the tools, and the CLI return the same data and the same error categories (tests check this).

## Acceptance criteria

- S1–S6 covered for competitor-watch (pilot) in `test_plan.md`.
- The standard is written into the scaffold template and `docs/agent-development.md` after the pilot is reviewed.
