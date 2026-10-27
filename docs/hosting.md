# Hosting requirements

For the person who will run the sandbox for a client. The application is one container for the host plus one PostgreSQL database. Everything else is configuration.

## What runs

- **Host**: one container built from `Dockerfile.host` (Python 3.12, runs as a non-root user). It serves the web pages, the API, and the agents.
- **Database**: PostgreSQL 17. `compose.sandbox.yaml` starts one with the pgvector extension. The host itself doesn't use vector columns, so a plain PostgreSQL 17 works. Any PostgreSQL URL works, including managed services.
- **Migrations** run automatically when the host starts. They are additive, and rollback is an explicit command.

## Network

- The host listens on port 8100 and is published on the loopback address only. Put a reverse proxy with HTTPS in front of it for users.
- There is no TLS inside the container. Set `SANDBOX_COOKIE_SECURE=true` once HTTPS is in place. The sign-in cookie depends on it.
- Outbound access is needed only for the providers that are enabled: Gemini (`generativelanguage.googleapis.com`), OpenAI (`api.openai.com`), Anthropic (`api.anthropic.com`), Exa (`api.exa.ai`), or the Azure OpenAI endpoint. Pages that agents read are fetched from the public internet. The fetcher refuses private and local addresses.

## Secrets and configuration

- All settings come from one environment file on the host. Keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `EXA_API_KEY`, `ANTHROPIC_API_KEY`, Azure) live only there. Nothing is logged or printed.
- Choose one model provider and one search provider per instance. Set spending limits with the provider (for example `SANDBOX_EXA_AGENT_MAX_COST_DOLLARS`).
- `SANDBOX_DB_PASSWORD` is required by the compose file.

## Accounts

- Operators create users with `python -m sandbox_host.users create <name>`. There is no self-sign-up.
- Sign-in is username and password, with a throttle after repeated failures. Single sign-on is planned, not built.
- Every page and API needs sign-in, except the health check and the sign-in page.

## What data goes where

| Data | Stored where | Kept for | Sent to a provider? |
|---|---|---|---|
| Client records (accounts, contacts, deals, tasks) | Database | Until archived. Archived records are kept and hidden | No |
| Uploaded files (up to 10 MB) | Database | Until deleted | Yes, when a person asks an agent about them |
| Meeting briefs (attendee names and roles included) | Database | 30 days, then deleted automatically | Search queries and page text; the brief is written by the model |
| Notes used for a meeting brief | Not stored; only the file's name and id are kept | Not kept | Yes, sent to the model for the one brief |
| Drafts (outward messages awaiting approval) | Database | Until deleted | No |
| Audit trail (who did what, and when) | Database, append-only | Kept | No |
| Chat conversation | Browser only | Until the page is closed | Yes, each message goes to the model |

Before connecting real client records, confirm with the client that sending prompts, uploaded documents, and meeting notes to the chosen model provider is acceptable. Use a provider contract that covers the client's data.

## Operations

- **Health check**: `GET /api/health`. It reports whether the database is reachable.
- **Backups**: the database is the only state that matters. The repository has no backup procedure yet, so back up the PostgreSQL volume, or use the managed service's backups.
- **Logs**: written to standard output of the container. There is no log shipping, metrics, or alerting yet.
- **Updates**: rebuild the image and restart. Migrations run on startup.

## Not in the repository yet

- The reverse proxy and HTTPS configuration.
- A backup and restore procedure.
- Monitoring and alerting.
- High availability. One host and one database.
