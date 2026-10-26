# Technical spec: sandbox operations

## Packaging

`pyproject.toml` already declares `packages.find where src` and the package data for `sandbox_host` (static HTML and host migrations). Verify that `sandbox_blocks` and `sandbox_host` are both listed and that `examples/` is not packaged (agents are run from the repository, or copied). The agents' `requirements.txt` files point to the repository install (`pip install -e ../..`).

## Migration commands (`src/sandbox_host/migrate.py`)

Components are the host (`sandbox-host`, migrations in `sandbox_host/migrations`) and each agent in the composition root's `AGENTS` list. Applied state comes from `sandbox_schema_migrations`.

- `status(engine, components) -> list[dict]`: per component `{name, applied: [...], pending: [...], mismatched: [...]}`.
- `up(engine, components)`: calls `apply_agent_migrations` for each component.
- `down(engine, component)`: finds the latest applied name for the component, looks for `<stem>.down.sql` next to the up file (`0002_x.sql` -> `0002_x.down.sql`), and runs it with the tracker row removal in one transaction. Refuses when the down file is missing, when the component is unknown, or when nothing is applied.

The up runner ignores `*.down.sql` files: its glob is `*.sql` sorted, so down files must be excluded explicitly. This is a required change to `apply_agent_migrations`.

## Container

`Dockerfile.host`: `python:3.12-slim`, creates user `sandbox` (uid 10001), installs from `pyproject.toml` with `pip install .`, copies `examples/`, `templates/`, and `sandbox_app.py`, sets `PYTHONPATH` for `examples`, and runs `uvicorn sandbox_app:create_sandbox_app --factory --host 0.0.0.0 --port 8100`. The host's own startup applies migrations.

`compose.sandbox.yaml`: `db` (pgvector image, healthcheck), `host` (built from `Dockerfile.host`, `DATABASE_URL` pointing at `db`, `env_file: instances/<client>.env` optional, port `127.0.0.1:${SANDBOX_PORT:-8100}:8100`, depends on healthy `db`). `SANDBOX_HOST` inside the container is `0.0.0.0` so the port mapping works; the published port is loopback only.

## Decisions

- **P1 Down migrations are opt-in per file.** Most migrations are additive; a rollback file is written when it is safe to remove the change.
- **P2 One migration runner.** The CLI reuses `apply_agent_migrations`; no second implementation.
