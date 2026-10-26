# Test plan: agent standard (competitor-watch pilot)

| ID | Behavior | Case | Expected |
|---|---|---|---|
| AS-1 | S1 | service functions run without the API | add, list, check, review work when called directly |
| AS-2 | S1 | service validation | short name, bad website, long note raise ValueError |
| AS-3 | S2 | tools exist for every action; schemas are objects with typed properties | names and types correct |
| AS-4 | S2 | calling a tool runs the service and records the call | result returned; `on_call` receives the name |
| AS-5 | S2 | tool error | `{"error": ...}`, no traceback |
| AS-6 | S3 | CLI add then list | JSON envelope `{"ok": true, "result": ...}` |
| AS-7 | S3 | CLI error (duplicate) | `{"ok": false, "error": ...}`, exit 1 |
| AS-8 | S3 | CLI bad usage | exit 2, nothing written |
| AS-9 | S3 | CLI check with fake search and model | findings stored, JSON result has the count |
| AS-10 | S4 | CLI as a subprocess with a timeout | runs and returns JSON (smoke test, offline) |
| AS-11 | S5 | migrations listed by the host runner for this agent | additive file present; the `.down.sql` file is not applied as up |
| AS-12 | S6 | API, tool, and CLI give the same competitor list for the same data | equal |
| AS-13 | S6 | API, tool, and CLI give the same error category for a duplicate name | equal category |

## Exit criteria

AS-1 to AS-13 pass in the full suite. The live check (CLI check against Gemini) is recorded in `acceptance_results.md`.
