# Technical spec: sandbox sign-in

## Layout

```text
src/sandbox_host/
  migrations/0001_host.sql        users and sessions tables (host-owned)
  passwords.py                    scrypt hashing and verification
  users.py                        create/disable users; CLI: python -m sandbox_host.users create <name>
  auth.py                         sessions, login throttle, FastAPI dependency and middleware
  static/login.html               sign-in page
```

## Tables

```sql
CREATE TABLE IF NOT EXISTS sandbox_users (
  id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
  disabled INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sandbox_sessions (
  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL, expires_at TEXT NOT NULL);
```

Timestamps are ISO-8601 UTC text, as in the agents.

## Passwords

`hashlib.scrypt(password, salt=16 random bytes, n=2**14, r=8, p=1, dklen=32)`. Stored as `scrypt$n$r$p$salt_hex$hash_hex`. Verification uses `hmac.compare_digest`. For an unknown username the code still runs one scrypt computation against a fixed dummy hash, so response time does not reveal which usernames exist.

## Sessions

- Token: `secrets.token_urlsafe(32)`; the database stores `sha256(token)`.
- Created on successful login; cookie name `sandbox_session`, `Path=/`, `HttpOnly`, `SameSite=Strict`, `Max-Age=43200`.
- Each request checks `expires_at` (creation + 12 h), the idle limit (`last_seen_at` + 2 h), and that the user is not disabled. A valid request refreshes `last_seen_at` at most once per minute.

## Throttling

In-memory `dict[username] -> deque[timestamps]`. Failed attempts are recorded; while the username has 5 failures in 15 minutes, login returns 429 without checking the password. A successful login clears the record. Limit: per process only.

## Enforcement

- A FastAPI middleware checks every request except the public paths. For unsafe methods it checks `X-Sandbox-Request: 1` first (403 if missing), then the session.
- Public paths: `/api/health`, `/api/auth/login`, `/login`, `/static/*` for the login page assets (none needed; the page is inline).
- Unauthenticated: `/api/*` returns 401 JSON `{"error": "Sign in required"}`; other paths redirect to `/login?next=<path>` (relative paths only).
- The authenticated user is stored in `request.state.user`.

## Auth without a database

Without `DATABASE_URL` there is no user store. The middleware returns 503 JSON for protected routes, so the host never runs unauthenticated by accident.

## Interface changes

- `create_app(..., auth=True)`: auth is on by default. Tests may construct a host with an engine and create a user with `sandbox_host.users.create_user`.
- The agent UIs' `fetch` calls send `X-Sandbox-Request: 1` on unsafe methods. The static test in each UI checks this.
