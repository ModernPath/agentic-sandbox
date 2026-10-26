# Task spec: sandbox sign-in (username and password)

**Status:** Implementing · **Builds on:** [sandbox host](../sandbox-host/task_spec.md) · **Later:** Microsoft Entra sign-in (not in this slice)

## Goal

Every page and API of the sandbox host requires a signed-in user. Users are created by an operator on the host; there is no self-registration. This is the minimum needed before the host runs on a client's intranet.

## Behavior

- **A1 Accounts.** Users have a unique username, a password stored only as a salted scrypt hash, and a disabled flag. Users are created with `python -m sandbox_host.users create <username>`, which prompts for the password (never on the command line).
- **A2 Password policy.** At least 12 characters. Nothing else is enforced (no composition rules).
- **A3 Sign-in.** `POST /api/auth/login` with `{username, password}` sets an `HttpOnly`, `SameSite=Strict` session cookie. Wrong username and wrong password return the same response and take the same time.
- **A4 Sessions.** The cookie holds an opaque random token; only its SHA-256 is stored. Sessions expire after 12 hours of age and after 2 hours without use. Sign-out (`POST /api/auth/logout`) deletes the session.
- **A5 Protection.** All `/api/agents/*`, `/api/agents`, `/agents/*` (UI pages), and `/` require a valid session. Unauthenticated API calls get 401 JSON; unauthenticated page requests redirect to `/login`. `/api/health`, `/api/auth/login`, and the login page itself are public.
- **A6 Login throttling.** After 5 failed attempts for a username within 15 minutes, further attempts for that username are refused with 429 for the rest of the window. The counter is per process (documented limit).
- **A7 Request integrity.** Unsafe methods (POST, PATCH, PUT, DELETE) must include the header `X-Sandbox-Request: 1`. Browsers cannot send it cross-site without a preflight, which this host does not allow. The header is required for every unsafe API call, including login and logout.
- **A8 Secure cookie.** The cookie carries the `Secure` attribute when `SANDBOX_COOKIE_SECURE=true`. The default is `false` for loopback development; client deployments must set it true behind HTTPS.
- **A9 Disabled users.** A disabled user cannot sign in, and existing sessions for them stop working on their next request.
- **A10 Storage.** Users and sessions are host tables created by the host's own migration (`src/sandbox_host/migrations/0001_host.sql`), applied at startup with the same runner as agents.

## Out of scope

- Self-service registration, password reset, email, MFA, roles beyond "signed in".
- Entra / OIDC (planned).
- Multi-process login throttling (needs shared storage).

## Acceptance criteria

- A1–A10 pass in `test_plan.md`, offline and against PostgreSQL.
- A browser check shows: the page redirects to login, a wrong password is rejected, the right password opens the agent index, and sign-out returns to login.
