# AGENTS.md — $Title

Rules for AI agents and developers working on this agent. The repository-wide rules are in the root `AGENTS.md` and `docs/agent-development.md`; read them first.

## What this agent is

$description

## Layout (the standard)

| File | Role | Rule |
|---|---|---|
| `service.py` | Use cases and business rules | The only place rules live. No HTTP, no printing. |
| `store.py` | Persistence through `sandbox_host.records` | Table names start with `${table}_`. Values are bound, never formatted into SQL. |
| `tools.py` | Model-callable tools | One tool per service action; typed parameters; errors returned as data. |
| `cli.py` | Command line with JSON output | One subcommand per action; exit 0/1/2; the subagent entry point. |
| `api.py` | HTTP routes | Calls `service` only; maps errors to status codes. |
| `migrations/` | Schema changes | Additive `NNNN_name.sql`; a `NNNN_name.down.sql` when the rollback is safe. Never edit an applied file. |
| `ui/index.html` | Page | Uses `/static/sandbox.css` and `/static/sandbox.js`; unsafe requests through `Sandbox.api`. |
| `tests/` | Tests | Offline. `test_standard.py` checks that API, tools, and CLI agree. |

## Adding an action (the usual change)

1. Write the failing test in `tests/` for the behaviour (service first, then tool, CLI, and API).
2. Add the function in `service.py` with validation and a safe error message.
3. Expose it in `tools.py` (typed parameters, a docstring the model can read).
4. Expose it in `cli.py` (a subcommand that prints JSON).
5. Expose it in `api.py` (a route that calls the service).
6. Run `python -m pytest -q` from the repository root with `PYTHONPATH=src:agents`.

## Adding a migration

1. Create the next number: `migrations/0002_<what>.sql`. Use the `${table}_` prefix for new tables.
2. Add `migrations/0002_<what>.down.sql` if the change can be reverted safely.
3. Do not edit an applied migration. Check with `python -m sandbox_host.migrate status --app sandbox_app`.
4. Test the migration on PostgreSQL before it reaches a client database.

## Rules that the tests enforce

- Every route requires sign-in; do not add public routes.
- The UI sends `X-Sandbox-Request: 1` on every unsafe request (the shared kit does this).
- Model and search calls go through `sandbox_blocks` (`Settings.from_env()`); never import a provider SDK here.
- Errors shown to people or to the model are short and safe: no stack traces, keys, or raw provider text.
- Personal data is not stored unless the spec says why and how long it is kept.

## Verify before you finish

- `PYTHONPATH=src:agents python -m pytest -q agents/$module/tests`
- Full suite from the repository root: `python -m pytest -q`
- Start the host and check the page in a browser: sign in, use the main flow, sign out.
- Record the result in `specs/features/$name/acceptance_results.md`.
