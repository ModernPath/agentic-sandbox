# Acceptance results: sales home and shared UI kit

**Date:** 2026-10-25 · **Scope:** H-1 to H-12 in [test_plan.md](test_plan.md)

## Automated

- Panel helper, registry check, static kit, home page, and agent panels: pass (H-1 to H-10).
- Full suite: 336 passed, 68 PostgreSQL-gated tests skipped.

## Browser (local host, development database, environment file loaded)

| Check | Result |
|---|---|
| Sales home shows a card per agent, each with its live panel (briefs, targets, files, competitor news) | Pass |
| Sign out from the home | Pass (verified in the earlier sign-in check; the home uses the same button) |
| One "Open" action per card | Pass after the fix (earlier version showed two) |

## Limits

- The existing agent pages (research brief, dashboard, file reader) still use their own styling; they can move to the shared kit next.
- Static files are public by design (stylesheet and script only, no data).
