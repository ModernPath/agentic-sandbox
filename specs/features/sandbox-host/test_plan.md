# Test plan: sandbox host

Tests use an in-memory SQLite engine for fast cases and a disposable PostgreSQL 17 database (`TEST_DATABASE_URL`, skipped when unset) for migration locking and the agent API. No test calls a real provider; agents receive fake services through `create_app(services=...)`.

| ID | Behavior | Case | Expected |
|---|---|---|---|
| S1 | H1 | `HostSettings.from_env({})` | database URL is None; loads without error |
| S2 | H1 | `/api/health` with no engine | `database: "not_configured"`, HTTP 200 |
| S3 | H1 | `/api/health` with a working engine | `database: "ok"` |
| S4 | H1 | `/api/health` when the query fails | `database: "error"`, no driver message in body |
| S5 | H2 | Registry with uppercase or spaced name | `RegistryError` |
| S6 | H2 | Registry with duplicate names | `RegistryError` |
| S7 | H4 | Apply migrations to an empty database | files recorded with checksum; table created |
| S8 | H4 | Apply the same migrations again | nothing re-executed (count unchanged) |
| S9 | H4 | Edit an applied file | `MigrationError` on next apply, no change to the database |
| S10 | H4 | Migration with a SQL error | rolled back; not recorded; error raised |
| S11 | H4 | Two agents with same file names | tracked separately by agent |
| S12 | H4 | PostgreSQL concurrent apply from two engines | both finish; each file applied once (advisory lock) |
| S13 | H3 | `/api/agents/<name>/...` route | reaches the agent router |
| S14 | H3 | UI directory | `/agents/<name>/` serves `index.html` |
| S15 | H5 | `GET /api/agents` | lists title, description, api base, UI path for each agent |
| S16 | H5 | `GET /` | HTML index with agent links |
| S17 | H6 | `POST /briefs` with fake services | 201-style record with id, summary, sources |
| S18 | H6 | `POST /briefs` with empty topic or over 300 characters | 422 |
| S19 | H6 | `GET /briefs` ordering | newest first |
| S20 | H6 | `GET /briefs/{unknown}` | 404 |
| S21 | H7 | Brief with no readable sources | stored with `reason`, summary null; still listed |
| S22 | H7 | Stored briefs after a new app instance on the same database | visible |
| S23 | H8 | `ProviderError` inside a route | 502 JSON with safe message; no key in body |
| S24 | H8 | `ConfigurationError` (missing key) | 503 JSON with safe message |
| S25 | H1 | Storage routes without an engine | 503 JSON, not a crash |
| S26 | H5 | Bind warning | logged when host is not loopback; not logged for `127.0.0.1` |
| S27 | — | UI JavaScript | `node --check` passes; a static test asserts no `innerHTML` assignment of model text |
| S28 | — | Browser check (manual, recorded) | create, list, and open a brief in the UI against the running host |

## Exit criteria

- S1–S27 pass under `pytest` from the repository root; the PostgreSQL cases pass when `TEST_DATABASE_URL` is set.
- No test reaches the network.
- S28 is recorded in `acceptance_results.md` before the feature is called done.

## TDD order

Config and database (S1–S4), registry (S5–S6), migrations (S7–S12), app and routing (S13–S16, S26), example agent (S17–S25), UI (S27), then browser check (S28).
