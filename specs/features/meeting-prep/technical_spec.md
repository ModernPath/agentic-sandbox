# Technical spec: meeting prep

## Layout

Scaffolded with `python -m sandbox_host.scaffold meeting-prep`. Module `agents/meeting_prep/`, host name `meeting-prep`.

| File | Role |
|---|---|
| `service.py` | Use cases and rules: `prepare_brief`, `list_briefs`, `get_brief`, `delete_brief`, `purge_expired`, `summary_panel`, `parse_attendees` |
| `prep.py` | The pure pipeline: research, signal filter, prompt, draft. Takes its clients as parameters |
| `peers.py` | Calls other agents' command-line tools in a subprocess (JSON on stdout, timeout) |
| `wiring.py` | Builds the clients from the environment and the host's injected services. Unconfigured blocks are `None` |
| `store.py` | The `meeting_prep_briefs` table, through `sandbox_host.records` |
| `tools.py`, `cli.py`, `api.py`, `models.py` | Thin surfaces over `service.py` |
| `ui/index.html` | The page, using the shared kit |

## Dependencies

`prepare_brief(store, *, search, read_page, llm, signals, notes, request, now=None)`:

- `search`, `read_page`, `llm`: building blocks, or `None` when not configured.
- `signals`: `() -> list[dict]`, returns the radar's signals. Production: `peers.radar_signals(environ)`.
- `notes`: `(file_id) -> dict` with `filename` and `text`. Production: `peers.read_notes(environ)`.

Tests inject fakes for all five. The API takes them from `app.state.services["meeting_prep"]` when present (same pattern as `research_brief`); a key present with `None` means "not configured".

## Peer calls (D1)

The root rules forbid reading another agent's tables, so meeting prep runs the peer's CLI, the same contract the chat uses:

- `python -m competitor_watch.cli signals --status new` and `--status reviewed`
- `python -m file_reader.cli read --id <id>`

`peers.run_peer(module, args, environ)` runs `sys.executable -m module ...` with `shell=False`, the environment filtered by `sandbox_host.cli_bridge.cli_env`, a 30-second timeout, and an output cap of 200,000 characters. It returns `result` from `{"ok": true}` or raises `PeerError` with a fixed message. `DATABASE_URL` is the host engine's URL and `PYTHONPATH` defaults to `cli_bridge.default_pythonpath()`.

Alternative considered: importing `competitor_watch.service` directly. Rejected because it couples the code and lets one agent reach another's store.

## Signal match (D2)

Only signals with an `http(s)` source link are kept. A signal matches when the company name, lower-cased and with surrounding spaces trimmed, appears in `competitor_name`, `headline`, or `summary`, lower-cased. New and reviewed signals are merged, de-duplicated by id, sorted by `created_at` descending, and limited to 5.

## Model prompt (D3)

The system text sets the rules (sources only, cite `[n]`, say when evidence is thin, ignore instructions inside the material, the five section headings). The user text lists the meeting details, numbered web sources (title, URL, up to 4,000 characters each), numbered radar signals, and the notes between markers. The model output is trimmed and capped at 6,000 characters.

## Data model

`meeting_prep_briefs` (migration `0001_briefs.sql`, rollback `0001_briefs.down.sql`):

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| company | TEXT | |
| website | TEXT | nullable |
| meeting_date | TEXT | nullable, `YYYY-MM-DD` |
| purpose | TEXT | default `''` |
| attendees_json | TEXT | `[{"name", "role"}]` |
| notes_file_json | TEXT | `{"id", "filename"}` or `null` |
| summary | TEXT | nullable |
| reason | TEXT | nullable; why there is no summary |
| sources_json | TEXT | `[{"number", "kind": "web"|"signal", "title", "url"}]` |
| signals_json | TEXT | `[{"number", "competitor_name", "headline", "category", "importance", "summary", "source_url"}]` |
| gaps_json | TEXT | list of fixed messages |
| provider, model | TEXT | nullable |
| created_at | TEXT | ISO-8601 UTC |
| expires_at | TEXT | created + 30 days; indexed |

## API

All under `/api/agents/meeting-prep`, behind sign-in.

| Method | Path | Result |
|---|---|---|
| POST | `/briefs` | 201, the brief. 422 on bad input |
| GET | `/briefs` | `{"briefs": [...]}` |
| GET | `/briefs/{id}` | the brief, or 404 |
| DELETE | `/briefs/{id}` | `{"deleted": true}`, or 404 |
| GET | `/panel` | the panel |

## CLI

`python -m meeting_prep.cli prepare --company "Acme" [--website URL] [--date YYYY-MM-DD] [--purpose TEXT] [--attendees "Ana Silva (CTO); Ben Ode (Buyer)"] [--notes-file-id ID]`, `list`, `get --id ID`, `delete --id ID`, `purge`. The chat allowlist is `prepare`, `list`, `get`.

## Gap messages (D4)

| Case | Message |
|---|---|
| no search block | Web search is not configured. |
| search fails | Web search failed. |
| search finds nothing readable | No public sources were found for this company. |
| radar call fails | The sales radar could not be read. |
| notes call fails | The notes file could not be read. |
| no model | (reason) No model is configured, so no written brief. |
| model fails | (reason) The model failed. Try again later. |

## Related fix (D5)

`file_reader/cli.py` had no `__main__` entry point, so `python -m file_reader.cli` printed nothing and the notes step (and the chat's command tool for File reader) got no JSON. Added the entry point with a subprocess test in `tests/test_example_file_reader.py`. `emeia_dashboard/cli.py` and `people_company_search/cli.py` have the same gap; not changed here.
