# Acceptance results: sandbox sign-in

**Date:** 2026-10-24 · **Scope:** A-1 to A-18 in [test_plan.md](test_plan.md)

## Automated

- Offline suite: 275 passed, 68 skipped (PostgreSQL-gated).
- PostgreSQL 17 suite (`signalscout_ui_test`, host migration applied): 343 passed, 0 skipped.
- Sign-in tests (A-1 to A-16): all pass; UI request-header checks (A-17) pass.

## Live (uvicorn on PostgreSQL, curl)

| Check | Result |
|---|---|
| Health without sign-in | 200 |
| API without session | 401 `Sign in required` |
| Page without session | 303 to `/login?next=/` |
| Wrong password | 401, same message as an unknown user |
| POST without `X-Sandbox-Request` | 403 |
| Correct password | 200, session cookie set |
| API and `/api/auth/me` with session | 200, `{"username": ...}` |
| Logout, then API | 200, then 401 |

## Browser (claude-in-chrome)

| Check | Result |
|---|---|
| `/` redirects to the sign-in page | Pass |
| Wrong password shows "Invalid username or password" | Pass |
| Correct password opens the agent index with all three agents | Pass |
| Opening an agent page while signed in works (emeia dashboard loads its data) | Pass |
| Sign out returns to the sign-in page | Pass |

## Limits (as specified)

- Login throttling is per process; several host processes would each allow their own attempts.
- No password reset, email, MFA, or Entra sign-in yet.
- Cookies are only marked Secure when `SANDBOX_COOKIE_SECURE=true`; client deployments must set it behind HTTPS.
