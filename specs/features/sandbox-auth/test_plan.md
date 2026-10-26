# Test plan: sandbox sign-in

Offline cases use in-memory SQLite (StaticPool). PostgreSQL cases run against a migrated test database.

| ID | Behavior | Case | Expected |
|---|---|---|---|
| A-1 | A1, A2 | Create user; password under 12 characters | user stored with a scrypt hash, no plain password; short password rejected |
| A-2 | A1 | CLI create reads the password from a prompt, not argv | prompt used; password never in argv |
| A-3 | A3 | Correct credentials | 200, session cookie with HttpOnly and SameSite=Strict |
| A-4 | A3 | Wrong password and unknown user | identical status and body |
| A-5 | A4 | Stored session token | only the SHA-256 is in the database |
| A-6 | A4 | Session older than 12 hours; idle more than 2 hours | 401 |
| A-7 | A4 | Logout | cookie cleared; old cookie rejected |
| A-8 | A5 | API call without cookie | 401 JSON |
| A-9 | A5 | Page without cookie | redirect to `/login?next=...` |
| A-10 | A5 | `/api/health` and `/login` without cookie | 200 |
| A-11 | A6 | Six wrong passwords for one username | 429 on the sixth and afterwards; other usernames unaffected |
| A-12 | A7 | POST without `X-Sandbox-Request` | 403, even with a valid session |
| A-13 | A8 | `SANDBOX_COOKIE_SECURE=true` | cookie has Secure |
| A-14 | A9 | Disabled user with an existing session | 401 on next request |
| A-15 | A10 | Migrations at startup | `sandbox_users` and `sandbox_sessions` exist |
| A-16 | — | No DATABASE_URL | protected routes return 503 JSON |
| A-17 | — | Agent UI scripts send the header on unsafe methods | static check per UI (`research-brief`, `emeia-dashboard`) |
| A-18 | — | Browser check (manual) | redirect, wrong password, right password, sign-out; recorded in acceptance results |

## Exit criteria

All offline cases pass in the full suite; PostgreSQL run passes; browser check recorded.
