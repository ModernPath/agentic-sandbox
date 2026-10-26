# Acceptance results: sandbox host

**Date:** 2026-10-24 · **Scope:** S1–S28 in [test_plan.md](test_plan.md)

## Automated

- Full suite against a disposable `pgvector/pgvector:pg17` container with `TEST_DATABASE_URL` and `DATABASE_URL` set: **184 passed, 0 skipped**. This includes the SignalScout PostgreSQL tests.
- Full suite without any PostgreSQL URL: 116 passed, 68 skipped (skips are the PostgreSQL-gated tests only).
- PostgreSQL concurrency test (S12): 40 consecutive runs passed after moving the advisory lock ahead of the tracker-table creation. One earlier run failed during development; I did not capture its message, and the race it most likely came from is the one this change removes.

## Browser (S28, against a running host)

Host run: `PYTHONPATH=src:agents DATABASE_URL=… uvicorn sandbox_app:create_sandbox_app --factory --port 8100`, with one brief seeded directly through the store. No provider keys were configured.

| Check | Result |
|---|---|
| Index `/` lists "Research brief" with an Open link | Pass |
| Agent UI loads at `/agents/research-brief/` with the recent-briefs history | Pass |
| Clicking a stored brief shows topic, summary, numbered sources, and a link | Pass |
| Submitting a new topic without search configured shows the safe 503 message in red | Pass |
| Full brief with live search and model calls | **Not verified.** Needs `SANDBOX_SEARCH_PROVIDER` and provider keys. |

## Not verified

- Live provider calls and the real search flow (see above; also still open from the building-blocks slice, which needs a live smoke check).
- Behaviour with multiple host processes against one database beyond the migration-lock test.
- Any authentication. None is implemented; the host is for loopback use.
