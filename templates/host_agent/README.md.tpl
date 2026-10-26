# $Title

## Contract

- **Purpose:** <one sentence: what this agent does for the client>
- **Users:** signed-in sandbox users (sign-in is enforced by the host).
- **Inputs:** `POST /api/agents/$name/items` with `{title, body}`.
- **Outputs:** items as JSON; the UI at `/agents/$name/`.
- **Data:** tables `${table}_items` (this agent only). Migration `migrations/0001_init.sql`.
- **Side effects:** writes to `${table}_items` only. No model or network calls in this template.
- **Blocks used:** none yet; add `sandbox_blocks` capabilities when the domain needs them.
- **Configuration:** none beyond the host's `DATABASE_URL`.

## Build steps

1. Write the spec in `specs/features/$name/` (task, technical, test plan).
2. Add a failing test in `tests/` for the next behaviour, confirm it fails, implement, refactor.
3. Keep tables prefixed `${table}_` and migrations in `migrations/`.
4. Run `python -m pytest -q` from this folder (with `PYTHONPATH=src:agents` from the repository root).
5. Check the UI in a browser after starting the host.
