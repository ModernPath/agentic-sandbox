# Test plan: Exa people and company search

Offline: a recording fake transport returns scripted run objects; a fake clock and sleep make polling deterministic. No network, no key.

| ID | Behavior | Case | Expected |
|---|---|---|---|
| X-1 | X1 | Create request | `POST /agent/runs`, `x-api-key`, body has query, effort, outputSchema, budget |
| X-2 | X1 | Fixed effort (`high`) | no `budget` key sent |
| X-3 | X1 | Invalid effort or cost outside 1–100 in Settings | `ConfigurationError` |
| X-4 | X2 | Status goes running → running → completed | polls three times; sleeps between polls |
| X-5 | X2 | Never terminal | `ProviderError` after `max_wait_seconds` |
| X-6 | X3 | Completed | structured, text, grounding, cost, stop reason returned |
| X-7 | X3 | Failed run | `ProviderError` containing status and stop reason; no output read |
| X-8 | X3 | Cancelled run | `ProviderError` |
| X-9 | X4 | Empty or >500 character query in CLI | exit code 2, no network call |
| X-10 | X4 | People and company schemas | `maxItems` present; no email or phone property |
| X-11 | X5 | CLI output for an item with grounding and one without | source URL printed; second labelled "unsourced" |
| X-12 | X6 | Model text containing terminal escape codes | printed with control characters removed |
| X-13 | X6 | Error message from a failed run | key value absent |

## Exit criteria

- X-1 to X-13 pass in the full suite.
- Live run recorded in `acceptance_results.md` (needs `EXA_API_KEY`).

## TDD order

Settings (X-3), client create and budget (X-1, X-2), polling (X-4, X-5), outcomes (X-6 to X-8), schemas (X-10), CLI (X-9, X-11, X-12), safety (X-13).
