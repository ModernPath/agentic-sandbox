# Technical spec: sandbox host

## Layout

```text
src/sandbox_host/
  __init__.py      public names: create_app, AgentSpec, HostSettings
  config.py        HostSettings.from_env: DATABASE_URL, bind warning helper
  database.py      make_engine(url), database_status(engine)
  migrations.py    apply_agent_migrations(engine, agent_name, directory)
  registry.py      AgentSpec dataclass and validate_registry(agents)
  app.py           create_app(settings, agents, engine=None, services=None)
  static/index.html  agent index page (fetches /api/agents)
agents/research_brief/
  api.py           APIRouter for briefs, plus make_agent_spec()
  store.py         BriefStore over SQLAlchemy Core text SQL
  migrations/0001_briefs.sql
  ui/index.html    small form and history page
```

Dependencies: FastAPI, SQLAlchemy, and psycopg are already pinned in `pyproject.toml`; no new packages.

## Database

- `make_engine(url)` uses `sqlalchemy.create_engine(url, pool_pre_ping=True)`. Supabase connection strings work as-is with `postgresql+psycopg://`. Pooling uses SQLAlchemy defaults; a client deployment behind Supabase's pooler should set a small pool size (documented, not coded).
- Schema is created only by migrations. No `create_all`.
- Agent tables use portable types where practical: ids are text UUIDs, timestamps are ISO-8601 text in UTC, and JSON payloads are text. Migrations still target PostgreSQL first.

## Migration runner (H4)

```sql
CREATE TABLE IF NOT EXISTS sandbox_schema_migrations (
  agent TEXT NOT NULL,
  name TEXT NOT NULL,
  checksum TEXT NOT NULL,
  applied_at TEXT NOT NULL,
  PRIMARY KEY (agent, name)
);
```

For each file (sorted by name): compute the SHA-256 of its bytes; if a row exists, compare checksums and raise `MigrationError` on mismatch, otherwise skip. If missing, execute the file's SQL and insert the row in one transaction. Multi-statement files are supported by executing the whole text with `exec_driver_sql`.

Concurrency: two host processes starting together could race. The runner takes a PostgreSQL advisory lock (`pg_advisory_xact_lock` on a fixed key) inside the same transaction when the dialect is PostgreSQL, and is a no-op on SQLite. Decision D2.

## Registry (H2)

`AgentSpec` fields: `name` (regex `^[a-z][a-z0-9-]{1,39}$`), `title`, `description`, `router` (`fastapi.APIRouter`), `migrations_dir: Path | None`, `ui_dir: Path | None`. `validate_registry(specs)` rejects bad names and duplicates with `RegistryError`.

## App (H1, H3, H5, H8)

`create_app(settings, agents, engine=None, services=None)`:

- Lifespan: if an engine exists, run migrations for every agent with `migrations_dir`. If the engine is absent, skip migrations and mark storage unavailable. Startup errors are re-raised so the process fails fast.
- `app.state.engine`, `app.state.settings`, and `app.state.services` (a dict of injectable dependencies such as LLM, search, and page reader factories) are set for agent routers.
- Each agent router is included at `/api/agents/{name}`. Its UI dir is mounted with `StaticFiles` at `/agents/{name}/` and `html=True`.
- `/api/health` runs `SELECT 1` through the engine when present: `database: "ok" | "error" | "not_configured"`. The error text is generic.
- Exception handlers map `ConfigurationError` and `ProviderError` to JSON 503/502 responses with safe messages.
- A bind warning is logged when `SANDBOX_HOST` is not a loopback address.

Agents get the engine with a dependency: `def get_engine(request: Request) -> Engine` raising 503 when none is configured.

## Example agent (H6, H7)

`agents/research_brief/api.py` defines `router = APIRouter()` and `make_agent_spec()`:

- `POST /briefs`: validates `topic` (1–300 characters). Builds clients from `app.state.services` if provided, otherwise from `Settings.from_env()` via `build_llm`/`build_search`. Calls `build_brief`. Stores a row whether or not sources were found. Returns the stored record. Provider configuration errors map to 503 through the app handler.
- `GET /briefs`: newest first, limit 50.
- `GET /briefs/{id}`: one record or 404.

`store.py` writes rows with `sqlalchemy.text`. JSON columns store `json.dumps` text.

Migration `0001_briefs.sql`:

```sql
CREATE TABLE IF NOT EXISTS research_brief_briefs (
  id TEXT PRIMARY KEY,
  topic TEXT NOT NULL,
  summary TEXT,
  sources_json TEXT NOT NULL,
  skipped_json TEXT NOT NULL,
  reason TEXT,
  provider TEXT,
  model TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS research_brief_briefs_created_idx ON research_brief_briefs (created_at);
```

## UI

`ui/index.html` is a single page with inline CSS and JavaScript: a topic form, a result panel showing summary and numbered sources, and a history list. It calls the agent's API with `fetch` and renders with `textContent` (no `innerHTML` for model or source text). Source URLs are shown as text and only `http(s)` links are made clickable.

## Decisions

- **D1 Migrations are plain SQL per agent**, not Alembic. The existing SignalScout app keeps Alembic. Plain files are easier for a dev agent to write, review, and copy into a client sandbox, and they need no ORM models.
- **D2 Advisory lock on PostgreSQL only.** Keeps SQLite tests simple while protecting real deployments.
- **D3 One process per sandbox.** The host is a single uvicorn process. Multiple workers need the advisory lock and are not tested in this slice.
- **D4 Services injection.** `create_app(services=...)` lets tests replace provider clients without environment variables.
- **D5 Supabase is a connection string.** No Supabase SDK is used. Row-level security and Supabase auth are client-deployment choices for the auth feature.

## Run

```sh
export DATABASE_URL='postgresql+psycopg://USER:URL_ENCODED_PASSWORD@HOST:5432/DB'
.venv/bin/uvicorn sandbox_host.app:create_app --factory --host 127.0.0.1 --port 8100
```

Open `http://127.0.0.1:8100/` for the index.
