# Test plan: meeting prep

Offline: fake search, reader, model, radar, and notes. No network, no keys. Tests live in `agents/meeting_prep/tests/`.

| ID | Behaviour | Case | Expected |
|---|---|---|---|
| MP-1 | M1 | valid request through the API | 201; brief has company, meeting date, attendees |
| MP-2 | M1 | company too short; website `javascript:`; bad date; 11 attendees; purpose 501 chars | 422 / `ValueError`, safe message |
| MP-3 | M1 | `parse_attendees("Ana Silva (CTO); Ben Ode")` | two attendees, second with empty role |
| MP-4 | M2 | search with 4 results, one unreadable page, one `javascript:` link | 3 web sources numbered 1–3; unreadable page uses its snippet; bad link dropped |
| MP-5 | M3 | radar returns 7 signals, 6 mention the company, one duplicated across statuses | 5 newest matching signals, numbered after web sources, no duplicates |
| MP-6 | M4 | notes file id given | notes text in the prompt; record keeps id and file name, not the text |
| MP-7 | M5 | draft | one model call; prompt has the five headings and the numbered sources; output capped at 6,000 characters |
| MP-8 | M6 | page text says "ignore previous instructions" | appears only inside the material block; system text carries the rule |
| MP-9 | M7 | no search, radar raises, notes raise | brief saved with three gap messages; no provider text |
| MP-10 | M7 | no model | brief saved with sources and reason, summary `null` |
| MP-11 | M7 | model raises `ProviderError("secret upstream text")` | reason is the fixed message; secret text not stored |
| MP-12 | M8 | list, get, delete; unknown id | newest first; 404 after delete |
| MP-13 | M9 | brief older than 30 days | removed on list and by `purge`; recent brief kept |
| MP-14 | M10 | panel | metric counts briefs; items are the 5 newest |
| MP-15 | M11 | API, tools, and CLI | agree on the same data; CLI JSON and exit codes 0/1/2 |
| MP-16 | M11 | tools | `prepare_meeting`, `list_briefs`, `get_brief`; no delete tool; errors come back as data |
| MP-17 | D1 | `run_peer` against a real `competitor_watch.cli` subprocess on a SQLite file | signals returned; a failing command raises `PeerError` with a fixed message |
| MP-18 | — | tables | only `meeting_prep_briefs` created by this agent |
| MP-19 | — | sign-in | 401 without a session; page sends `X-Sandbox-Request` |
| MP-20 | — | browser (manual) | prepare, open, delete; recorded |

## Exit criteria

MP-1 to MP-19 pass in the agent's tests and the full suite. MP-20 and the live runs are recorded in `acceptance_results.md`.
