# Acceptance results: agent standard (competitor-watch pilot)

**Date:** 2026-10-25 · **Scope:** AS-1 to AS-13 in [test_plan.md](test_plan.md)

## Automated

- AS-1 to AS-13: pass (13 tests in `tests/test_competitor_standard.py`).
- Competitor-watch API and UI tests: still pass after the refactor (20 tests).
- Full suite: 349 passed, 68 PostgreSQL-gated tests skipped.

## Live (shared development database, Gemini search and model)

| Check | Result |
|---|---|
| `python -m competitor_watch.cli list` | Pass: JSON envelope with the stored competitor |
| `python -m competitor_watch.cli check` | Pass: `{"ok": true, "result": {"checked": 1}}` |

## Not yet done

- Scaffold template and `docs/agent-development.md` still describe the old shape. They change after this pilot is reviewed.
- Other host agents (`research_brief`, `emeia_dashboard`, `file_reader`, `people_company_search`) have not been moved to the standard yet.
- Subagents as CLI calls are specified, but no agent in this pilot needs one.
