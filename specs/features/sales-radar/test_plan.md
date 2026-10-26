# Test plan: Sales radar

All tests run offline with fake search, reader, and model (as in `tests/test_example_competitor_watch.py`).

| Case | Covers | Expectation |
|---|---|---|
| S-1 check stores enriched signals | R2, R4 | Two valid signals stored with category, importance, source URL |
| S-2 invalid enum values fall back | R2 | Unknown category → `other`; unknown importance → `low` |
| S-3 signal citing a missing result is dropped | R2 | Only signals pointing at real results are stored |
| S-4 check skips seen URLs | R2 | Second check with the same results: `no_new_sources`, model not called |
| S-5 unparseable model output | R3 | Outcome `no_signals`; no signals stored; no provider text |
| S-6 provider error recorded safely | R3 | Outcome `error`, fixed message; other competitors still checked |
| S-7 non-http result dropped | R4, R10 | `javascript:` URL never stored |
| S-8 signal filters | R4 | status/category/importance/competitor filters return the right rows |
| S-9 review and dismiss | R5 | Status changes; default list excludes them |
| S-10 dashboard shape and counts | R6 | KPIs, by_category, zero-filled daily (14 entries), competitor rows, latest ≤25 |
| S-11 chat calls tools | R7 | Fake model calls `list_competitors`; reply and tool names returned |
| S-12 chat validation | R7 | >20 history entries or >1000-char message → 422 |
| S-13 chat without model | R7 | 503 with fixed message |
| S-14 competitor brief | R8 | Counts by category and newest new signals for one competitor |
| S-15 home redirect | R9 | `/` → 302 to `home_path` when signed in; login required otherwise |
| S-16 radar page | R9, R10 | `/agents/competitor-watch/` serves the page; no inline mock data; uses textContent |

Exit criteria: S-1…S-16 pass; the existing 33 competitor-watch tests still pass or are updated with the reason stated in the test; the full suite passes; live run recorded in `acceptance_results.md`.
