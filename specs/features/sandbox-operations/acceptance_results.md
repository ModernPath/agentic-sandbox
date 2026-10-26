# Acceptance results: sandbox operations

**Date:** 2026-10-24 · **Scope:** O-1 to O-14 in [test_plan.md](test_plan.md)

## Automated

- Migration commands (O-3 to O-11) and packaging metadata (O-1): pass.
- Full suite: 304 passed, 68 PostgreSQL-gated tests skipped in the default run.

## Manual, recorded

| Check | Result |
|---|---|
| O-2: `pip install .` into a fresh virtual environment, imports from another folder | Pass. `sandbox_blocks` and `sandbox_host` import; the host migration and login and index pages are packaged; `examples/` is not installed (by design). |
| O-12: `docker build -f Dockerfile.host` | Pass. Image builds from `python:3.12-slim`. |
| O-13: `docker compose -f compose.sandbox.yaml config` | Pass. Fails without `SANDBOX_DB_PASSWORD` (intended); host port binds to `127.0.0.1` only. |
| O-14: stack up (`up -d --wait`), host and database healthy, user created in the container, sign-in 200, `/api/agents` lists four agents, `migrate status` shows everything applied | Pass. Stack removed afterwards. |

## Notes

- Rollback on SQLite runs the down script without a transaction around DDL (SQLite's executescript behaviour); PostgreSQL runs it in one transaction. Rollback is tested on SQLite here; test it on PostgreSQL before relying on it for a client.
- The migrate CLI loads its composition root from the repository (`--app sandbox_app`), so run it from the repository root or with the repository on `PYTHONPATH`.
