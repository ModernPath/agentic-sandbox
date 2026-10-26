# Test plan: agent scaffolding

| ID | Behavior | Case | Expected |
|---|---|---|---|
| G-1 | S3 | insert and fetch a row | round trip; values bound |
| G-2 | S3 | table name with a semicolon or spaces | ValueError, nothing executed |
| G-3 | S3 | column name injection in where | ValueError |
| G-4 | S3 | update returns False for unknown id | False |
| G-5 | S3 | fetch_many order and limit bounds | newest first; limit 0 or 501 refused |
| G-6 | S4 | signed_in_client without `with` | authenticated; `/api/agents` 200 |
| G-7 | S1 | scaffold `notes-demo` | folder created with all template files; names substituted |
| G-8 | S1 | scaffold into an existing folder | refused, nothing overwritten |
| G-9 | S1 | invalid name (`Bad Name`, `1x`) | refused |
| G-10 | S1 | registration | sandbox_app.py gains the import and the spec; compiles |
| G-11 | S1 | missing marker | refused before any file is written |
| G-12 | S2 | generated tests pass | run pytest in the generated folder with the sandbox on the path |
| G-13 | S6 | generated migration creates only `<module>_*` tables | checked by inspecting the SQL |
| G-14 | S2 | generated UI sends the sandbox header on unsafe requests | the UI test pattern from `tests/test_ui_request_header.py` |
| G-15 | S5 | docs mention every convention enforced by G-13 and G-14 | text check |

## Exit criteria

All G-cases pass in the full suite. The live check (scaffold a demo agent, register it, sign in, call its API) is recorded in `acceptance_results.md`.
