# Test plan: sandbox operations

| ID | Behavior | Case | Expected |
|---|---|---|---|
| O-1 | O1 | `pyproject.toml` packages | `sandbox_blocks`, `sandbox_host`, `signalscout` listed; `examples` not packaged |
| O-2 | O1 | Fresh venv: `pip install .` then import `sandbox_blocks` from another folder | import works (manual, recorded) |
| O-3 | O2 | status on a fresh database | host and each agent: all migrations pending |
| O-4 | O2 | status after `up` | all applied; none pending |
| O-5 | O2 | edited applied file | `mismatched` lists it; status does not change the database |
| O-6 | O3 | up with an unknown component in the list | ignored; known ones applied |
| O-7 | O4 | down for a component with a down file | latest applied migration reverted; tracker row removed; table gone |
| O-8 | O4 | down without a down file | refused, nothing changed |
| O-9 | O4 | down when nothing is applied | refused |
| O-10 | O4 | down for an unknown component | refused |
| O-11 | O4 | up after down | reapplies the reverted migration |
| O-12 | O5 | `docker build -f Dockerfile.host` | image builds (manual, recorded) |
| O-13 | O6 | `docker compose -f compose.sandbox.yaml config` | valid; host publishes only loopback |
| O-14 | O5/O6 | container run against PostgreSQL, sign in, `/api/health` | 200 and signed-in access (manual, recorded) |

## Exit criteria

O-1, O-3 to O-11 pass offline. O-2, O-12 to O-14 are recorded in `acceptance_results.md`.
