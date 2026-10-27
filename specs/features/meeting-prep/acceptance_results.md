# Acceptance results: meeting prep

## 2026-10-27 — offline build and local host check

**Offline tests.** `PYTHONPATH=src:agents python -m pytest -q agents/meeting_prep/tests`: 43 passed. Covers MP-1 to MP-19. MP-17 runs the real `competitor_watch.cli` in a subprocess against a SQLite file. The full suite (`python -m pytest -q`) passed, with the new `file_reader` CLI test (D5).

**Local host (MP-20).** Host started with `uvicorn sandbox_app:create_sandbox_app --factory` on a SQLite file database, migrations applied with `sandbox_host.migrate up`, no search or model provider configured. Seeded data: one radar competitor "Acme Oy" with one signal, and one uploaded `.txt` notes file in File reader.

| Check | Result |
|---|---|
| `POST /briefs` through the API, signed in | 201. Radar signal found through the real `competitor_watch.cli` subprocess and numbered [1]. Notes file read through the real `file_reader.cli` subprocess (file name stored, text not stored). Gap "Web search is not configured."; reason "No model is configured, so no written brief." |
| `GET /briefs` without a session | 401 |
| Panel | "Briefs kept" 1; item "Acme Oy", "Meeting 2026-10-30" |
| Browser (Playwright, Chromium): sign in, prepare with attendees and a notes file, open, delete, sign out | Passed. No console errors. No horizontal scroll at 375 px width |
| `python -m meeting_prep.cli list / prepare / purge`; `prepare` without `--company` | JSON envelopes; exit 2 on bad usage |

## Not yet verified

- A live brief with the configured search, page reader, and model (written summary, citations, and talking points quality).
- Running on PostgreSQL. The migration is plain SQL with text columns, like the other agents, but has only been run on SQLite.
- The common chat calling `meeting-prep__prepare_meeting` with a real model.
