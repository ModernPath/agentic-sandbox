# Test plan: competitor watch

Offline: fake search and model services. No network, no keys.

| ID | Behavior | Case | Expected |
|---|---|---|---|
| CW-1 | C1 | add a competitor | 201; listed |
| CW-2 | C1 | duplicate name in another case ("ACME" after "Acme") | 409 |
| CW-3 | C1 | name too short; website not http(s); note too long | 422 |
| CW-4 | C1 | delete a competitor | removed; unknown id 404 |
| CW-5 | C2 | check all with two competitors | two findings with summaries and sources |
| CW-6 | C2 | check one competitor by id | one finding |
| CW-7 | C2 | search returns no results | "No recent news found" finding |
| CW-8 | C3 | finding stored | summary, sources, created time, reviewed false |
| CW-9 | C4 | mark reviewed; unknown id | reviewed true; 404 |
| CW-10 | C5 | results with `javascript:` and `http` links | only http link kept |
| CW-11 | C5 | model output of 3000 characters | stored at most 1200 |
| CW-12 | C6 | panel | metric counts unreviewed; items are the latest 5 unreviewed |
| CW-13 | C7 | search raises for one competitor | error finding for it; others still checked; no provider text stored |
| CW-14 | C7 | model raises | error finding; fixed message |
| CW-15 | C8 | tables | only `competitor_watch_*` created |
| CW-16 | — | sign-in required | 401 without session |
| CW-17 | — | browser check (manual) | add, check, review on the sales home; recorded |

## Exit criteria

CW-1 to CW-16 pass in the full suite. CW-17 and the live check are recorded in `acceptance_results.md`.
